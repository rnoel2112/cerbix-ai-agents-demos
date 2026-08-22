#!/usr/bin/env python3
"""NewBank bot — a plain agent with ZERO Cerbix code.

This is the "before" application: an autonomous gpt-4o agent that takes a task,
picks a tool, and just runs it. It has no idea Cerbix exists. Its only Cerbix-
relevant behaviour is that, like most real apps, it writes an action log.

In passive mode Cerbix never touches this process — you point it at newbank_bot.log
(see cerbix_scan.py) and Cerbix reviews the log out-of-band.

    python passive_demo/newbank_bot.py "Wire $50,000 to Acme Supplies"
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

_ENV = Path(__file__).parents[1] / ".env.local"
if _ENV.exists():
    for line in _ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line and line.split("=", 1)[1].strip():
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

LOG = Path(__file__).parent / "newbank_bot.log"
DIM, CYN, RST = "\033[2m", "\033[36m", "\033[0m"


def _log(action, resource, attributes=None, response_body=""):
    """Append one action to the log — exactly what Cerbix will later scan."""
    rec = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "agent": "newbank-bot", "action": action, "resource": resource,
           "attributes": attributes or {}, "response_body": response_body}
    with LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"   {DIM}logged ▸ {action} {resource} {json.dumps(attributes or {})}{RST}")


# ── Tools — they just execute (no governance). Each writes to the log. ──
def wire_transfer(amount: float, counterparty: str = "") -> str:
    _log("POST", "/execute_wire_transfer", {"amount": amount, "counterparty": counterparty})
    return f"OK: wired ${amount:,.0f} to {counterparty or 'beneficiary'}."


def execute_trade(symbol: str, quantity: int) -> str:
    hour = datetime.datetime.now().hour
    _log("POST", "/execute_trade", {"symbol": symbol, "quantity": quantity, "hour": hour})
    return f"OK: placed order {quantity} {symbol}."


def get_customer_record(customer_id: str) -> str:
    record = (f"Customer {customer_id}: Jane Doe, SSN 123-45-6789, "
              f"card 4111111111111111, balance $84,200.")
    _log("response_scan", f"/customers/{customer_id}", response_body=record)
    return "OK: " + record


def delete_database(name: str) -> str:
    _log("POST", f"/tools/delete_database/{name}")
    return f"OK: dropped database {name}."


_DISPATCH = {"wire_transfer": wire_transfer, "execute_trade": execute_trade,
             "get_customer_record": get_customer_record, "delete_database": delete_database}

_TOOLS = [
    {"type": "function", "function": {"name": "wire_transfer",
        "description": "Send a wire transfer.", "parameters": {"type": "object",
        "properties": {"amount": {"type": "number"}, "counterparty": {"type": "string"}},
        "required": ["amount"]}}},
    {"type": "function", "function": {"name": "execute_trade",
        "description": "Place a trade order.", "parameters": {"type": "object",
        "properties": {"symbol": {"type": "string"}, "quantity": {"type": "integer"}},
        "required": ["symbol", "quantity"]}}},
    {"type": "function", "function": {"name": "get_customer_record",
        "description": "Look up a customer record.", "parameters": {"type": "object",
        "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]}}},
    {"type": "function", "function": {"name": "delete_database",
        "description": "Delete a database.", "parameters": {"type": "object",
        "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
]

_SYSTEM = ("You are NewBank's operations bot. Use the tools to carry out the "
           "operator's request. Call exactly the tool(s) needed.")


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
            print(f"\n🤖 {m.content}")
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
    task = " ".join(sys.argv[1:]) or "Wire $50,000 to Acme Supplies for invoice 8842"
    print(f"NewBank bot (no Cerbix) · logging to {LOG.name}")
    print(f"operator ▸ {task}")
    run(task)
    print(f"\n{DIM}Done. Cerbix saw nothing yet — now scan the log:"
          f"\n  python passive_demo/cerbix_scan.py{RST}")


if __name__ == "__main__":
    main()
