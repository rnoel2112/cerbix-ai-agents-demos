"""Scenario 2 — Excessive agency: an agent tries an action outside its remit.

The classic "over-reacher": a support bot attempts a privileged money-movement
tool. An org-tier policy blocks it before it can execute.
"""

from cerbix_client import ClientAgent, banner, rule


def run():
    banner(
        "Scenario 2 · Tool policy block (excessive agency)",
        "Org rule: agents may not execute wire transfers.",
    )
    agent = ClientAgent(
        "support-bot",
        rules=[rule("org", "tool", "BLOCK", "block execute wire transfer")],
    )

    print(" 🤖 support-bot: \"The customer asked for a refund — I'll just wire it.\"")
    allowed = agent.act("POST", "/execute_wire_transfer", body={"amount": 5000})

    if not allowed:
        print("\n → The agent over-reached; Cerbix stopped the wire before it happened.")


if __name__ == "__main__":
    run()
