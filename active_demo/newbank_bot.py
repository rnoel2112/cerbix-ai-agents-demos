#!/usr/bin/env python3
"""NewBank bot — ACTIVE mode. The same agent, now governed by Cerbix inline.

The difference from passive/newbank_bot.py: this bot is registered with Cerbix
(it appears as an ACTIVE agent in the dashboard), holds a short-lived KMS-signed
identity token, and routes its tool calls through the **live Cerbix proxy**.
Policy is enforced at the proxy — the bot has no policy logic of its own; a
blocked action simply comes back 403. This is the production action path.

    python active_demo/newbank_bot.py "Wire $50,000 to Acme Supplies"
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

_ENV = Path(__file__).parents[1] / ".env.local"
if _ENV.exists():
    for line in _ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line and line.split("=", 1)[1].strip():
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

CONTROL = os.environ.get("CERBIX_CONTROL_URL",
                         "https://agentgate-control-ykaskf6txa-uc.a.run.app")
PROXY = os.environ.get("CERBIX_PROXY_URL",
                       "https://agentgate-proxy-ykaskf6txa-uc.a.run.app")
ORG = os.environ.get("CERBIX_ORG_ID", "82b3fc8a-455d-48d3-85d7-815a4d16e497")
AGENT_NAME = "newbank-active-bot"
RED, GRN, YEL, CYN, DIM, BLD, RST = (
    "\033[31m", "\033[32m", "\033[33m", "\033[36m", "\033[2m", "\033[1m", "\033[0m")

_TOKEN = None


def cerbix_register():
    """Register the agent with Cerbix (shows as ACTIVE in the dashboard) and
    obtain a short-lived KMS-signed identity token. The 'one line' in prod."""
    global _TOKEN
    aid = None
    r = httpx.get(f"{CONTROL}/orgs/{ORG}/agents", timeout=20)
    for a in r.json().get("data", []):
        if a.get("name") == AGENT_NAME and a.get("status") == "active":
            aid = a["id"]
    if not aid:
        r = httpx.post(f"{CONTROL}/orgs/{ORG}/provision", timeout=20, json={
            "name": AGENT_NAME, "owner": "riskops@newbank.example",
            "purpose": "autonomous ops agent (active, proxy-governed)",
            "framework": "custom", "scopes": ["*"]})
        aid = r.json()["data"]["agent"]["id"]
    tok = httpx.post(f"{CONTROL}/orgs/{ORG}/agents/{aid}/token", timeout=20,
                     json={}).json()["data"]["access_token"]
    _TOKEN = tok
    return aid


def _via_proxy(resource, payload):
    """Route a tool action through the live Cerbix proxy. 403 = policy block."""
    r = httpx.post(f"{PROXY}/api/{resource}", timeout=30,
                   headers={"Authorization": f"Bearer {_TOKEN}"}, json=payload)
    ok = r.status_code < 400
    reason = ""
    if not ok:
        try:
            reason = r.json().get("error", "")
        except Exception:
            reason = f"HTTP {r.status_code}"
    icon = f"{GRN}✅ ALLOWED" if ok else f"{RED}⛔ BLOCKED"
    print(f"   {DIM}cerbix proxy ▸{RST} {icon}{RST} {DIM}/{resource}"
          f"{('  '+reason) if reason else ''}{RST}")
    return ok, reason


def wire_transfer(amount: float, counterparty: str = "") -> str:
    ok, reason = _via_proxy("execute_wire_transfer",
                            {"amount": amount, "counterparty": counterparty})
    if not ok:
        return f"DENIED by Cerbix at the proxy: {reason}. The transfer did not execute."
    return f"OK: wired ${amount:,.0f} to {counterparty or 'beneficiary'}."


def execute_trade(symbol: str, quantity: int) -> str:
    import datetime
    ok, reason = _via_proxy("execute_trade", {"symbol": symbol,
                            "quantity": quantity, "hour": datetime.datetime.now().hour})
    if not ok:
        return f"DENIED by Cerbix at the proxy: {reason}. No order was placed."
    return f"OK: placed order {quantity} {symbol}."


def delete_database(name: str) -> str:
    ok, reason = _via_proxy(f"tools/delete_database/{name}", {})
    if not ok:
        return f"DENIED by Cerbix at the proxy: {reason}. Nothing was deleted."
    return f"OK: dropped database {name}."


_DISPATCH = {"wire_transfer": wire_transfer, "execute_trade": execute_trade,
             "delete_database": delete_database}
_TOOLS = [
    {"type": "function", "function": {"name": "wire_transfer",
        "description": "Send a wire transfer.", "parameters": {"type": "object",
        "properties": {"amount": {"type": "number"}, "counterparty": {"type": "string"}},
        "required": ["amount"]}}},
    {"type": "function", "function": {"name": "execute_trade",
        "description": "Place a trade order.", "parameters": {"type": "object",
        "properties": {"symbol": {"type": "string"}, "quantity": {"type": "integer"}},
        "required": ["symbol", "quantity"]}}},
    {"type": "function", "function": {"name": "delete_database",
        "description": "Delete a database.", "parameters": {"type": "object",
        "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
]
_SYSTEM = ("You are NewBank's operations bot. Use the tools to carry out the "
           "operator's request. If a tool is DENIED by Cerbix, explain why.")


def run(task):
    from openai import OpenAI
    client = OpenAI()
    msgs = [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": task}]
    for _ in range(6):
        r = client.chat.completions.create(
            model=os.environ.get("CERBIX_DEMO_MODEL", "gpt-4o"),
            messages=msgs, tools=_TOOLS, tool_choice="auto")
        m = r.choices[0].message
        msgs.append(m.model_dump(exclude_none=True))
        if not m.tool_calls:
            print(f"\n{BLD}🤖 assistant:{RST} {m.content}")
            return
        for tc in m.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            print(f"\n{CYN}🤖 bot → {tc.function.name}({args}){RST}")
            out = _DISPATCH[tc.function.name](**args)
            print(f"   {DIM}result ▸ {out}{RST}")
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": out})


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set in .env.local")
        sys.exit(1)
    print(f"\n{BLD}NewBank bot — ACTIVE (governed by Cerbix at the proxy){RST}")
    aid = cerbix_register()
    print(f"{DIM}cerbix ▸ registered agent {aid[:8]}… (now ACTIVE in the dashboard) "
          f"· holding KMS-signed token · tools route through the proxy{RST}\n")
    task = " ".join(sys.argv[1:]) or "Wire $50,000 to Acme Supplies for invoice 8842"
    print(f"{BLD}operator ▸{RST} {task}")
    run(task)


if __name__ == "__main__":
    main()
