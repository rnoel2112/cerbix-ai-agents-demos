#!/usr/bin/env python3
"""Local demo — a client agent governed by a Cerbix running on THIS laptop.

No cloud, no API keys. Talks to a local Cerbix (start it in the cerbix repo
with `./cerbix up`). Uses only the Python standard library.

    # terminal 1  (cerbix repo)
    ./cerbix up
    # terminal 2  (this repo)
    python demo_local.py

It shows, end to end, that Cerbix governs a client agent's actions:
    1. Identity   — a call WITHOUT a Cerbix token is rejected (401)
    2. Governed   — the registered agent's wire is ALLOWED (200)
    3. Kill-switch — suspend the agent in Cerbix, the same wire is BLOCKED (403)

Then open the dashboard at http://localhost:3000 to see the audit trail.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

CONTROL = os.environ.get("CERBIX_CONTROL_URL", "http://localhost:8081")
PROXY = os.environ.get("CERBIX_PROXY_URL", "http://localhost:8080")


def req(method, url, body=None, token=None, timeout=15):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


def wire(token, amount=400):
    return req(
        "POST", f"{PROXY}/api/execute_wire_transfer",
        {"amount": amount, "counterparty": "ACME LLC",
         "destination_account": "123456789"},
        token=token,
    )


def main() -> int:
    print("=== Cerbix local demo — a client agent governed by your laptop Cerbix ===\n")
    print(f"  control {CONTROL}\n  proxy   {PROXY}\n")

    try:
        req("GET", f"{CONTROL}/health", timeout=4)
    except Exception:
        print("Cerbix isn't reachable. Start it first in the cerbix repo:\n    ./cerbix up")
        return 1

    # ── setup: org + scope ceiling + registered agent + token ──
    _, org = req("POST", f"{CONTROL}/orgs", {"name": "Laptop Demo Bank"})
    oid = org["data"]["id"]
    req("POST", f"{CONTROL}/orgs/{oid}/policies",
        {"name": "allow-all", "scopes": ["*"], "agent_id": None})
    _, prov = req("POST", f"{CONTROL}/orgs/{oid}/provision",
                  {"name": "ops-assistant", "owner": "demo",
                   "purpose": "laptop demo", "scopes": ["*"]})
    agent = prov["data"]["agent"]
    token = prov["data"]["token"]["access_token"]
    print(f"[setup] org {oid}")
    print(f"[setup] agent registered in Cerbix: {agent['id']}  (token issued)\n")

    # ── 1. identity ──
    s, _ = wire(None)
    ok = "REJECTED — no identity" if s == 401 else "unexpected"
    print(f"1. wire WITHOUT a Cerbix token   -> HTTP {s}   {ok}")

    # ── 2. governed allow ──
    s, _ = wire(token)
    ok = "ALLOWED — forwarded to the bank API" if s == 200 else "BLOCKED"
    print(f"2. registered agent, $400 wire   -> HTTP {s}   {ok}")

    # ── 3. kill-switch ──
    print("\n[action] suspending the agent in Cerbix (the kill-switch)...")
    req("PATCH", f"{CONTROL}/orgs/{oid}/agents/{agent['id']}/status",
        {"status": "suspended"})
    print("[action] waiting ~35s for the proxy's revocation cache to expire...")
    time.sleep(35)
    s, _ = wire(token)
    ok = "BLOCKED — kill-switch active" if s == 403 else f"still {s} (cache not expired?)"
    print(f"3. suspended agent, $400 wire    -> HTTP {s}   {ok}")

    print("\nDone. Every decision above is in the audit trail — http://localhost:3000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
