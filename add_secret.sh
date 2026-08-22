#!/usr/bin/env bash
# Add a key value to a GCP Secret Manager secret — paste-safe, no history, no
# trailing newline. The value goes straight from this prompt to Secret Manager.
#
#   bash clientAI/add_secret.sh demo-openai-api-key
#   bash clientAI/add_secret.sh demo-gemini-api-key
set -euo pipefail
secret="${1:?usage: bash add_secret.sh <secret-name>}"
project="${2:-cerbix-ai}"

printf 'Paste the key for %s (input hidden), then press Enter: ' "$secret" >&2
IFS= read -rs KEY
printf '\n' >&2
[ -n "$KEY" ] || { echo "no input — aborted" >&2; exit 1; }

printf %s "$KEY" | gcloud secrets versions add "$secret" \
  --data-file=- --project="$project" >/dev/null
unset KEY
echo "✓ added a new version to $secret" >&2
