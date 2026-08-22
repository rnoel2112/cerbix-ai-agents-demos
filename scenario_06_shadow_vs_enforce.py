"""Scenario 6 — Shadow vs enforce: the same leak, two modes.

Teams roll Cerbix out in *shadow* first (observe, never block) to measure
impact, then flip to *enforce*. Same PII-leaking response, two agents: shadow
records it and lets it through; enforce blocks it.
"""

from cerbix_client import ClientAgent, banner

LEAK = "Here is the SSN you asked for: 123-45-6789."


def run():
    banner(
        "Scenario 6 · Shadow vs enforce",
        "Roll out safely: observe first, then enforce — same code, one flag.",
    )

    print(" Shadow mode (observe-only):")
    shadow_agent = ClientAgent("shadow-bot", dlp=True, shadow=True)
    shadow_agent.receive(LEAK)
    print("   → recorded for review, but NOT blocked.")

    print("\n Enforce mode:")
    enforce_agent = ClientAgent("enforce-bot", dlp=True, shadow=False)
    enforce_agent.receive(LEAK)
    print("   → same finding, now blocked.")


if __name__ == "__main__":
    run()
