"""Scenario 10 — OFAC / sanctions counterparty screening (list condition).

Block any payment whose counterparty appears on a sanctions list. The OFAC list
ships with the policy bundle; the rule's condition checks list membership.
"""

from cerbix_client import ClientAgent, banner, rule

# A named list shipped with the policy bundle (centrally managed in prod).
OFAC = {"ofac": ["SANCTIONED HOLDINGS LTD", "EVILCORP", "BLOCKED BANK SA"]}


def _cond_rule(text, conditions):
    r = rule("org", "tool", "BLOCK", text)
    r["conditions"] = conditions
    return r


def run():
    banner(
        "Scenario 10 · OFAC / sanctions screening",
        "Org rule: block payments to sanctioned counterparties (condition: in_list ofac).",
    )
    agent = ClientAgent(
        "payments-bot",
        lists=OFAC,
        rules=[_cond_rule(
            "block wire transfer to sanctioned counterparty",
            [{"field": "counterparty", "op": "in_list", "value": "ofac"}],
        )],
    )

    print(" 🛂 payments-bot: \"Pay TRUSTED VENDOR INC.\"")
    agent.act("POST", "/execute_wire_transfer",
              attributes={"counterparty": "TRUSTED VENDOR INC"})

    print("\n 🛂 payments-bot: \"Pay EVILCORP.\"")
    agent.act("POST", "/execute_wire_transfer",
              attributes={"counterparty": "EVILCORP"})

    print("\n → List membership (OFAC, denylists) is enforced in-line, on every payment.")


if __name__ == "__main__":
    run()
