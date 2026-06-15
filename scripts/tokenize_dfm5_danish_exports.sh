#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "scripts/tokenize_dfm5_danish_exports.sh is superseded by scripts/tokenize_dfm5_exports.sh" >&2
exec "${ROOT}/scripts/tokenize_dfm5_exports.sh"
