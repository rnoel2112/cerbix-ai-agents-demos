"""Scenario 4 — DLP on the way out: a secret in the prompt is blocked.

An agent tries to paste a live credential into an LLM prompt. With DLP in
enforce mode, Cerbix blocks the request before it leaves the process — the
secret never reaches the model provider.
"""

from cerbix_client import ClientAgent, banner


def run():
    banner(
        "Scenario 4 · DLP — secret in an outbound prompt",
        "DLP enforce mode scans the request body for secrets/PII.",
    )
    agent = ClientAgent("devops-bot", dlp=True)

    leaky_prompt = (
        "Summarize this config for me: "
        "aws_secret_access_key=AKIAIOSFODNN7EXAMPLE "
        "and database_url=postgres://admin:p4ssw0rd@db.internal:5432/prod"
    )
    print(" 🤖 devops-bot: \"Let me ask the LLM to summarize our prod config…\"")
    agent.act("POST", "https://api.openai.com/v1/chat/completions", body=leaky_prompt)

    print("\n → The credential never left the machine.")


if __name__ == "__main__":
    run()
