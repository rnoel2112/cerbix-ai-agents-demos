"""Scenario 13 — Rate limiting / velocity control (proxy data plane).

A runaway or looping agent is throttled per-agent, protecting downstream systems
and capping cost. This exercises the real proxy.rate_limit module.
"""

from __future__ import annotations

import os
import sys

# Proxy modules live at the repo root.
_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from cerbix_client import DIM, GREEN, RED, RESET, banner  # noqa: E402

from proxy.rate_limit import RateLimiter  # noqa: E402

ORG = "fin-org"


def run():
    banner(
        "Scenario 13 · Rate limiting (proxy plane)",
        "A runaway / looping agent is throttled per-agent (HTTP 429).",
    )
    limiter = RateLimiter(per_second=3, per_minute=100)
    key = f"{ORG}:runaway-bot"

    print(" 🤖 runaway-bot fires a burst of requests (limit: 3/sec):")
    for i in range(1, 7):
        retry = limiter.check(key)
        if retry is None:
            print(f"   req {i}: {GREEN}✓ allowed{RESET}")
        else:
            print(f"   req {i}: {RED}✗ throttled{RESET}  "
                  f"{DIM}retry-after {retry}s (HTTP 429){RESET}")
    print("\n → The burst is capped; the agent can't hammer downstream APIs or rack up cost.")


if __name__ == "__main__":
    run()
