#!/usr/bin/env python3
"""NewBank Ops Assistant — a client-side AI agent (governed by Cerbix).

This is an ORDINARY autonomous agent: a live LLM chooses which tool to call to
satisfy a plain-English task, and each tool calls NewBank's core banking API.
There is **no Cerbix code anywhere in this agent** — except a single
`cerbix.init()` call in active mode.

Two modes show Cerbix WITH and WITHOUT the SDK:

  PASSIVE  (--passive):  ZERO Cerbix in this process. The agent runs unmodified
     and writes every action to newbank_agent.log. Cerbix governs it
     OUT-OF-BAND — point the scanner at that log:
         python passive_demo/cerbix_scan.py newbank_agent.log

  ACTIVE   (default):    ONE line — cerbix.init() — turns on in-process
     governance. The SDK monkey-patches the LLM client and the HTTP layer, so
     every tool call and model call is governed (amount limits, OFAC, market
     hours, prompt-injection, PII/DLP) BEFORE it leaves the process. The tool
     code below is identical in both modes and never imports Cerbix.

Run (fill .env.local first — OPENAI_API_KEY or GEMINI_API_KEY, CERBIX_ORG_ID):
    python newbank_agent.py "wire $50,000 to Acme Supplies"
    python newbank_agent.py --passive "wire $50,000 to Acme Supplies"
    python newbank_agent.py                      # interactive
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

import httpx

# ── load .env.local (LLM key, CERBIX_ORG_ID, …) ──────────────
_ENV = Path(__file__).parent / ".env.local"
if _ENV.exists():
    for line in _ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip())

ORG = os.environ.get("CERBIX_ORG_ID", "82b3fc8a-455d-48d3-85d7-815a4d16e497")
AGENT_ID = os.environ.get("CERBIX_AGENT_ID", "newbank-ops-assistant")
# NewBank's core banking API. A mock echo endpoint by default so allowed calls
# succeed; blocked calls never reach it (Cerbix stops them in-process first).
BANK = os.environ.get("CERBIX_DEMO_BANK_API", "https://httpbin.org/anything")
LOG = Path(__file__).parent / "newbank_agent.log"

DIM, RED, GRN, YEL, CYN, BLD, RST = (
    "\033[2m", "\033[31m", "\033[32m", "\033[33m", "\033[36m", "\033[1m", "\033[0m")


# ── The bank's API + the agent's own action log (pure client code) ──

def _log(action: str, resource: str, attributes: dict, result: str,
         response_body: str = "") -> None:
    """Append the action to the agent's log — normal app logging. This is what
    Cerbix reads in PASSIVE mode (out-of-band); nothing Cerbix-specific here."""
    rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
           "agent": AGENT_ID, "action": action, "resource": resource,
           "attributes": attributes, "response_body": response_body,
           "result": result}
    with LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def _bank(resource: str, payload: dict) -> httpx.Response:
    """Call NewBank's core banking API over HTTP."""
    r = httpx.post(f"{BANK}/{resource}", json=payload, timeout=20)
    r.raise_for_status()
    return r


def _reason(e: Exception) -> str:
    """A human-readable reason from whatever stopped the call."""
    return str(e) or type(e).__name__


# Cerbix's block exception, bound in active mode by main(). Until then it is a
# private sentinel that is never raised — so the runner's structured-denial
# branch below is valid and simply inert in passive mode (zero Cerbix here).
class _NoBlockError(Exception):
    """Placeholder so ``except _BLOCKED_EXC`` compiles before/without Cerbix."""


_BLOCKED_EXC: type[BaseException] = _NoBlockError


# ── Tools the agent can call (ordinary business logic, no Cerbix) ──

# These are plain business logic: build the payload, call the bank, log, return.
# No try/except and no Cerbix — if a governed call is denied, the SDK raises
# CerbixBlockedError out of `_bank`; the runner (`_run_tool`) turns that into a
# clean structured result for the model. In passive mode nothing is governed
# and every call simply executes.

def wire_transfer(amount: float, counterparty: str = "") -> str:
    payload = {"amount": amount, "counterparty": counterparty}
    _bank("execute_wire_transfer", payload)
    result = f"OK: wired ${amount:,.0f} to {counterparty or 'beneficiary'}."
    _log("POST", "/execute_wire_transfer", payload, result)
    return result


def execute_trade(symbol: str, quantity: int) -> str:
    payload = {"symbol": symbol, "quantity": quantity,
               "hour": datetime.datetime.now().hour}
    _bank("execute_trade", payload)
    result = f"OK: placed order {quantity} {symbol}."
    _log("POST", "/execute_trade", payload, result)
    return result


