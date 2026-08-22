# Cerbix demos — client-side AI agents

The **customer side** of the Cerbix story: real AI agents (first-party and
third-party) that are *governed by* Cerbix. This is intentionally a **separate
repo** — it is not part of the Cerbix product. It depends on `cerbix-sdk` as an
external package and talks to the live Cerbix control/audit plane.

## What's here

| Path | What |
|---|---|
| `newbank_agent.py` | Autonomous NewBank ops agent (gpt-4o function-calling), governed in-process by Cerbix; `--runaway` shows anomaly → auto-suspend |
| `public_agents/sql_agent/` | LangChain SQL agent — before/after (PII exfiltration blocked) |
| `public_agents/babyagi/` | BabyAGI-style loop — runaway → auto-suspended |
| `public_agents/crewai/` | CrewAI multi-agent — PII + injection caught |
| `console/` | Demo console — start/stop agents, live logs with the firing policy highlighted, live violations feed (`http://localhost:8095`) |
| `seed_audit.py` | Seed a lived-in audit history for the dashboard |
| `scenario_*.py`, `run_all.py` | The original 13 client-side scenario demos |
| `load_secrets.sh`, `add_secret.sh` | Pull demo LLM keys from GCP Secret Manager |

## Setup

Assumes the `cerbix` repo is a **sibling** directory (`../cerbix`).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ../cerbix/sdk        # cerbix-sdk (published to PyPI later)
pip install -r requirements.txt
cd public_agents/sql_agent && pip install -r requirements.txt && cd -   # for the SQL demo

# LLM key (stored in GCP Secret Manager, pulled into .env.local)
bash add_secret.sh demo-openai-api-key
bash load_secrets.sh
```

If the editable `cerbix-sdk` install can't be resolved, the entry scripts fall
back to importing from the sibling `../cerbix/sdk` automatically.

## Run

```bash
python console/server.py                       # → http://localhost:8095
python newbank_agent.py "Wire $50,000 to Acme Supplies"
python newbank_agent.py --runaway
python public_agents/sql_agent/run.py --mode enforce
```

The agents point at the live Cerbix stack:

- control — `https://agentgate-control-ykaskf6txa-uc.a.run.app`
- audit — `https://agentgate-audit-ykaskf6txa-uc.a.run.app`

The demo org is **NewBank** (`82b3fc8a-455d-48d3-85d7-815a4d16e497`).

## Safety

The public-agent demos run third-party code. Vet it, use throwaway/test API
keys, and never wire real money or production credentials.
