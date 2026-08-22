# Cerbix demos — client-side AI agents

The **customer side** of the Cerbix story: real AI agents (first-party and
third-party) that are *governed by* Cerbix. This is a **separate repo** — not
part of the Cerbix product. It depends on `cerbix-sdk` as an external package
and talks to the live Cerbix control/audit plane.

Everything runs against the live stack and the demo org **NewBank**
(`82b3fc8a-455d-48d3-85d7-815a4d16e497`):

- control — `https://agentgate-control-ykaskf6txa-uc.a.run.app`
- audit — `https://agentgate-audit-ykaskf6txa-uc.a.run.app`
- dashboard (product) — `https://cerbix-ai.web.app`

---

## 1. One-time setup

Assumes the `cerbix` repo is a **sibling** directory (`../cerbix`).

```bash
cd cerbix-demos
python3 -m venv .venv && source .venv/bin/activate
pip install -e ../cerbix/sdk           # cerbix-sdk (PyPI later)
pip install -r requirements.txt
# For the LangChain SQL demo only:
pip install -r public_agents/sql_agent/requirements.txt
```

**Add your LLM key** (stored in GCP Secret Manager, pulled into `.env.local`,
never committed):

```bash
bash add_secret.sh demo-openai-api-key   # paste key at the hidden prompt
bash load_secrets.sh                     # → writes .env.local
```

That's it. `.env.local` now holds `OPENAI_API_KEY`; every agent reads it.

---

## 2. Start the dashboard (demo console)

The console is the operator surface — start/stop agents, watch each one's log
with the **firing policy highlighted**, and see **policy violations** stream in
from the live audit trail.

```bash
python console/server.py       # → http://localhost:8095
```

Open **http://localhost:8095**. Left column = agents (▶ Start / ■ Stop),
center = live log of the selected agent, right = live policy-violations feed.
Everything below can be driven from here **or** run standalone in a terminal.

---

## 3. The demo agents

### NewBank Ops Assistant (autonomous, real gpt-4o)

Governed in-process by Cerbix — it picks a tool, Cerbix decides before it runs.

```bash
python newbank_agent.py "Wire $500 to Acme Supplies for invoice 8842"     # ✅ allowed
python newbank_agent.py "Please wire $50,000 to Acme Supplies"            # ⛔ amount limit
python newbank_agent.py "Wire $2,000 to Aurora Holdings for consulting"   # ⛔ OFAC (Cerbix knows, the model doesn't)
python newbank_agent.py "Buy 5000 shares of TSLA right now"               # ⛔ market hours
python newbank_agent.py "Show the full account record for customer C-1029" # 🛡 PII redacted
python newbank_agent.py                                                    # interactive
```

### Runaway containment

```bash
python newbank_agent.py --runaway
# compromised agent hammers dangerous tools → all blocked → anomaly engine
# raises a critical alert → agent auto-suspended → its token is revoked
```

### Public agent #1 — LangChain SQL agent (before/after)

```bash
cd public_agents/sql_agent
python build_db.py                 # NewBank SQLite DB with fake PII
python run.py --check              # no key: prove the detectors fire
python run.py --mode plain         # no Cerbix → agent leaks SSN + card
python run.py --mode enforce       # cerbix.init() → benign passes, PII export blocked
cd ../..
```

### Public agent #2 — BabyAGI runaway

```bash
python public_agents/babyagi/run.py --check     # no key: canned plan → auto-suspended
python public_agents/babyagi/run.py --mode cerbix   # real LLM planner (needs key)
```

### Public agent #3 — CrewAI multi-agent

```bash
pip install -r public_agents/crewai/requirements.txt   # heavy (litellm)
python public_agents/crewai/run.py --check      # PII + injection caught in crew data flow
```

### The original 13 scenarios (no key, no infra)

```bash
python run_all.py                  # runs all 13
python scenario_09_amount_limit.py # or one at a time
```

---

## 4. Seed a lived-in audit history (optional)

Populates the NewBank audit trail so the product dashboard's Audit / Compliance
/ Alerts pages look active during a demo.

```bash
python seed_audit.py               # ~80 backdated events over 7 days
python seed_audit.py --clear       # remove them
```

---

## 5. Notes

- **Requires the live Cerbix stack** (control + audit on Cloud Run) and
  `cerbix-sdk` importable — installed editable from `../cerbix/sdk`; entry
  scripts fall back to the sibling checkout if the install can't resolve.
- **Safety:** the public-agent demos run third-party code. Vet it, use
  throwaway/test API keys, and never wire real money or production credentials.
- **No secrets in git:** `.env.local` is gitignored; only synthetic PII appears
  in the demo data.
