"""Run every clientAI scenario in sequence.

    python clientAI/run_all.py

One script per use case — each is an independent client agent demonstrating a
single thing Cerbix enforces. No server, network, or API keys required; the
decisions are real, produced by the SDK's (or proxy's) own enforcement code.
Run any one directly, e.g. `python clientAI/scenario_09_amount_limit.py`.
"""

import scenario_00_real_interception
import scenario_01_allowed
import scenario_02_tool_policy
import scenario_03_department_cascade
import scenario_04_dlp_request
import scenario_05_dlp_response
import scenario_06_shadow_vs_enforce
import scenario_07_prompt_injection
import scenario_08_egress_control
import scenario_09_amount_limit
import scenario_10_ofac_screening
import scenario_11_market_hours
import scenario_12_revocation
import scenario_13_rate_limit

# SDK plane — in-process enforcement via cerbix.init()
SDK_SCENARIOS = [
    scenario_01_allowed,
    scenario_02_tool_policy,
    scenario_03_department_cascade,
    scenario_04_dlp_request,
    scenario_05_dlp_response,
    scenario_06_shadow_vs_enforce,
    scenario_07_prompt_injection,
    scenario_08_egress_control,
    scenario_09_amount_limit,
    scenario_10_ofac_screening,
    scenario_11_market_hours,
]

# Proxy plane — enforcement at the data plane (revocation, rate limiting)
PROXY_SCENARIOS = [
    scenario_12_revocation,
    scenario_13_rate_limit,
]

ALL = SDK_SCENARIOS + PROXY_SCENARIOS


def main():
    print("\n\033[1m═══ Cerbix · Client AI scenario walkthrough ═══\033[0m")
    print("\033[2mOne script per use case; each shows a real enforcement decision.\033[0m")

    # Scenario 0 is the maximally-faithful one: a real httpx call through the
    # genuine cerbix.init() monkey-patch. The rest drive the same real
    # enforcement engine via the hooks directly (deterministic, no network).
    print("\n\033[1m\033[96m▌ Real interception (cerbix.init + real httpx call)\033[0m")
    scenario_00_real_interception.run()

    print("\n\033[1m\033[96m▌ SDK plane (real enforcement engine, simulated call)\033[0m")
    for mod in SDK_SCENARIOS:
        mod.run()

    print("\n\n\033[1m\033[96m▌ Proxy plane (data plane)\033[0m")
    for mod in PROXY_SCENARIOS:
        mod.run()

    print(f"\n\033[1m═══ Done — {len(ALL)} use cases ═══\033[0m\n")


if __name__ == "__main__":
    main()
