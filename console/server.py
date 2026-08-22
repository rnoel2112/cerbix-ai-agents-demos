#!/usr/bin/env python3
"""Cerbix demo console — start/stop the demo agents, watch logs + policy violations.

A small local control panel for the live demo. It spawns the demo agents as
subprocesses, streams their stdout, and shows policy violations pulled live from
the NewBank audit trail.

    python clientAI/console/server.py      # → http://localhost:8095
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
ORG = "82b3fc8a-455d-48d3-85d7-815a4d16e497"

# Load .env.local into the environment we hand to the agents.
_ENV = ROOT / ".env.local"
_AGENT_ENV = dict(os.environ)
if _ENV.exists():
    for line in _ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip():
                _AGENT_ENV.setdefault(k.strip(), v.strip())
# Dev fallback so agents import cerbix even without the editable install:
# point at the sibling cerbix checkout's sdk (cerbix-sdk is normally installed).
_AGENT_ENV["PYTHONPATH"] = str(ROOT.parent / "cerbix" / "sdk")
_AGENT_ENV["PYTHONUNBUFFERED"] = "1"

PY = str(ROOT / ".venv" / "bin" / "python")
if not Path(PY).exists():
    PY = "python3"


def _cmd(*parts):
    return [PY, str(ROOT / parts[0]), *parts[1:]]


# The catalogue of runnable agents.
AGENTS = {
    "newbank-wire": {
        "name": "NewBank agent · $50k wire",
        "desc": "Autonomous agent tries a large wire → blocked (amount)",
        "cmd": _cmd("newbank_agent.py", "Please wire $50,000 to Acme Supplies for invoice 8842")},
    "newbank-ofac": {
        "name": "NewBank agent · OFAC wire",
        "desc": "Wire to a sanctioned (but neutral-looking) counterparty → blocked",
        "cmd": _cmd("newbank_agent.py", "Wire $2,000 to Aurora Holdings for consulting services")},
    "newbank-pii": {
        "name": "NewBank agent · customer record",
        "desc": "Pull a customer record → PII redacted",
        "cmd": _cmd("newbank_agent.py",
                    "Look up the full account record for customer C-1029")},
    "newbank-runaway": {
        "name": "Runaway agent · containment",
        "desc": "Compromised agent hammers dangerous tools → auto-suspended",
        "cmd": _cmd("newbank_agent.py", "--runaway")},
    "sql-plain": {
        "name": "LangChain SQL agent · PLAIN",
        "desc": "Third-party agent, no Cerbix → leaks customer PII",
        "cmd": _cmd("public_agents/sql_agent/run.py", "--mode", "plain")},
    "sql-enforce": {
        "name": "LangChain SQL agent · CERBIX",
        "desc": "Same agent + cerbix.init() → PII exfiltration blocked",
        "cmd": _cmd("public_agents/sql_agent/run.py", "--mode", "enforce")},
    "babyagi": {
        "name": "BabyAGI · runaway",
        "desc": "Autonomous loop → anomaly → auto-suspended",
        "cmd": _cmd("public_agents/babyagi/run.py", "--check")},
    "crewai": {
        "name": "CrewAI · multi-agent",
        "desc": "Crew data flow → PII + injection caught (detection self-check)",
        "cmd": _cmd("public_agents/crewai/run.py", "--check")},
}

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class Run:
    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.lines: deque[str] = deque(maxlen=500)
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


RUNS: dict[str, Run] = {k: Run() for k in AGENTS}

app = FastAPI(title="Cerbix demo console")


@app.get("/")
def index():
    return FileResponse(HERE / "index.html")


@app.get("/api/agents")
def agents():
    return {k: {"name": v["name"], "desc": v["desc"], "status": RUNS[k].status}
            for k, v in AGENTS.items()}


@app.post("/api/start/{agent_id}")
def start(agent_id: str):
    if agent_id not in AGENTS:
        return JSONResponse({"error": "unknown agent"}, status_code=404)
    RUNS[agent_id].start(AGENTS[agent_id]["cmd"])
    return {"status": RUNS[agent_id].status}


@app.post("/api/stop/{agent_id}")
def stop(agent_id: str):
    if agent_id not in AGENTS:
        return JSONResponse({"error": "unknown agent"}, status_code=404)
    RUNS[agent_id].stop()
    return {"status": RUNS[agent_id].status}


@app.get("/api/logs/{agent_id}")
def logs(agent_id: str):
    r = RUNS.get(agent_id)
    if not r:
        return JSONResponse({"error": "unknown agent"}, status_code=404)
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
    """Recent policy violations from the live NewBank audit trail."""
    try:
        r = httpx.get(f"{AUDIT}/orgs/{ORG}/events", params={"limit": 60}, timeout=25)
        evs = r.json().get("data", [])
    except Exception:
        return {"violations": []}
    out = []
    for e in evs:
        dec = str(e.get("decision", "")).lower()
        if dec in ("allow", ""):
            continue
        out.append({
            "agent": _name(e.get("agent_id", "")),
            "action": e.get("action", ""),
            "resource": e.get("resource", ""),
            "decision": e.get("decision", ""),
            "ts": str(e.get("timestamp", ""))[:19]})
    return {"violations": out[:25]}


if __name__ == "__main__":
    import uvicorn
    print("Cerbix demo console → http://localhost:8095")
    uvicorn.run(app, host="127.0.0.1", port=8095, log_level="warning")
