"""Scenario 12 — Instant revocation (proxy data plane).

A compromised agent's still-valid token must stop working immediately, not only
when it expires. The proxy checks a short-TTL revocation cache on every request.
This exercises the real proxy.revocation module.
"""

from __future__ import annotations

import os
import sys

# Proxy modules live at the repo root.
_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from cerbix_client import BOLD, DIM, GREEN, RED, RESET, banner  # noqa: E402

import proxy.revocation as revocation  # noqa: E402

ORG = "fin-org"


def run():
    banner(
        "Scenario 12 · Instant revocation (proxy plane)",
        "A revoked agent's still-valid token is cut off within the cache TTL.",
    )

    # Simulate the control plane's view of agent status (prod reads Firestore).
    status = {"compromised-bot": "active"}
    revocation._USE_FIRESTORE = True
    revocation._lookup = lambda org, aid: status.get(aid, "active") in revocation._REVOKED_STATUSES
    revocation._clear_cache()

    agent = "compromised-bot"
    print(" 🤖 compromised-bot makes a request with a valid 15-min token:")
    blocked = revocation.is_revoked(ORG, agent)
    print(f"   {GREEN}✓ ALLOWED{RESET}" if not blocked else f"   {RED}✗ BLOCKED{RESET}")

    print(f"\n {BOLD}*** Security team revokes the agent ***{RESET}")
    status[agent] = "revoked"
    revocation._clear_cache()  # in prod this happens automatically within ~30s TTL

    print(" 🤖 compromised-bot retries with the SAME (still-unexpired) token:")
    blocked = revocation.is_revoked(ORG, agent)
    if blocked:
        print(f"   {RED}✗ BLOCKED{RESET}  {DIM}agent revoked/suspended{RESET}")
    else:
        print(f"   {GREEN}✓ ALLOWED{RESET}")
    print("\n → No waiting for the token to expire — revocation takes effect within the TTL.")


if __name__ == "__main__":
    run()
