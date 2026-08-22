"""Scenario 9 — Transaction amount limit (structured condition).

A finance control substring matching can't express: block wire transfers above
a threshold. The rule carries a numeric condition (amount > $10,000) evaluated
against the request's structured attributes.
"""

from cerbix_client import ClientAgent, banner, rule


def _cond_rule(text, conditions):
    r = rule("org", "tool", "BLOCK", text)
    r["conditions"] = conditions
    return r


def run():
    banner(
        "Scenario 9 · Transaction amount limit",
        "Org rule: block wire transfers over $10,000 (condition: amount > 10000).",
    )
    agent = ClientAgent(
        "payments-bot",
        rules=[_cond_rule("block large wire transfer",
                          [{"field": "amount", "op": "gt", "value": 10000}])],
    )

    print(" 💸 payments-bot: \"Wire $500 to the approved vendor.\"")
    agent.act("POST", "/execute_wire_transfer", attributes={"amount": 500})

    print("\n 💸 payments-bot: \"Now wire $50,000.\"")
    agent.act("POST", "/execute_wire_transfer", attributes={"amount": 50000})

    print("\n → Numeric thresholds are first-class — no keyword could express \"> $10k\".")


if __name__ == "__main__":
    run()
