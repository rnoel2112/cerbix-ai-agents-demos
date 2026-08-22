"""Scenario 3 — Cascade tiers: the same action, two departments, two outcomes.

Demonstrates the function (department) tier. A *function*-scoped rule blocks
wire transfers for Marketing, but a Finance agent — for whom the rule does not
apply — is allowed. Same action, different decision, driven by identity.
"""

from cerbix_client import ClientAgent, banner, rule


def run():
    banner(
        "Scenario 3 · Department cascade (function tier)",
        "Function rule: Marketing agents cannot wire money. Finance can.",
    )
    wire_rule = rule(
        "function", "tool", "BLOCK",
        "block execute wire transfer", department="marketing",
    )

    marketing = ClientAgent("marketing-bot", department="marketing", rules=[wire_rule])
    finance = ClientAgent("finance-bot", department="finance", rules=[wire_rule])

    print(" 🤖 marketing-bot (dept=marketing): \"Wire the vendor their bonus.\"")
    marketing.act("POST", "/execute_wire_transfer", body={"amount": 2000})

    print("\n 🤖 finance-bot (dept=finance): \"Process the approved vendor wire.\"")
    finance.act("POST", "/execute_wire_transfer", body={"amount": 2000})

    print("\n → One rule, evaluated against each agent's department. No per-agent config.")


if __name__ == "__main__":
    run()
