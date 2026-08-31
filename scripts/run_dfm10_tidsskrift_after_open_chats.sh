#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OPEN_LOCK="$ROOT/data/dfm10_open_grounded_chats/campaign.lock"
mkdir -p "$(dirname "$OPEN_LOCK")"

echo "$(date -Is) waiting for the Wikipedia/OpenStax grounded-chat campaign"
exec 8>"$OPEN_LOCK"
flock 8
flock -u 8

echo "$(date -Is) Wikipedia/OpenStax campaign released; starting Tidsskrift"
exec bash scripts/run_dfm10_tidsskrift_grounded_8gpu.sh
