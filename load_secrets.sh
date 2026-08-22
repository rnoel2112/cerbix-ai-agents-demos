#!/usr/bin/env bash
# Pull demo LLM keys from GCP Secret Manager into clientAI/.env.local (gitignored).
# The key values live only in Secret Manager and this local file — never in git.
#
#   bash clientAI/load_secrets.sh
#
# Add/rotate a key value (the value never leaves your machine):
#   read -rs KEY && printf %s "$KEY" | \
#     gcloud secrets versions add demo-openai-api-key --data-file=- --project=cerbix-ai
#   unset KEY
set -euo pipefail
cd "$(dirname "$0")"
PROJECT=cerbix-ai
ENV=.env.local
[ -f "$ENV" ] || cp .env.example "$ENV"

load() {
  local secret=$1 var=$2 val
  if val=$(gcloud secrets versions access latest --secret="$secret" \
             --project="$PROJECT" 2>/dev/null); then
    VAL="$val" VAR="$var" ENVF="$ENV" python3 - <<'PY'
import os
path, var, val = os.environ["ENVF"], os.environ["VAR"], os.environ["VAL"]
lines = open(path).read().splitlines()
found = False
for i, l in enumerate(lines):
    if l.startswith(var + "="):
        lines[i], found = f"{var}={val}", True
if not found:
    lines.append(f"{var}={val}")
open(path, "w").write("\n".join(lines) + "\n")
PY
    echo "  loaded $var  ← $secret"
  else
    echo "  $secret has no version yet — skipping $var"
  fi
}

echo "loading demo keys from Secret Manager ($PROJECT)…"
load demo-openai-api-key OPENAI_API_KEY
load demo-gemini-api-key GEMINI_API_KEY
echo "done — $ENV updated (gitignored)."
