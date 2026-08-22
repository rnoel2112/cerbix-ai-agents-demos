#!/usr/bin/env python3
"""Cerbix demo console — a page per agent: purpose, build, block diagram, code,
start/stop, live logs with the firing policy highlighted, and a violations feed.

    python console/server.py      # → http://localhost:8095
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

ROOT = Path(__file__).parents[1]           # cerbix-demos repo root
HERE = Path(__file__).parent
AUDIT = "https://agentgate-audit-ykaskf6txa-uc.a.run.app"
CONTROL = "https://agentgate-control-ykaskf6txa-uc.a.run.app"
PROXY = "https://agentgate-proxy-ykaskf6txa-uc.a.run.app"
# Register the demo agents into the org the operator is viewing in the Cerbix
# product dashboard, so the governance shows up where they're logged in.
# Default: Test Org (override with CERBIX_ORG).
ORG = os.environ.get("CERBIX_ORG", "71e5d8a7-d242-4e2f-a09b-4dd7f282da00")
# The Cerbix product dashboard — deep-linked from each governed agent.
CERBIX_APP = os.environ.get("CERBIX_APP", "https://cerbix-ai.web.app")

_ENV = ROOT / ".env.local"
_AGENT_ENV = dict(os.environ)
if _ENV.exists():
    for line in _ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip():
                _AGENT_ENV.setdefault(k.strip(), v.strip())
_AGENT_ENV["PYTHONPATH"] = str(ROOT.parent / "cerbix" / "sdk")
_AGENT_ENV["PYTHONUNBUFFERED"] = "1"
# Bot scripts register into the same org the console governs.
_AGENT_ENV["CERBIX_ORG_ID"] = ORG

PY = str(ROOT / ".venv" / "bin" / "python")
if not Path(PY).exists():
    PY = "python3"


def _c(*parts):
    return [PY, str(ROOT / parts[0]), *parts[1:]]


# ── The agent catalogue: one entry per agent (each its own page) ──
AGENTS = {
    "newbank": {
        "name": "NewBank Ops Assistant",
        "tag": "first-party · autonomous",
        "passive_flag": "--passive",   # supports passive (observe) vs active (enforce)
        "purpose": (
            "An autonomous operations agent for a bank. An operator asks for "
            "something in plain English; the agent decides which tool to call "
            "(wire, trade, customer lookup). Cerbix governs every action before "
            "it runs — so the agent can reason freely but can't act outside policy."),
        "how": (
            "Real gpt-4o with function-calling picks the tool. Each tool handler "
            "calls the Cerbix guard — policy_sync.decide() — which evaluates the "
            "org→function→agent cascade with structured conditions IN-PROCESS, "
            "against policies synced live from the control plane. Allow → the "
            "tool runs; block → the tool returns a denial the LLM explains; "
            "redact → PII is masked. Every decision is logged to the audit trail."),
        "code": ["newbank_agent.py"],
        "flow": [
            {"t": "Operator task (English)", "k": "in"},
            {"t": "gpt-4o · function-calling picks a tool", "k": "agent"},
            {"t": "Cerbix guard · decide() in-process", "k": "cerbix"},
            {"t": "allow · block · redact", "k": "decision"},
            {"t": "tool executes / refused → agent explains", "k": "exec"},
            {"t": "audit trail", "k": "audit"},
        ],
        "actions": {
            "small": {"label": "$500 wire (allowed)",
                      "cmd": _c("newbank_agent.py", "Wire $500 to Acme Supplies for invoice 8842")},
            "wire": {"label": "$50k wire (blocked · amount)",
                     "cmd": _c("newbank_agent.py",
                               "Please wire $50,000 to Acme Supplies for invoice 8842")},
            "ofac": {"label": "OFAC wire (blocked · sanctions)",
                     "cmd": _c("newbank_agent.py",
                               "Wire $2,000 to Aurora Holdings for consulting services")},
            "pii": {"label": "Customer record (PII redacted)",
                    "cmd": _c("newbank_agent.py",
                              "Look up the full account record for customer C-1029")},
            "runaway": {"label": "Runaway → auto-suspended",
                        "cmd": _c("newbank_agent.py", "--runaway")},
        },
    },
    "twoapp": {
        "name": "NewBank bot — two-app (passive & active)",
        "tag": "production model · separate processes",
        "purpose": (
            "The production model: Cerbix and the agent are separate processes "
            "that share no code. Passive = point Cerbix at the agent's log (no "
            "code in the app). Active = one-line register + route tool calls "
            "through the Cerbix proxy, enforced at the data plane."),
        "how": (
            "Passive runs a zero-Cerbix bot that writes an action log, then the "
            "scanner posts it to the control-plane /scan endpoint — Cerbix "
            "registers a discovered agent and flags would-be violations. Active "
            "registers the agent, gets a KMS-signed token, and routes tool calls "
            "through the live proxy, which enforces OPA + the policy cascade "
            "before the action reaches the bank. Same policies; passive flags, "
            "active blocks."),
        "code": ["passive_demo/newbank_bot.py", "passive_demo/cerbix_scan.py",
                 "active_demo/newbank_bot.py"],
        "flow": [
            {"t": "Agent runs (separate process)", "k": "agent"},
            {"t": "passive: writes log  ·  active: tools via proxy", "k": "in"},
            {"t": "Cerbix: /scan (flag)  ·  proxy (enforce)", "k": "cerbix"},
            {"t": "discovered + flagged  ·  blocked / allowed", "k": "decision"},
            {"t": "shows in the product dashboard", "k": "audit"},
        ],
        "actions": {
            "passive_run": {"label": "Passive · run bot (writes log, no Cerbix)",
                            "cmd": _c("passive_demo/newbank_bot.py",
                                      "Wire $75,000 to Acme Supplies and pull the full record for customer C-1029")},
            "passive_scan": {"label": "Passive · scan log → flag (discovered)",
                             "cmd": _c("passive_demo/cerbix_scan.py")},
            "active": {"label": "Active · $50k + $400 wire (proxy-enforced)",
                       "cmd": _c("active_demo/newbank_bot.py",
                                 "Please wire $50,000 to Acme Supplies, and also send $400 to Beta Corp")},
        },
    },
    "sql": {
        "name": "LangChain SQL Agent",
        "tag": "third-party · unmodified",
        "purpose": (
            "A real, off-the-shelf LangChain SQL agent pointed at a bank "
            "database. It answers questions by writing and running SQL — which "
            "means it can also be asked to dump every customer's SSN and card. "
            "The demo shows the same agent with and without Cerbix."),
        "how": (
            "langchain's own create_sql_agent + ChatOpenAI, unmodified. Adding "
            "cerbix.init() (two lines, zero agent changes) turns on the DLP + PIP "
            "scanners, which intercept the agent's LLM traffic. A benign query "
            "passes; a request that would exfiltrate PII is blocked before it "
            "leaves the process."),
        "code": ["public_agents/sql_agent/run.py", "public_agents/sql_agent/build_db.py"],
        "flow": [
            {"t": "User question", "k": "in"},
            {"t": "LangChain SQL agent → SQL → answer", "k": "agent"},
            {"t": "cerbix.init() intercepts the LLM traffic", "k": "cerbix"},
            {"t": "DLP scans prompt + response for PII", "k": "decision"},
            {"t": "answer returned / PII exfiltration blocked", "k": "exec"},
        ],
        "actions": {
            "check": {"label": "Detection self-check (no key)",
                      "cmd": _c("public_agents/sql_agent/run.py", "--check")},
            "plain": {"label": "PLAIN — leaks PII",
                      "cmd": _c("public_agents/sql_agent/run.py", "--mode", "plain")},
            "enforce": {"label": "CERBIX — exfiltration blocked",
                        "cmd": _c("public_agents/sql_agent/run.py", "--mode", "enforce")},
        },
    },
    "babyagi": {
        "name": "BabyAGI",
        "tag": "third-party · autonomous loop",
        "purpose": (
            "The classic autonomous task loop: given an objective, it plans an "
            "action, does it, and plans the next — with no stopping condition. "
            "Point it at an aggressive objective and it spirals into unbounded "
            "high-risk actions. The demo shows Cerbix bounding that runaway."),
        "how": (
            "A BabyAGI-style loop on the current openai SDK (so Cerbix "
            "intercepts it). Each planned action is checked by the Cerbix guard; "
            "blocked actions accumulate in the audit trail until the anomaly "
            "engine raises a critical alert and auto-suspends the agent."),
        "code": ["public_agents/babyagi/run.py"],
        "flow": [
            {"t": "Aggressive objective", "k": "in"},
            {"t": "loop · LLM plans the next action", "k": "agent"},
            {"t": "Cerbix guard per action", "k": "cerbix"},
            {"t": "blocked actions accumulate", "k": "decision"},
            {"t": "anomaly engine → auto-suspend", "k": "audit"},
        ],
        "actions": {
            "check": {"label": "Runaway → auto-suspended (no key)",
                      "cmd": _c("public_agents/babyagi/run.py", "--check")},
            "cerbix": {"label": "Real LLM planner (needs key)",
                       "cmd": _c("public_agents/babyagi/run.py", "--mode", "cerbix")},
        },
    },
    "crewai": {
        "name": "CrewAI Crew",
        "tag": "third-party · multi-agent",
        "purpose": (
            "A crew of collaborating agents (researcher → writer) handling a "
            "memo that contains PII and a hidden prompt injection. Multi-agent "
            "systems pass sensitive data freely between members; the demo shows "
            "one cerbix.init() governing the whole crew."),
        "how": (
            "CrewAI (litellm/openai under the hood). One cerbix.init() covers "
            "every agent in the crew: PIP flags the injected instruction and DLP "
            "redacts the PII as it flows between members — no per-agent wiring."),
        "code": ["public_agents/crewai/run.py"],
        "flow": [
            {"t": "Task + research material (with PII + injection)", "k": "in"},
            {"t": "Crew · researcher → writer", "k": "agent"},
            {"t": "cerbix.init() governs every member", "k": "cerbix"},
            {"t": "PIP flags injection · DLP redacts PII", "k": "decision"},
            {"t": "clean report / leak blocked", "k": "exec"},
        ],
        "actions": {
            "check": {"label": "Detection self-check (no key)",
                      "cmd": _c("public_agents/crewai/run.py", "--check")},
        },
    },
}

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class Run:
    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.lines: deque[str] = deque(maxlen=600)
        self.status = "idle"

    def start(self, cmd):
        if self.proc and self.proc.poll() is None:
            return
        self.lines.clear()
        self.status = "running"
        self.proc = subprocess.Popen(
            cmd, cwd=str(ROOT), env=_AGENT_ENV,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            self.lines.append(_ANSI.sub("", line.rstrip("\n")))
        self.status = "done"

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.status = "stopped"


RUNS: dict[str, Run] = {}


def _run(agent, action, passive=False):
    return RUNS.setdefault(f"{agent}.{action}.{'p' if passive else 'a'}", Run())


app = FastAPI(title="Cerbix demo console")


@app.get("/")
def index():
    return FileResponse(HERE / "index.html")


@app.get("/api/agents")
def agents():
    return [{"id": k, "name": v["name"], "tag": v["tag"],
             "purpose": v["purpose"], "actions": len(v["actions"])}
            for k, v in AGENTS.items()]


@app.get("/api/agent/{aid}")
def agent(aid: str, passive: bool = False):
    a = AGENTS.get(aid)
    if not a:
        return JSONResponse({"error": "unknown"}, status_code=404)
    return {"id": aid, "name": a["name"], "tag": a["tag"],
            "purpose": a["purpose"], "how": a["how"], "flow": a["flow"],
            "code": a["code"], "passive": bool(a.get("passive_flag")),
            "actions": [{"id": k, "label": v["label"],
                         "status": _run(aid, k, passive).status}
                        for k, v in a["actions"].items()]}


@app.get("/api/agent/{aid}/code")
def code(aid: str):
    a = AGENTS.get(aid)
    if not a:
        return JSONResponse({"error": "unknown"}, status_code=404)
    files = []
    for rel in a["code"]:
        p = ROOT / rel
        files.append({"path": rel,
                      "text": p.read_text() if p.exists() else "(missing)"})
    return {"files": files}


@app.post("/api/run/{aid}/{action}")
def start(aid: str, action: str, passive: bool = False):
    if aid not in AGENTS or action not in AGENTS[aid]["actions"]:
        return JSONResponse({"error": "unknown"}, status_code=404)
    cmd = list(AGENTS[aid]["actions"][action]["cmd"])
    flag = AGENTS[aid].get("passive_flag")
    if passive and flag:
        cmd.append(flag)
    r = _run(aid, action, passive)
    r.start(cmd)
    return {"status": r.status}


@app.post("/api/stop/{aid}/{action}")
def stop(aid: str, action: str, passive: bool = False):
    _run(aid, action, passive).stop()
    return {"status": _run(aid, action, passive).status}


@app.get("/api/logs/{aid}/{action}")
def logs(aid: str, action: str, passive: bool = False):
    r = _run(aid, action, passive)
    return {"status": r.status, "lines": list(r.lines)}


_agent_names: dict[str, str] = {}
_names_ts = 0.0


def _name(aid: str) -> str:
    global _names_ts
    if time.time() - _names_ts > 60:
        try:
            r = httpx.get(f"{CONTROL}/orgs/{ORG}/agents", timeout=8)
            for a in r.json().get("data", []):
                _agent_names[a["id"]] = a.get("name", a["id"][:8])
            _names_ts = time.time()
        except Exception:
            pass
    return _agent_names.get(aid, aid[:8])


@app.get("/api/violations")
def violations():
    try:
        r = httpx.get(f"{AUDIT}/orgs/{ORG}/events", params={"limit": 60}, timeout=25)
        evs = r.json().get("data", [])
    except Exception:
        return {"violations": []}
    out = []
    for e in evs:
        if str(e.get("decision", "")).lower() in ("allow", ""):
            continue
        out.append({"agent": _name(e.get("agent_id", "")),
                    "action": e.get("action", ""), "resource": e.get("resource", ""),
                    "decision": e.get("decision", ""),
                    "ts": str(e.get("timestamp", ""))[:19]})
    return {"violations": out[:25]}


# ── Register in Cerbix — the bridge to the product dashboard ──────────
# From this AI-Agents console the operator registers a client-side agent into
# Cerbix (active or passive), then drives governed requests through the proxy.
# The same agent + its enforcement then appear on the Cerbix product dashboard.

REG: dict[str, dict] = {}  # aid -> {agent_id, token, mode, url}

# Preset governed calls to demonstrate enforcement at the proxy.
_GOVERNED_CALLS = {
    "benign": {"resource": "get_orders", "payload": {"limit": 5},
               "label": "List recent orders (benign)"},
    "pii": {"resource": "export_client_pii", "payload": {"customer": "C-1029"},
            "label": "Export client PII (should be blocked)"},
    "wire": {"resource": "execute_wire_transfer",
             "payload": {"amount": 250000, "counterparty": "Acme"},
             "label": "Wire $250,000 (high-risk)"},
}


@app.get("/api/cerbix/reg/{aid}")
def cerbix_reg(aid: str):
    r = REG.get(aid)
    if not r:
        return {"registered": False}
    return {"registered": True, **r}


@app.post("/api/cerbix/register/{aid}")
def cerbix_register(aid: str, mode: str = "active"):
    a = AGENTS.get(aid)
    if not a:
        return JSONResponse({"error": "unknown"}, status_code=404)
    name = f"{aid}-agent"
    if mode == "passive":
        # Discover via a log scan — no code in the agent.
        events = [
            {"action": "POST", "resource": "export_client_pii",
             "attributes": {}, "response_body": ""},
            {"action": "POST", "resource": "get_orders", "attributes": {}},
        ]
        try:
            r = httpx.post(f"{CONTROL}/orgs/{ORG}/scan", timeout=30, json={
                "agent_name": name, "framework": aid,
                "department": "operations", "events": events})
            data = r.json().get("data", {})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=502)
        agent_id = data.get("agent_id", "")
        REG[aid] = {"agent_id": agent_id, "token": "", "mode": "passive",
                    "url": f"{CERBIX_APP}/agents/{agent_id}"}
        return {"registered": True, **REG[aid], "scan": data}

    # Active — provision + KMS token; tool calls will route through the proxy.
    try:
        r = httpx.post(f"{CONTROL}/orgs/{ORG}/provision", timeout=30, json={
            "name": name, "owner": "ops@newbank.example",
            "purpose": a["purpose"][:180], "framework": aid, "scopes": ["*"]})
        d = r.json().get("data", {})
        agent_id = d["agent"]["id"]
        token = d["token"]["access_token"]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    # Mark it Active (enforced) so the product page shows it enforcing.
    try:
        httpx.patch(f"{CONTROL}/orgs/{ORG}/agents/{agent_id}/governance",
                    timeout=15, json={"state": "enforced"})
    except Exception:
        pass
    REG[aid] = {"agent_id": agent_id, "token": token, "mode": "active",
                "url": f"{CERBIX_APP}/agents/{agent_id}"}
    return {"registered": True, **REG[aid]}


@app.post("/api/cerbix/call/{aid}")
def cerbix_call(aid: str, kind: str = "benign"):
    """Route a governed request through the Cerbix proxy with the agent's token."""
    reg = REG.get(aid)
    if not reg or reg["mode"] != "active" or not reg["token"]:
        return JSONResponse(
            {"error": "Register this agent as Active first."}, status_code=400)
    call = _GOVERNED_CALLS.get(kind, _GOVERNED_CALLS["benign"])
    try:
        r = httpx.post(f"{PROXY}/api/{call['resource']}", timeout=30,
                       headers={"Authorization": f"Bearer {reg['token']}"},
                       json=call["payload"])
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    allowed = r.status_code < 400
    reason = ""
    if not allowed:
        try:
            reason = r.json().get("error", "")
        except Exception:
            reason = f"HTTP {r.status_code}"
    return {"label": call["label"], "resource": call["resource"],
            "allowed": allowed, "status": r.status_code, "reason": reason}


if __name__ == "__main__":
    import uvicorn
    print("Cerbix demo console → http://localhost:8095")
    uvicorn.run(app, host="127.0.0.1", port=8095, log_level="warning")