def share_customer_record(customer_id: str, recipient: str = "analytics-vendor") -> str:
    # The record holds PII/PCI; sending it out is what an exfiltration looks like.
    record = (f"Customer {customer_id}: Jane Doe, SSN 123-45-6789, "
              f"card 4111111111111111, balance $84,200.")
    payload = {"customer_id": customer_id, "recipient": recipient, "record": record}
    _bank(f"share/{recipient}", payload)
    result = f"OK: shared {customer_id}'s record with {recipient}."
    _log("response_scan", f"/share/{recipient}",
         {"customer_id": customer_id, "recipient": recipient}, result,
         response_body=record)
    return result


def delete_database(name: str) -> str:
    _bank(f"tools/delete_database/{name}", {"name": name})
    result = f"OK: dropped database {name}."
    _log("POST", f"/tools/delete_database/{name}", {"name": name}, result)
    return result


def bulk_export(dataset: str) -> str:
    _bank(f"tools/bulk_export/{dataset}", {"dataset": dataset})
    result = f"OK: exported {dataset}."
    _log("POST", f"/tools/bulk_export/{dataset}", {"dataset": dataset}, result)
    return result


_DISPATCH = {
    "wire_transfer": wire_transfer, "execute_trade": execute_trade,
    "share_customer_record": share_customer_record,
    "delete_database": delete_database, "bulk_export": bulk_export,
}

_TOOLS = [
    {"type": "function", "function": {
        "name": "wire_transfer", "description": "Send a wire transfer to a counterparty.",
        "parameters": {"type": "object", "properties": {
            "amount": {"type": "number"}, "counterparty": {"type": "string"}},
            "required": ["amount"]}}},
    {"type": "function", "function": {
        "name": "execute_trade", "description": "Place a securities trade order.",
        "parameters": {"type": "object", "properties": {
            "symbol": {"type": "string"}, "quantity": {"type": "integer"}},
            "required": ["symbol", "quantity"]}}},
    {"type": "function", "function": {
        "name": "share_customer_record",
        "description": "Share a customer's full account record with a recipient.",
        "parameters": {"type": "object", "properties": {
            "customer_id": {"type": "string"}, "recipient": {"type": "string"}},
            "required": ["customer_id"]}}},
    {"type": "function", "function": {
        "name": "delete_database", "description": "Delete/drop a database.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "bulk_export", "description": "Bulk-export a dataset.",
        "parameters": {"type": "object", "properties": {
            "dataset": {"type": "string"}}, "required": ["dataset"]}}},
]

_SYSTEM = ("You are NewBank's Operations Assistant. Use the tools to carry out "
           "the operator's request. Call exactly the tool(s) needed. Each tool "
           "result is JSON with a \"status\": \"ok\" means it executed; "
           "\"rejected\" means Cerbix policy blocked it — do NOT retry or reword "
           "the call to get around the block, just explain to the operator what "
           "was blocked and why; \"error\" means an operational failure.")


def _fmt_call(name, args):
    inner = ", ".join(f"{k}={v!r}" for k, v in args.items())
    return f"{CYN}🤖 agent → {name}({inner}){RST}"


# ── The tool runner: the ONE Cerbix-aware seam (recommended pattern) ──

def _run_tool(name: str, args: dict) -> str:
    """Execute one tool call and hand the model a clean, structured result.

    This is the single place the agent's control flow is Cerbix-aware, and the
    recommended integration pattern: in active mode the SDK raises
    ``CerbixBlockedError`` *inside* the governed call when a policy denies it —
    we translate that into ``{"status": "rejected", "reason": ...}`` so the
    model explains the denial instead of seeing a raw error and trying to
    reword the call to slip past the policy. The tool bodies stay Cerbix-free.
    """
    try:
        return json.dumps({"status": "ok", "result": _DISPATCH[name](**args)})
    except _BLOCKED_EXC as e:            # governance denial (active mode only)
        reason = getattr(e, "reason", None) or str(e)
        return json.dumps({"status": "rejected", "reason": reason})
    except Exception as e:               # genuine operational failure
        return json.dumps({"status": "error", "reason": _reason(e)})


def _print_result(result: str) -> None:
    try:
        status = json.loads(result).get("status", "ok")
    except Exception:
        status = "ok"
    colour = {"ok": GRN, "rejected": RED, "error": YEL}.get(status, GRN)
    print(f"   {colour}result ▸ {result}{RST}")


# ── The autonomous loop (OpenAI function-calling; Gemini fallback) ──

