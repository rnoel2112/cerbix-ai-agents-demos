# Public agents — before / after Cerbix

Take a **real, publicly available AI agent, unmodified**, run it, and show the
difference Cerbix makes with a two-line `cerbix.init()` and zero changes to the
agent's code.

The pattern for each agent is three passes:

| Pass | What happens |
|---|---|
| **plain** | the agent misbehaves (leaks PII, obeys an injection, spirals) |
| **shadow** | `cerbix.init()` observes only — produces a risk report, blocks nothing |
| **enforce** | same agent, one flag — Cerbix blocks the injection / redacts the leak / suspends the runaway |

Cerbix intercepts the agent's LLM calls (openai / anthropic / google-genai /
langchain), so **prompt injection (PIP)** and **PII in prompts or responses
(DLP)** are caught automatically. Governing the agent's *actions* (a SQL query,
a shell command) is a hard block when routed through the Cerbix proxy.

## Safety

These run third-party code. Vet it, run sandboxed, use throwaway/test API keys,
and never wire real money or production credentials.

## Modules

| Dir | Agent | Weakness shown | Cerbix capability |
|---|---|---|---|
| `sql_agent/` | LangChain `create_sql_agent` | injection → PII exfiltration / destructive SQL | PIP + DLP (auto), proxy (tool block) |
| `babyagi/` | BabyAGI task loop | unbounded autonomous spiral | runaway anomaly → auto-suspend |
| `crewai/` | CrewAI crew | unscoped delegation, compromised member | delegation governance + PIP/DLP |

## Run (sql_agent)

```bash
cd clientAI/public_agents/sql_agent
pip install -r requirements.txt
python build_db.py                 # NewBank DB with fake PII
python run.py --check              # no key: prove Cerbix detection fires
python run.py --mode plain         # agent leaks PII on injection
python run.py --mode shadow        # cerbix observes + reports
python run.py --mode enforce       # cerbix blocks the exfiltration
```

The live agent modes need an `OPENAI_API_KEY` in `clientAI/.env.local`.
`--check` needs no key and validates the PIP + DLP detectors directly.
