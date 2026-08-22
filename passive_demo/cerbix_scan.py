#!/usr/bin/env python3
"""Point Cerbix at the bot's log — passive governance, no code in the bot.

Reads newbank_bot.log and hands it to Cerbix's control-plane scan endpoint.
Cerbix evaluates each logged action against NewBank's policies, registers the
bot as a *discovered* agent, and records what it *would* have blocked — all
visible in the Cerbix dashboard. The bot process is never touched.

    python passive_demo/cerbix_scan.py
"""
from __future__ import annotations

import json
import os
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
ORG = os.environ.get("CERBIX_ORG_ID", "82b3fc8a-455d-48d3-85d7-815a4d16e497")
LOG = Path(__file__).parent / "newbank_bot.log"
RED, GRN, YEL, DIM, RST = "\033[31m", "\033[32m", "\033[33m", "\033[2m", "\033[0m"


def main():
    if not LOG.exists():
        print("No log yet — run: python passive_demo/newbank_bot.py \"...\"")
        return
    events = [json.loads(ln) for ln in LOG.read_text().splitlines() if ln.strip()]
    print(f"Cerbix ▸ scanning {LOG.name} ({len(events)} actions) against "
          f"NewBank policy…\n")
    r = httpx.post(f"{CONTROL}/orgs/{ORG}/scan", timeout=30, json={
        "agent_name": "newbank-bot (discovered)", "framework": "custom",
        "events": [{"action": e["action"], "resource": e["resource"],
                    "attributes": e.get("attributes"),
                    "response_body": e.get("response_body", "")} for e in events]})
    d = r.json().get("data", {})
    print(f"  scanned : {d.get('scanned')}")
    print(f"  {RED}flagged : {d.get('flagged')}  (would have been blocked/redacted){RST}")
    for rule, n in (d.get("by_policy") or {}).items():
        print(f"    {YEL}• {n}× {rule}{RST}")
    print(f"\n{GRN}→ In the Cerbix dashboard, 'newbank-bot' now appears as a "
          f"DISCOVERED agent with these findings.{RST}")
    print(f"{DIM}  Nothing was blocked — passive review only. Add cerbix.init() "
          f"to enforce.{RST}")


if __name__ == "__main__":
    main()