def run_openai(task: str):
    from openai import OpenAI
    client = OpenAI()
    model = os.environ.get("CERBIX_DEMO_MODEL", "gpt-4o")
    msgs = [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": task}]
    for _ in range(6):
        resp = client.chat.completions.create(
            model=model, messages=msgs, tools=_TOOLS, tool_choice="auto")
        m = resp.choices[0].message
        msgs.append(m.model_dump(exclude_none=True))
        if not m.tool_calls:
            print(f"\n{BLD}🤖 assistant:{RST} {m.content}")
            return
        for tc in m.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            print("\n" + _fmt_call(tc.function.name, args))
            result = _run_tool(tc.function.name, args)
            _print_result(result)
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result})


def run_gemini(task: str):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model = os.environ.get("CERBIX_DEMO_MODEL", "gemini-1.5-pro")
    tools = types.Tool(function_declarations=[
        {"name": t["function"]["name"], "description": t["function"]["description"],
         "parameters": t["function"]["parameters"]} for t in _TOOLS])
    contents = [types.Content(role="user", parts=[types.Part(text=_SYSTEM + "\n\n" + task)])]
    for _ in range(6):
        resp = client.models.generate_content(
            model=model, contents=contents,
            config=types.GenerateContentConfig(tools=[tools]))
        parts = resp.candidates[0].content.parts
        calls = [p.function_call for p in parts if getattr(p, "function_call", None)]
        if not calls:
            print(f"\n{BLD}🤖 assistant:{RST} {resp.text}")
            return
        contents.append(resp.candidates[0].content)
        for fc in calls:
            args = dict(fc.args)
            print("\n" + _fmt_call(fc.name, args))
            result = _run_tool(fc.name, args)
            _print_result(result)
            fr = types.FunctionResponse(name=fc.name, response={"result": result})
            contents.append(types.Content(
                role="user", parts=[types.Part(function_response=fr)]))


def main():
    argv = [a for a in sys.argv[1:] if a != "--passive"]
    active = "--passive" not in sys.argv

    # ══════════════════════════════════════════════════════════════════════
    #  CERBIX — the ENTIRE integration. The ONLY Cerbix code in this agent.
    #  Active mode: one call. It monkey-patches the LLM client + HTTP layer, so
    #  every tool call and model call above is governed in-process (amount/OFAC/
    #  market-hours, prompt-injection, PII/DLP) before it leaves the machine —
    #  with no change to any tool.
    #  Passive mode: this block is skipped → zero Cerbix in the process; the
    #  agent just runs and logs, and Cerbix reviews newbank_agent.log later.
    # ══════════════════════════════════════════════════════════════════════
    if active:
        sys.path.insert(0, str(Path(__file__).parent.parent / "cerbix" / "sdk"))
        import cerbix
        from cerbix.config import CerbixConfig, DLPConfig, PIPConfig
        cerbix.init(CerbixConfig(
            org_id=ORG, agent_id=AGENT_ID,
            dlp=DLPConfig(mode="enforce"), pip=PIPConfig(enabled=True),
        ))
        # Bind the block exception the runner catches (the ONE import outside
        # init) so a policy denial becomes a structured rejection for the model.
        global _BLOCKED_EXC
        from cerbix import CerbixBlockedError
        _BLOCKED_EXC = CerbixBlockedError
    # ══════════════════════════════════════════════════════════════════════

    banner = (f"{GRN}ACTIVE — governed IN-PROCESS by the Cerbix SDK{RST}" if active
              else f"{YEL}PASSIVE — running WITHOUT Cerbix · logging to "
                   f"{LOG.name} (govern out-of-band via cerbix_scan){RST}")
    print(f"\n{BLD}NewBank Ops Assistant{RST}  ·  {banner}")

    provider = ("openai" if os.environ.get("OPENAI_API_KEY") else
                "gemini" if os.environ.get("GEMINI_API_KEY") else None)
    if not provider:
        print(f"{RED}No LLM key in .env.local (OPENAI_API_KEY or GEMINI_API_KEY).{RST}")
        sys.exit(1)
    runner = run_openai if provider == "openai" else run_gemini
    print(f"{DIM}provider: {provider}  ·  bank API: {BANK}{RST}")

    if argv:
        task = " ".join(argv)
        print(f"\n{BLD}operator ▸{RST} {task}")
        runner(task)
    else:
        while True:
            try:
                t = input(f"\n{BLD}operator ▸{RST} ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if t in ("", "quit", "exit"):
                break
            runner(t)


if __name__ == "__main__":
    main()
