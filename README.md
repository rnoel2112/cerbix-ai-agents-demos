# Cerbix demos — client-side AI agents

The **customer side** of the Cerbix story: real AI agents (first- and
third-party) that are *governed by* Cerbix. This is a **separate repo** — not
part of the Cerbix product. It depends on `cerbix-sdk` externally and talks to
the live Cerbix control / audit / proxy plane.

Everything runs against the live stack and the demo org **NewBank**
(`82b3fc8a-455d-48d3-85d7-815a4d16e497`):

- control — `https://agentgate-control-ykaskf6txa-uc.a.run.app`
- proxy — `https://agentgate-proxy-ykaskf6txa-uc.a.run.app`
- audit — `https://agentgate-audit-ykaskf6txa-uc.a.run.app`
- dashboard (product) — `https://cerbix-ai.web.app`

---

## The two modes (two separate apps)

Cerbix and the agent are **separate processes** — they never share code.

| Mode | Code in the agent | How Cerbix sees it | What happens |
|---|---|---|---|
| **Passive** (`passive_demo/`) | **none** | you point Cerbix at the agent's **log** | Cerbix reviews the log, **flags** would-be violations, registers a *discovered* agent. Nothing is blocked. |
| **Active** (`active_demo/`) | **one line** (register + token) | the agent's tool calls **route through the Cerbix proxy** | policy is **enforced at the proxy** — a blocked action comes back 403. The agent has no policy logic. |

Same policies, both modes — passive flags, active enforces.

### Passive — govern an agent without touching it

```bash
python passive_demo/newbank_bot.py "Wire $75,000 to Acme and pull customer C-1029"
#   a plain agent (zero Cerbix) runs and writes newbank_bot.log
python passive_demo/cerbix_scan.py
#   → Cerbix scans the log, flags the $75k wire + PII, registers a DISCOVERED agent
```

### Active — one line, enforced at the proxy

```bash
python active_demo/newbank_bot.py "Please wire $50,000 to Acme, and $400 to Beta Corp"
#   bot registers (ACTIVE agent) + gets a KMS token; tools go through the proxy
#   $50k → BLOCKED at the proxy (cascade: over limit);  $400 → allowed
```

Both show up in the product dashboard: passive as a **discovered** agent on the
Discovery page; active as an **active** agent, with the blocks in the Audit log.

---

## One-time setup

Assumes the `cerbix` repo is a **sibling** directory (`../cerbix`).

```bash
cd cerbix-demos
python3 -m venv .venv && source .venv/bin/activate
pip install -e ../cerbix/sdk           # cerbix-sdk (PyPI later)
pip install -r requirements.txt
pip install -r public_agents/sql_agent/requirements.txt   # SQL demo only

# LLM key (GCP Secret Manager → .env.local, never committed)
bash add_secret.sh demo-openai-api-key
bash load_secrets.sh
```

---

## The console (operator surface)

```bash
python console/server.py       # → http://localhost:8095
```

A page per agent: purpose, block diagram, source, start/stop, a live log with
the **firing policy highlighted**, an **Active/Passive** toggle, a **payload &
interception** panel, and the live **policy-violations** feed.

---

## More demos

**In-process SDK guard** (`newbank_agent.py`) — the same NewBank agent governed
in-process (the SDK path, vs. the proxy path in `active_demo/`):

```bash
python newbank_agent.py "Please wire $50,000 to Acme Supplies"   # ⛔ amount
python newbank_agent.py "Wire $2,000 to Aurora Holdings"         # ⛔ OFAC
python newbank_agent.py "Show the full account record for C-1029" # 🛡 PII redacted
python newbank_agent.py --runaway                                # anomaly → auto-suspend
python newbank_agent.py --passive "..."                          # observe & flag only
```

**Public third-party agents, before/after** (`public_agents/`):

```bash
cd public_agents/sql_agent && python build_db.py
python run.py --mode plain      # LangChain SQL agent leaks PII
python run.py --mode enforce    # cerbix.init() → exfiltration blocked
cd ../.. && python public_agents/babyagi/run.py --check   # runaway → auto-suspended
python public_agents/crewai/run.py --check                # PII + injection caught
```

**Original 13 scenarios** (no key, no infra): `python run_all.py`

**Seed a lived-in audit history** for the dashboard: `python seed_audit.py`
(`--clear` to remove).

---

## Notes

- **Requires the live Cerbix stack** and `cerbix-sdk` importable — installed
  editable from `../cerbix/sdk`; entry scripts fall back to the sibling checkout.
- **Safety:** the public-agent demos run third-party code. Vet it, use
  throwaway/test API keys, never wire real money or production credentials.
- **No secrets in git:** `.env.local` and `*.log` are gitignored; only synthetic
  PII appears in the demo data.
