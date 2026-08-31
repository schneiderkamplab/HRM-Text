#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${DIEM_GENERATOR_BASE_URL:?Set DIEM_GENERATOR_BASE_URL to a Gemma 4 31B OpenAI-compatible endpoint}"
: "${DIEM_AUDIT_BASE_URL:?Set DIEM_AUDIT_BASE_URL to an independent E4B OpenAI-compatible endpoint}"

REQUESTS="data/dfm10_diem_modernization/requests.jsonl"
GENERATED="data/dfm10_diem_modernization/generated.jsonl"
AUDITED="data/dfm10_diem_modernization/audited.jsonl"
OUTPUT="data/converted_sources/diem_modernization/diem_modernization__accepted.jsonl"

echo "Generating faithful DiEm modernizations with Gemma 4 31B..."
python scripts/run_dfm10_dynaword_sft.py generate \
  --input "$REQUESTS" \
  --output "$GENERATED" \
  --base-url "$DIEM_GENERATOR_BASE_URL" \
  --model "${DIEM_GENERATOR_MODEL:-gemma-4-31b}" \
  --concurrency "${DIEM_GENERATOR_CONCURRENCY:-64}"

echo "Auditing DiEm modernizations with an independent E4B judge..."
python scripts/run_dfm10_dynaword_sft.py audit \
  --requests "$REQUESTS" \
  --generated "$GENERATED" \
  --output "$AUDITED" \
  --base-url "$DIEM_AUDIT_BASE_URL" \
  --model "${DIEM_AUDIT_MODEL:-gemma-4-e4b-diem-judge}" \
  --concurrency "${DIEM_AUDIT_CONCURRENCY:-64}"

echo "Building and sealing accepted DiEm modernization rows..."
mkdir -p "$(dirname "$OUTPUT")"
python scripts/run_dfm10_dynaword_sft.py build \
  --requests "$REQUESTS" \
  --generated "$GENERATED" \
  --audited "$AUDITED" \
  --output "$OUTPUT"
python scripts/validate_dfm10_diem_modernization.py
