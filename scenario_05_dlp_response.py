"""Scenario 5 — DLP on the way back: a model response leaking PII is blocked.

The data-exfiltration direction. A research agent asks a question and the model
returns a customer's SSN. With DLP in enforce mode, Cerbix blocks the response
so the sensitive data never reaches the calling application.
"""

from cerbix_client import ClientAgent, banner


def run():
    banner(
        "Scenario 5 · DLP — PII in an inbound response",
        "DLP enforce mode scans the model's response before your code sees it.",
    )
    agent = ClientAgent("research-bot", dlp=True)

    print(" 🤖 research-bot: \"What's on file for customer #123?\"")
    print("   (model responds…)")
    model_output = (
        "Customer #123 is Jane Doe, SSN 123-45-6789, card 4111111111111111. "
        "Account in good standing."
    )
    delivered = agent.receive(model_output)

    if delivered is None:
        print("\n → The leak was caught on the response path — the app got nothing sensitive.")


if __name__ == "__main__":
    run()
