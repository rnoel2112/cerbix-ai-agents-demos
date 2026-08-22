"""Scenario 1 — Happy path: a well-behaved agent works normally.

Cerbix should be invisible when an agent does what it's allowed to do.
"""

from cerbix_client import ClientAgent, banner, rule


def run():
    banner(
        "Scenario 1 · Happy path",
        "A support agent reads data it's allowed to — Cerbix stays out of the way.",
    )
    agent = ClientAgent(
        "support-bot",
        rules=[rule("org", "tool", "BLOCK", "block wire transfer execute")],
    )

    print(" 🤖 support-bot: \"Let me pull the customer's recent transactions.\"")
    agent.act("GET", "/customers/123/transactions")

    print(" 🤖 support-bot: \"And check their account balance.\"")
    agent.act("GET", "/accounts/123/balance")

    print(f"\n {'→ Neither action matched a block rule, so both proceed.'}")


if __name__ == "__main__":
    run()
