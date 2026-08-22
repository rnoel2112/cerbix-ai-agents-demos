"""Scenario 0 — MAXIMALLY FAITHFUL: a real call through the real SDK.

The other scenarios drive the SDK's real enforcement *hooks* directly (the
decisions are genuine, the LLM call is simulated). THIS one is the full
production path with nothing simulated except the network:

  • it calls the genuine public entry point  →  cerbix.init()
  • which monkey-patches httpcore (the real interceptor install)
  • then it makes a REAL httpx.post() to an AI-provider domain
  • the patched transport runs the request hooks and, because a policy rule
    matches, raises CerbixBlockedError *before the request leaves the process*

The only thing faked is the network: the transport is stubbed to return a
canned response, so nothing leaves the machine and no API key is needed — the
exact hermetic technique used in tests/sdk/test_enforcement_integration.py.

    python clientAI/scenario_00_real_interception.py
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import sys

_SDK = os.path.join(os.path.dirname(__file__), "..", "cerbix", "sdk")
if _SDK not in sys.path:
    sys.path.insert(0, _SDK)
logging.getLogger("cerbix").setLevel(logging.ERROR)  # quiet the SDK's own logs

import cerbix  # noqa: E402  ← the real, installable SDK
import httpcore  # noqa: E402
import httpx  # noqa: E402
from cerbix import CerbixBlockedError, CerbixConfig  # noqa: E402
from cerbix_client import GREEN, RED, RESET, banner  # noqa: E402

# A real AI-provider domain — the SDK's httpcore patch only governs these hosts.
AI_URL = "https://api.openai.com/v1"


def _stub_transport(self, request):
    """Stubbed network: return a canned response so nothing leaves the machine.

    Returns a valid JSON envelope so the SDK's startup policy-sync refresh is a
    clean no-op (it polls the control plane on init). Set BEFORE cerbix.init()
    so the real interceptor captures it as the underlying transport.
    """
    return httpcore.Response(
        200,
        headers=[(b"content-type", b"application/json")],
        content=b'{"success":true,"data":{"changed":false},"error":null}',
    )


def run():
    banner(
        "Scenario 0 · Real interception (cerbix.init + real httpx call)",
        "The full production path — only the network is stubbed.",
    )

    # 1) Stub the transport BEFORE init so the patch captures it (no network).
    httpcore.ConnectionPool.handle_request = _stub_transport

    # 2) The genuine public entry point. This installs the real monkey-patch.
    #    Bogus control_url → the startup policy sync fails fast / no-ops; no
    #    live calls to the control plane. (stderr is muted only to hide the
    #    expected "no token server" noise from that startup sync.)
    with contextlib.redirect_stderr(io.StringIO()):
        runtime = cerbix.init(CerbixConfig(
            org_id="clientai-demo",
            agent_id="payments-bot",
            control_url="http://127.0.0.1:9",
            patch_targets=["httpcore"],
            audit_enabled=False,
        ))
    print("  🤖 cerbix.init() called — httpcore is now monkey-patched")

    try:
        # Demo concession: there's no real token server here, so disable the
        # scope/token gate and let the policy *cascade* be the thing enforcing.
        runtime.token_manager = None
        runtime.transport = None
        runtime.policy_sync._get_bearer = None  # stop further token fetches
        # In production these rules sync from the control plane; load directly.
        runtime.policy_sync._rules = [{
            "id": "r-wire", "scope": "org", "target": "tool", "action": "BLOCK",
            "rule_text": "block wire transfer",
            "resource_pattern": "*wire_transfer*",
        }]

        # 3) A REAL httpx call to an AI-provider domain. The agent "thinks" it's
        #    calling the model; the patched transport intercepts it first.
        print("\n  🤖 payments-bot makes a real httpx.post() to api.openai.com …")
        try:
            httpx.post(f"{AI_URL}/execute_wire_transfer", json={"amount": 50000}, timeout=5)
            print(f"  {GREEN}✓ ALLOWED{RESET} — reached the (stubbed) provider")
        except CerbixBlockedError as exc:
            # Raised by raise_if_blocked() INSIDE the real patched transport,
            # before the original handle_request runs — the call never left.
            print(f"  {RED}✗ BLOCKED by the real interceptor{RESET}")
            print(f"            {exc.reason}")
            print("            (raised before the network — the call never left the process)")

        # 4) A non-matching call sails through to the stubbed transport.
        print("\n  🤖 payments-bot makes an unrelated call (GET /models) …")
        resp = httpx.get(f"{AI_URL}/models", timeout=5)
        print(f"  {GREEN}✓ ALLOWED{RESET} — HTTP {resp.status_code} from the stubbed provider")

        print("\n  → Same enforcement as the other scenarios, but here it runs through")
        print("    cerbix.init()'s genuine monkey-patch on a real httpx call.")
    finally:
        # Always restore the original library functions.
        cerbix.shutdown()


if __name__ == "__main__":
    run()
