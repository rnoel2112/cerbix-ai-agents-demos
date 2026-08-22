"""Scenario 11 — Market-hours restriction (time-window condition).

Trading agents may only act during market hours (09:00–16:00). The rule's
condition checks the request hour against a window.
"""

from cerbix_client import ClientAgent, banner, rule


def _cond_rule(text, conditions):
    r = rule("org", "tool", "BLOCK", text)
    r["conditions"] = conditions
    return r


def run():
    banner(
        "Scenario 11 · Market-hours restriction",
        "Org rule: no trades outside 09:00–16:00 (condition: hour not_between [9,16]).",
    )
    agent = ClientAgent(
        "trading-bot",
        rules=[_cond_rule("block trade outside market hours",
                          [{"field": "hour", "op": "not_between", "value": [9, 16]}])],
    )

    print(" 🕒 trading-bot at 11:00: \"Execute the buy order.\"")
    agent.act("POST", "/execute_trade", attributes={"hour": 11})

    print("\n 🕒 trading-bot at 22:00: \"Execute the buy order.\"")
    agent.act("POST", "/execute_trade", attributes={"hour": 22})

    print("\n → Time windows are enforceable — off-hours trading is blocked.")
    print("   (The transport supplies `hour`; the rule decides.)")


if __name__ == "__main__":
    run()
