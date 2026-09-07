#!/usr/bin/env bash
# Upload every sample transcript to the API. Usage: scripts/seed.sh [API_URL]
set -euo pipefail
API_URL="${1:-http://localhost:8000}"
cd "$(dirname "$0")/.."
for f in fixtures/transcripts/*.txt; do
  printf '%s -> ' "$(basename "$f")"
  curl -sS -F "file=@$f" "$API_URL/meetings"
  echo
done
