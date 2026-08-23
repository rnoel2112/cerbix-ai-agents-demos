# Testing the full loop — Passive & Active

End-to-end test of the Cerbix governance loop with the **AI Agents** console
(this repo) and the **Cerbix product dashboard**. Runs against the **live**
stack by default; a local option is at the bottom.

> Registration happens **only in Cerbix**. This console mimics a customer's
> client-side agents — it shows governance status and drives traffic, it never
> registers anything itself.

---

## Setup (once)

```bash
cd ~/Documents/GitHub/cerbix-ai-agents-demos
```
```bash
python3 -m venv .venv
```
```bash
source .venv/bin/activate
```
```bash
pip install -e ../cerbix/sdk
```
```bash
pip install -r requirements.txt
```
```bash
bash add_secret.sh demo-openai-api-key
```
```bash
bash load_secrets.sh
```
```bash
python console/server.py
```

Console → **http://localhost:8095**. Also sign in to the Cerbix dashboard →
**https://cerbix-ai.web.app** (Test Org). Keep both open side by side.

> Run one command per line — don't paste trailing `# comments` into zsh (it
> doesn't treat `#` as a comment by default).
>
> If you rename this repo folder, the venv breaks (venvs bake in absolute
> paths) — recreate it: `rm -rf .venv && python3 -m venv .venv && …`.

The demo agents register into the org you're viewing in Cerbix. Default is
**Test Org** (`71e5d8a7-d242-4e2f-a09b-4dd7f282da00`); override with
`CERBIX_ORG` for the console, or `CERBIX_ORG_ID` for the CLI scripts below.

---

## PASSIVE mode — govern an agent with no code in it

The story: an agent is already running; you point Cerbix at its log; Cerbix
discovers it and flags what it *would* have blocked. Nothing is enforced.

1. Run the plain agent (zero Cerbix code) — it writes a log:
   ```bash
   CERBIX_ORG_ID=71e5d8a7-d242-4e2f-a09b-4dd7f282da00 python passive_demo/newbank_bot.py "Wire $75,000 to Acme and pull the full record for customer C-1029"
   ```
2. Point Cerbix at the log (Cerbix reviews it — no agent code involved):
   ```bash
   CERBIX_ORG_ID=71e5d8a7-d242-4e2f-a09b-4dd7f282da00 python passive_demo/cerbix_scan.py
   ```
   → prints `scanned N · flagged M` and registers a **discovered** agent.
3. Observe in the Cerbix dashboard:
   - **Discovery** (or **Agents**) → a new **discovered** agent (`newbank-bot`).
   - Click it → its page shows the flagged activity (would-be blocks).
   - **Audit Log** → `shadow` findings + the discovery event.

✅ **Passive proven:** governed an agent without touching it; violations
flagged, nothing enforced.

---

## ACTIVE mode — registered in Cerbix, enforced at the data plane

The story: you deliberately register the agent in Cerbix, then its calls are
enforced.

4. Register in Cerbix (dashboard) → **Agents → Register Agent** → wizard:
   - Step 1 — Identity: **Name = `newbank-agent`** (this name links it to the
     console's NewBank page), owner, purpose.
   - Step 2 — Mode: **Active**.
   - Step 3 — it's registered **enforcing**; you get the integration snippet.
     (`agent.registered` lands in the Audit Log.)
5. Drive it from the AI Agents console → http://localhost:8095 → **NewBank**
   agent → the **Governed by Cerbix · Active** panel now shows. Click
   **Send a governed request**:
   - **List orders (benign)** → ✅ ALLOWED
   - **Export client PII** → ⛔ **BLOCKED — "GDPR Art.5 — block export of client PII"**
   - **Wire $250,000** → ✅ ALLOWED (frameworks don't cap amounts — that's a
     custom policy you can add)
6. Observe in the Cerbix dashboard:
   - **Agents → newbank-agent → its page**: stats (Total / Allowed / Blocked),
     the live audit table, and the violations feed with the GDPR block.
   - **Audit Log**: the `deny` on `/export_client_pii`, the `allow`s, and the
     `agent.registered` event.
   - **Policies**: the four frameworks enabled; GDPR shows "2 rules enforcing."

✅ **Active proven:** registered only through Cerbix, enforced live at the
proxy, fully audited, visible on the agent's own page.

---

## What the full loop proves

Passive (flag, no code) and Active (enforce, one registration) run the **same
frameworks** — passive flags, active blocks — with registration happening
**only in Cerbix** and every step in the audit trail.

---

## Run against a local Cerbix instead

Start the full local stack in the `../cerbix` repo, run the dashboard, and point
the console at localhost:

```bash
cd ../cerbix && bash scripts/local_firestore.sh
```
```bash
cd dashboard && npm run dev
```
```bash
cd ../../cerbix-ai-agents-demos && CERBIX_CONTROL_URL=http://localhost:8081 CERBIX_AUDIT_URL=http://localhost:8082 CERBIX_PROXY_URL=http://localhost:8080 python console/server.py
```

The dashboard is then at **http://localhost:3000**. See `../cerbix` README
("Quick Start — Run It Locally") for the two backend modes.
