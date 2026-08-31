#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TOKENIZER_PATH="${TOKENIZER_PATH:-../brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"
TOKENIZER_WORKERS="${TOKENIZER_WORKERS:-16}"
FOLKETING_ARCHIVE="${FOLKETING_ARCHIVE:-data/downloads/datasets/folketingets_dokumenter_14004/14004.zip}"

if [[ ! -s "$FOLKETING_ARCHIVE" ]]; then
  echo "Downloading Rigsarkivet Folketinget handover 14004..."
  mkdir -p "$(dirname "$FOLKETING_ARCHIVE")"
  curl -L --fail --retry 5 --retry-delay 5 --continue-at - \
    https://digidata.rigsarkivet.dk/download/14004 \
    -o "$FOLKETING_ARCHIVE"
fi

echo "Validating Andersen train/validation partition..."
python scripts/prepare_dfm10_andersen.py --force

echo "Downloading approved Bornholmsk and DiEm research sources..."
python scripts/download_training_datasets.py \
  --download \
  --groups dfm10 \
  --only dfm10_bornholmsk_parallel,ra_diem_htr,dfm10_danish_book_ads,dfm10_elrc_medical,dfm10_emea_medical,dfm10_ecdc_medical,dfm10_nhs_synthetic_clinical_notes

echo "Preparing pinned, license-clear medical supervision..."
python scripts/prepare_dfm10_medical.py --force
python scripts/prepare_dfm10_emea.py --force
python scripts/prepare_dfm10_ecdc.py --force
python scripts/tokenize_chat_template.py \
  data/converted_sources/dfm10_medical \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_medical \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Preparing pinned MedQuAD translation requests..."
python scripts/prepare_dfm10_medquad_da.py prepare --shards 8
if [[ ! -s data/dfm10_medquad_sources/manifest.json ]]; then
  echo "MedQuAD Danish translation/audit is incomplete. Run:" >&2
  echo "  setsid bash scripts/run_dfm10_medquad_da_8gpu.sh > logs/dfm10_medquad_da_runner.log 2>&1 &" >&2
  exit 2
fi
python scripts/tokenize_chat_template.py \
  data/dfm10_medquad_sources \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_medquad \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Preparing bidirectional Bornholmsk/standard-Danish translation tasks..."
python scripts/prepare_dfm10_bornholmsk_parallel.py --force

echo "Preparing grounded COR.SEM lexical-semantic tasks..."
python scripts/prepare_dfm10_cor_sem.py --force

echo "Preparing checked, source-grounded Danish book-ad tasks..."
python scripts/prepare_dfm10_danish_book_ads.py --force

SKS_ROOT="data/downloads/datasets/kb_dk_sks_tei"
SKS_REVISION="27a6b110c24e97b381e010595b50f3ca3d4ca8c9"
if [[ ! -d "$SKS_ROOT/.git" ]]; then
  git clone https://github.com/kb-dk/SKS_tei.git "$SKS_ROOT"
fi
git -C "$SKS_ROOT" fetch --quiet origin "$SKS_REVISION"
git -C "$SKS_ROOT" checkout --quiet --detach "$SKS_REVISION"
echo "Preparing source-grounded SKS editorial-commentary tasks..."
python scripts/prepare_dfm10_sks_tei.py --force

echo "Preparing DiEm historical-modernization requests..."
python scripts/prepare_dfm10_diem_modernization.py --force
DIEM_OUTPUT="data/converted_sources/diem_modernization/diem_modernization__accepted.jsonl"
DIEM_GATE="data/converted_sources/diem_modernization/production_gate.json"
if [[ ! -s "$DIEM_OUTPUT" || ! -s "$DIEM_GATE" ]]; then
  echo "DiEm modernization has not passed generation and audit." >&2
  echo "Start independent Gemma 4 31B and E4B endpoints, then run:" >&2
  echo "  DIEM_GENERATOR_BASE_URL=... DIEM_AUDIT_BASE_URL=... scripts/finish_dfm10_diem_modernization.sh" >&2
  exit 2
fi
python scripts/validate_dfm10_diem_modernization.py

echo "Preparing explicitly licensed DSL Danish lexical supervision..."
SENTIMENT_REPO="data/downloads/datasets/dsldk_danish_sentiment_lexicon"
FRAMENET_REPO="data/downloads/datasets/dsldk_dansk_frame_net"
if [[ ! -d "$SENTIMENT_REPO/.git" ]]; then
  git clone https://github.com/dsldk/danish-sentiment-lexicon.git "$SENTIMENT_REPO"
fi
if [[ ! -d "$FRAMENET_REPO/.git" ]]; then
  git clone https://github.com/dsldk/dansk-frame-net.git "$FRAMENET_REPO"
fi
git -C "$SENTIMENT_REPO" checkout 4d50cf4331d50a726599fc93201db77a88d640e3
git -C "$FRAMENET_REPO" checkout 81da285274c7775cad6598cfe21ff6114f7f7c5b
python scripts/prepare_dfm10_danish_lexical_sft.py --force
python scripts/tokenize_chat_template.py \
  data/dfm10_danish_lexical_sources \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_danish_lexical \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Harvesting strict-open Tidsskrift.dk gold author-abstract rows..."
python scripts/prepare_dfm10_tidsskrift_expansion.py scan-sets --workers 2 --delay 1.0
python scripts/prepare_dfm10_tidsskrift_expansion.py export
python scripts/prepare_dfm10_tidsskrift_expansion.py download --delay 1.5
python scripts/prepare_dfm10_tidsskrift_expansion.py convert
if [[ -z "${TIDSSKRIFT_AUDIT_BASE_URL:-}" ]]; then
  echo "Set TIDSSKRIFT_AUDIT_BASE_URL to an OpenAI-compatible Gemma 4 31B server." >&2
  exit 2
fi
python scripts/audit_dfm10_tidsskrift_summaries.py audit \
  --input data/dfm10_tidsskrift_expansion/tidsskrift_open_article_summaries_candidates.jsonl \
  --output data/dfm10_tidsskrift_expansion/tidsskrift_open_article_summaries_audit.jsonl \
  --base-url "$TIDSSKRIFT_AUDIT_BASE_URL" \
  --model "${TIDSSKRIFT_AUDIT_MODEL:-gemma-4-31b}" \
  --concurrency "${TIDSSKRIFT_AUDIT_CONCURRENCY:-2}"
python scripts/audit_dfm10_tidsskrift_summaries.py filter \
  --input data/dfm10_tidsskrift_expansion/tidsskrift_open_article_summaries_candidates.jsonl \
  --audit data/dfm10_tidsskrift_expansion/tidsskrift_open_article_summaries_audit.jsonl \
  --output data/dfm10_tidsskrift_sources/tidsskrift_open_article_summaries.jsonl
if [[ ! -s data/dfm10_tidsskrift_open_sft_source/tidsskrift_open_sft.jsonl ]]; then
  echo "The unified Tidsskrift source is not built. Run scripts/run_dfm10_tidsskrift_grounded_8gpu.sh first." >&2
  exit 2
fi
if [[ ! -s data/dfm10_tidsskrift_open_chats_source/tidsskrift_open_chats.jsonl ]]; then
  echo "The Tidsskrift chat source is not built. Run scripts/run_dfm10_tidsskrift_grounded_8gpu.sh first." >&2
  exit 2
fi
python scripts/tokenize_chat_template.py \
  data/dfm10_tidsskrift_open_sft_source \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_tidsskrift_open \
  --workers "$TOKENIZER_WORKERS" \
  --force
python scripts/tokenize_chat_template.py \
  data/dfm10_tidsskrift_open_chats_source \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_tidsskrift_open_chats \
  --workers "$TOKENIZER_WORKERS" \
  --force
if [[ -s data/dfm10_danish_wikipedia_open_chats_source/danish_wikipedia_open_chats.jsonl ]]; then
  python scripts/tokenize_chat_template.py \
    data/dfm10_danish_wikipedia_open_chats_source \
    --tokenizer-path "$TOKENIZER_PATH" \
    --chat-template "$CHAT_TEMPLATE" \
    --output-dir data/tokenized_dfm10_danish_wikipedia_open_chats \
    --workers "$TOKENIZER_WORKERS" \
    --force
fi
if [[ -s data/dfm10_openstax_open_chats_source/openstax_open_chats.jsonl ]]; then
  python scripts/tokenize_chat_template.py \
    data/dfm10_openstax_open_chats_source \
    --tokenizer-path "$TOKENIZER_PATH" \
    --chat-template "$CHAT_TEMPLATE" \
    --output-dir data/tokenized_dfm10_openstax_open_chats \
    --workers "$TOKENIZER_WORKERS" \
    --force
fi

echo "Downloading approved Alexandra Institute DFM10 train sources..."
python scripts/download_training_datasets.py \
  --download \
  --groups dfm10 \
  --only alexandra_nordjylland_news,alexandra_scandi_qa,alexandra_multi_zebra_logic,alexandra_dane,alexandra_dacoref,zai_deepdive,allenai_code_meta_reasoning

echo "Converting approved Alexandra Institute DFM10 train sources..."
python scripts/prepare_dfm10_alexandra.py --force

echo "Converting Z.ai DeepDive trajectories to Gemma 4 native tool use..."
python scripts/prepare_dfm10_deepdive.py --force

echo "Generating Folketinget self-supervised transformation tasks..."
python scripts/prepare_dfm10_folketing_tasks.py --force

echo "Tokenizing Andersen training split with the Gemma 4 template..."
python scripts/tokenize_chat_template.py \
  data/dfm10_andersen_sources \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_andersen \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing bidirectional Bornholmsk translation tasks..."
python scripts/tokenize_chat_template.py \
  data/converted_sources/bornholmsk_parallel \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_bornholmsk_parallel \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing independently audited DiEm modernization tasks..."
python scripts/tokenize_chat_template.py \
  data/converted_sources/diem_modernization \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_diem_modernization \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing grounded COR.SEM tasks..."
python scripts/tokenize_chat_template.py \
  data/converted_sources/cor_sem_sft \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_cor_sem \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing grounded Danish book-ad tasks..."
python scripts/tokenize_chat_template.py \
  data/converted_sources/danish_book_ads_sft \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_danish_book_ads \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing grounded SKS editorial-commentary tasks..."
python scripts/tokenize_chat_template.py \
  data/converted_sources/sks_tei_sft \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_sks_tei \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing Alexandra Institute training splits with the Gemma 4 template..."
python scripts/tokenize_chat_template.py \
  data/dfm10_alexandra_sources \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_alexandra \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing native Z.ai DeepDive search trajectories..."
python scripts/tokenize_chat_template.py \
  data/dfm10_deepdive_sources \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_deepdive \
  --max-seq-len 4096 \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing validated repaired DBC abstracts and reviews..."
DBC_REPAIRED_STAGE="data/dfm10_dbc_repaired_sources"
rm -rf "$DBC_REPAIRED_STAGE"
mkdir -p "$DBC_REPAIRED_STAGE"
ln -s "$(realpath data/converted_sources/dbc_repaired)" "$DBC_REPAIRED_STAGE/dbc_repaired"
python scripts/tokenize_chat_template.py \
  "$DBC_REPAIRED_STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_dbc_repaired \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing verified and PRM-filtered OpenMathInstruct-2..."
OPENMATH_REPAIRED_STAGE="data/dfm10_openmathinstruct2_repaired_sources"
rm -rf "$OPENMATH_REPAIRED_STAGE"
mkdir -p "$OPENMATH_REPAIRED_STAGE"
ln -s "$(realpath data/converted_sources/openmathinstruct2_repaired)" \
  "$OPENMATH_REPAIRED_STAGE/openmathinstruct2_repaired"
python scripts/tokenize_chat_template.py \
  "$OPENMATH_REPAIRED_STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_openmathinstruct2_repaired \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing structurally repaired Nemotron SWE next-action supervision..."
NEMOTRON_SWE_REPAIRED_STAGE="data/dfm10_nemotron_swe_repaired_sources"
rm -rf "$NEMOTRON_SWE_REPAIRED_STAGE"
mkdir -p "$NEMOTRON_SWE_REPAIRED_STAGE"
ln -s "$(realpath data/converted_sources/nemotron_swe_repaired)" \
  "$NEMOTRON_SWE_REPAIRED_STAGE/nemotron_swe_repaired"
python scripts/tokenize_chat_template.py \
  "$NEMOTRON_SWE_REPAIRED_STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_nemotron_swe_repaired \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing audited DynaWord instruction repairs..."
DYNAWORD_INSTRUCT_REPAIRED="data/converted_sources/dynaword_instruct_repaired"
if [[ ! -f "$DYNAWORD_INSTRUCT_REPAIRED/manifest.json" ]]; then
  echo "Final repaired DynaWord instruction corpus is missing at $DYNAWORD_INSTRUCT_REPAIRED." >&2
  echo "Complete prompt generation, re-audit, and finalization before preparing DFM10." >&2
  exit 2
fi
DYNAWORD_INSTRUCT_STAGE="data/dfm10_dynaword_instruct_repaired_sources"
rm -rf "$DYNAWORD_INSTRUCT_STAGE"
mkdir -p "$DYNAWORD_INSTRUCT_STAGE/dynaword_instruct_repaired"
for source in "$DYNAWORD_INSTRUCT_REPAIRED"/*.jsonl; do
  ln -s "$(realpath "$source")" \
    "$DYNAWORD_INSTRUCT_STAGE/dynaword_instruct_repaired/$(basename "$source")"
done
python scripts/tokenize_chat_template.py \
  "$DYNAWORD_INSTRUCT_STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_dynaword_instruct_repaired \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Building and tokenizing language/alignment-filtered OPUS DA/EN pairs..."
OPUS_SCORED_ROOT="data/opus_da_en_quality/scored_shards"
OPUS_SHARD_COUNT="$(find "$OPUS_SCORED_ROOT" -maxdepth 1 -type f -name 'part-*.parquet' | wc -l)"
if [[ "$OPUS_SHARD_COUNT" -ne 64 ]]; then
  echo "Expected 64 complete OPUS score shards, found $OPUS_SHARD_COUNT." >&2
  echo "Run scripts/run_opus_da_en_filter_8gpu.sh before preparing DFM10." >&2
  exit 2
fi
python scripts/build_opus_da_en_repaired.py
OPUS_REPAIRED_STAGE="data/dfm10_opus_repaired_sources"
rm -rf "$OPUS_REPAIRED_STAGE"
mkdir -p "$OPUS_REPAIRED_STAGE"
ln -s "$(realpath data/converted_sources/opus_da_en_repaired)" \
  "$OPUS_REPAIRED_STAGE/opus_da_en_repaired"
python scripts/tokenize_chat_template.py \
  "$OPUS_REPAIRED_STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_opus_repaired \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing fully audited Danish university-portals instructions..."
UNIVERSITY_PORTALS_REPAIRED="data/converted_sources/danish_university_portals_bt_repaired"
if [[ ! -f "$UNIVERSITY_PORTALS_REPAIRED/manifest.json" ]]; then
  echo "University-portals full-corpus repair is missing." >&2
  echo "Run scripts/finish_danish_university_portals_bt_repair.sh before preparing DFM10." >&2
  exit 2
fi
UNIVERSITY_PORTALS_STAGE="data/dfm10_university_portals_repaired_sources"
rm -rf "$UNIVERSITY_PORTALS_STAGE"
mkdir -p "$UNIVERSITY_PORTALS_STAGE"
ln -s "$(realpath "$UNIVERSITY_PORTALS_REPAIRED")" \
  "$UNIVERSITY_PORTALS_STAGE/danish_university_portals_bt_repaired"
python scripts/tokenize_chat_template.py \
  "$UNIVERSITY_PORTALS_STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_university_portals_repaired \
  --workers "$TOKENIZER_WORKERS" \
  --force
python scripts/repair_danish_university_portals_bt.py validate

echo "Repairing and tokenizing structured AllenAI Code Meta-Reasoning..."
python scripts/repair_code_meta_reasoning.py --workers 36
CODE_META_AUDIT="logs/data_audits/code_meta_reasoning_repaired_20260828/summary.json"
python - "$CODE_META_AUDIT" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(f"missing required Code Meta-Reasoning audit: {path}")
summary = json.loads(path.read_text())
if summary.get("strict_usable_rate", 0.0) < 0.90:
    raise SystemExit(
        f"Code Meta-Reasoning strict audit gate failed: {summary.get('strict_usable_rate')}"
    )
PY
CODE_META_REPAIRED_STAGE="data/dfm10_code_meta_reasoning_repaired_sources"
rm -rf "$CODE_META_REPAIRED_STAGE"
mkdir -p "$CODE_META_REPAIRED_STAGE"
ln -s "$(realpath data/converted_sources/code_meta_reasoning_repaired)" \
  "$CODE_META_REPAIRED_STAGE/code_meta_reasoning_repaired"
python scripts/tokenize_chat_template.py \
  "$CODE_META_REPAIRED_STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_code_meta_reasoning_repaired \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Repairing and tokenizing validated DOLCI native tool-use trajectories..."
python scripts/repair_dolci_tool_use.py --workers 7 --force
DOLCI_REPAIRED_STAGE="data/dfm10_dolci_tool_use_repaired_sources"
python scripts/build_dolci_tool_use_tokenizer_staging.py \
  --output-root "$DOLCI_REPAIRED_STAGE"
python scripts/tokenize_chat_template.py \
  "$DOLCI_REPAIRED_STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_dolci_tool_use_repaired \
  --max-seq-len 4096 \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing fully audited, complete, grounded GovReport summaries..."
if [[ ! -f data/converted_sources/govreport_summarization_grounded/filter_summary.json ]]; then
  echo "GovReport full-corpus grounding filter is missing. Follow wiki/pages/dfm10-govreport-repair.md first."
  exit 2
fi
GOVREPORT_REPAIRED_STAGE="data/dfm10_govreport_repaired_sources"
rm -rf "$GOVREPORT_REPAIRED_STAGE"
mkdir -p "$GOVREPORT_REPAIRED_STAGE/govreport_summarization_repaired"
for source in data/converted_sources/govreport_summarization_grounded/*.parquet; do
  ln -s "$(realpath "$source")" \
    "$GOVREPORT_REPAIRED_STAGE/govreport_summarization_repaired/$(basename "$source")"
done
python scripts/tokenize_chat_template.py \
  "$GOVREPORT_REPAIRED_STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_govreport_repaired \
  --workers 2 \
  --force

echo "Building and tokenizing fully audited, grounded WikiCatSum summaries..."
WIKI_CAT_REPAIRED="data/converted_sources/wiki_cat_sum_repaired_with_recovery"
if [[ ! -f "$WIKI_CAT_REPAIRED/filter_summary.json" ]]; then
  python scripts/repair_wiki_cat_sum.py --workers "$TOKENIZER_WORKERS"
  WIKI_CAT_CANDIDATES="data/converted_sources/wiki_cat_sum_grounded_candidates"
  WIKI_CAT_AUDIT="logs/data_audits/wiki_cat_sum_repaired_20260828"
  WIKI_CAT_REPAIRED="data/converted_sources/wiki_cat_sum_repaired"
  python scripts/audit_repaired_wiki_cat_sum.py filter \
    --input-dir "$WIKI_CAT_CANDIDATES" \
    --audit-dir "$WIKI_CAT_AUDIT" \
    --output-dir "$WIKI_CAT_REPAIRED"
fi
WIKI_CAT_REPAIRED_STAGE="data/dfm10_wiki_cat_sum_repaired_sources"
rm -rf "$WIKI_CAT_REPAIRED_STAGE"
mkdir -p "$WIKI_CAT_REPAIRED_STAGE"
ln -s "$(realpath "$WIKI_CAT_REPAIRED")" \
  "$WIKI_CAT_REPAIRED_STAGE/wiki_cat_sum_repaired"
python scripts/tokenize_chat_template.py \
  "$WIKI_CAT_REPAIRED_STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_wiki_cat_sum_repaired \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing repaired Scientific Summaries and Sapient sources..."
for specification in \
  "scientific_summaries_repaired:data/converted_sources/scientific_summaries_repaired:data/tokenized_dfm10_scientific_summaries_repaired" \
  "sapient_qrecc_ii_repaired:data/converted_sources/sapient_qrecc_ii_repaired:data/tokenized_dfm10_qrecc_ii_repaired" \
  "sapient_scibench_repaired:data/converted_sources/sapient_scibench_repaired:data/tokenized_dfm10_scibench_repaired"; do
  IFS=: read -r name source output <<< "$specification"
  stage="data/dfm10_${name}_sources"
  rm -rf "$stage"
  mkdir -p "$stage"
  ln -s "$(realpath "$source")" "$stage/$name"
  python scripts/tokenize_chat_template.py "$stage" \
    --tokenizer-path "$TOKENIZER_PATH" \
    --chat-template "$CHAT_TEMPLATE" \
    --output-dir "$output" \
    --workers "$TOKENIZER_WORKERS" \
    --force
done

echo "Tokenizing language/alignment-filtered DA/UK translation pairs..."
DA_UK_REPAIRED="data/converted_sources/machine_translation_da_uk_repaired"
if [[ ! -f "$DA_UK_REPAIRED/manifest.json" ]]; then
  echo "DA/UK repair is incomplete. Run scripts/run_machine_translation_da_uk_repair_when_free.sh first." >&2
  exit 2
fi
DA_UK_STAGE="data/dfm10_machine_translation_da_uk_repaired_sources"
rm -rf "$DA_UK_STAGE"
mkdir -p "$DA_UK_STAGE"
ln -s "$(realpath "$DA_UK_REPAIRED")" "$DA_UK_STAGE/machine_translation_da_uk_repaired"
python scripts/tokenize_chat_template.py "$DA_UK_STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_machine_translation_da_uk_repaired \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing fully audited, answer-matched Danmarks Statistik instructions..."
DST_REPAIRED="data/converted_sources/danmarks_statistik_bt_repaired_with_article_recovery"
if [[ ! -f "$DST_REPAIRED/filter_summary.json" ]]; then
  DST_REPAIRED="data/converted_sources/danmarks_statistik_bt_repaired"
fi
if [[ ! -f "$DST_REPAIRED/filter_summary.json" ]]; then
  echo "Danmarks Statistik BT full-corpus repair is missing. Follow wiki/pages/dfm10-danmarks-statistik-repair.md first." >&2
  exit 2
fi
DST_REPAIRED_STAGE="data/dfm10_danmarks_statistik_bt_repaired_sources"
rm -rf "$DST_REPAIRED_STAGE"
mkdir -p "$DST_REPAIRED_STAGE"
ln -s "$(realpath "$DST_REPAIRED")" \
  "$DST_REPAIRED_STAGE/danmarks_statistik_bt_repaired"
python scripts/tokenize_chat_template.py \
  "$DST_REPAIRED_STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_danmarks_statistik_bt_repaired \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing fully audited and grounded NordjyllandNews summaries..."
NORDJYLLAND_REPAIRED="data/converted_sources/nordjylland_news_repaired_grounded"
if [[ ! -f "$NORDJYLLAND_REPAIRED/filter_summary.json" ]]; then
  echo "NordjyllandNews full-corpus grounding filter is missing. Follow wiki/pages/dfm10-nordjylland-news-repair.md first." >&2
  exit 2
fi
NORDJYLLAND_REPAIRED_STAGE="data/dfm10_nordjylland_news_repaired_sources"
rm -rf "$NORDJYLLAND_REPAIRED_STAGE"
mkdir -p "$NORDJYLLAND_REPAIRED_STAGE/nordjylland_news_repaired"
ln -s "$(realpath "$NORDJYLLAND_REPAIRED/train.parquet")" \
  "$NORDJYLLAND_REPAIRED_STAGE/nordjylland_news_repaired/train.parquet"
python scripts/tokenize_chat_template.py \
  "$NORDJYLLAND_REPAIRED_STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_nordjylland_news_repaired \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Checking fully audited and grounded DST table-to-text examples..."
DST_REPAIRED="data/converted_sources/dst_table_prompts_repaired_grounded"
if [[ ! -f "data/tokenized_dfm10_dst_table_prompts_repaired/production_gate.json" ]]; then
  echo "DST table-prompts full-corpus grounding filter is missing. Follow wiki/pages/dfm10-dst-table-prompts-repair.md first." >&2
  exit 2
fi

FOLKETING_AUDITED_ROOT="${FOLKETING_AUDITED_ROOT:-data/dfm10_folketing_transform_sources_audited}"
if [[ ! -d "$FOLKETING_AUDITED_ROOT" ]]; then
  echo "Folketinget candidates are ready for audit, but no filtered tree exists at $FOLKETING_AUDITED_ROOT."
  echo "Run scripts/audit_dfm10_folketing_tasks.sh and scripts/filter_dfm10_folketing_tasks.sh before tokenization."
  exit 2
fi

echo "Tokenizing audited Folketinget transformation tasks with the Gemma 4 template..."
python scripts/tokenize_chat_template.py \
  "$FOLKETING_AUDITED_ROOT" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_folketing \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing independently audited OpenStax Mimir SFT..."
if [[ ! -f data/dfm10_openstax_sft_sources/manifest.json ]]; then
  echo "Audited OpenStax staging is missing. Run scripts/integrate_openstax_mimir_sft_when_audited.sh first." >&2
  exit 2
fi
python scripts/tokenize_chat_template.py \
  data/dfm10_openstax_sft_sources \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_openstax_sft \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Tokenizing expanded Mimir grounded SFT..."
MIMIR_PACKAGE="exports_dfm10/dfm10-mimir-grounded-expanded-sft"
MIMIR_SOURCE_ROOT="data/dfm10_mimir_grounded_expanded_sources"
if [[ ! -s "$MIMIR_PACKAGE/metadata/validation.json" ]]; then
  echo "Validated expanded Mimir export package is missing." >&2
  exit 2
fi
MIMIR_SOURCE_TMP="${MIMIR_SOURCE_ROOT}.tmp.$$"
rm -rf "$MIMIR_SOURCE_TMP"
mkdir -p "$MIMIR_SOURCE_TMP"
for shard in "$MIMIR_PACKAGE"/data/train-*.jsonl.gz; do
  [[ -f "$shard" ]] || { echo "Expanded Mimir export shards are missing." >&2; exit 2; }
  suffix="${shard##*/train-}"
  ln -s "$ROOT/$shard" "$MIMIR_SOURCE_TMP/mimir_grounded_expanded_sft__part-$suffix"
done
rm -rf "$MIMIR_SOURCE_ROOT"
mv "$MIMIR_SOURCE_TMP" "$MIMIR_SOURCE_ROOT"
python scripts/tokenize_chat_template.py \
  "$MIMIR_SOURCE_ROOT" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_mimir_grounded_expanded_sft \
  --workers "$TOKENIZER_WORKERS" \
  --force

if [[ -s data/mimir_benchmark_campaigns/accepted/summary.json ]]; then
  echo "Tokenizing accepted Mimir benchmark campaigns..."
  python scripts/tokenize_chat_template.py \
    data/mimir_benchmark_campaigns/accepted \
    --tokenizer-path "$TOKENIZER_PATH" \
    --chat-template "$CHAT_TEMPLATE" \
    --output-dir data/tokenized_dfm10_mimir_benchmark_campaigns \
    --workers "$TOKENIZER_WORKERS" \
    --force
fi

echo "Preparing and tokenizing native multi-turn Nemotron Terminal conversations..."
python scripts/prepare_nemotron_terminal_native.py --force
python scripts/tokenize_chat_template.py \
  data/converted_sources/nemotron_terminal_corpus_native \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_nemotron_terminal_native \
  --max-seq-len 4096 \
  --preserve-first-user \
  --workers "$TOKENIZER_WORKERS" \
  --force

echo "Preparing and tokenizing Synthetic Values Model Charter SFT..."
python scripts/prepare_dfm10_synthetic_values_model_charter.py --force
python scripts/tokenize_chat_template.py \
  data/converted_sources/dfm10_synthetic_values_model_charter \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_synthetic_values_model_charter \
  --workers "$TOKENIZER_WORKERS" \
  --force

if [[ -s data/converted_sources/dfm10_synthetic_values_model_charter_da/data/model_charter_values_da.jsonl ]]; then
  echo "Tokenizing audited Danish Synthetic Values Model Charter SFT..."
  python scripts/tokenize_chat_template.py \
    data/converted_sources/dfm10_synthetic_values_model_charter_da \
    --tokenizer-path "$TOKENIZER_PATH" \
    --chat-template "$CHAT_TEMPLATE" \
    --output-dir data/tokenized_dfm10_synthetic_values_model_charter_da \
    --workers "$TOKENIZER_WORKERS" \
    --force
fi

if [[ -s data/dfm10_danish_persona_chats_source/danish_persona_chats__accepted.jsonl ]]; then
  echo "Tokenizing audited Danish persona chats..."
  python scripts/tokenize_chat_template.py \
    data/dfm10_danish_persona_chats_source \
    --tokenizer-path "$TOKENIZER_PATH" \
    --chat-template "$CHAT_TEMPLATE" \
    --output-dir data/tokenized_dfm10_danish_persona_chats \
    --workers "$TOKENIZER_WORKERS" \
    --force
fi
if [[ -s data/dfm10_domsdatabasen_grounded_chats_source/domsdatabasen_grounded_chats__accepted.jsonl ]]; then
  echo "Tokenizing audited Domsdatabasen grounded chats..."
  python scripts/tokenize_chat_template.py \
    data/dfm10_domsdatabasen_grounded_chats_source \
    --tokenizer-path "$TOKENIZER_PATH" \
    --chat-template "$CHAT_TEMPLATE" \
    --output-dir data/tokenized_dfm10_domsdatabasen_grounded_chats \
    --workers "$TOKENIZER_WORKERS" \
    --force
fi

echo "Building DFM10 tokenized union tree..."
python scripts/build_tokenized_dfm10_tree.py \
  --nemotron-terminal-native data/tokenized_dfm10_nemotron_terminal_native \
  --bornholmsk-parallel data/tokenized_dfm10_bornholmsk_parallel \
  --diem-modernization data/tokenized_dfm10_diem_modernization \
  --cor-sem data/tokenized_dfm10_cor_sem \
  --danish-book-ads data/tokenized_dfm10_danish_book_ads \
  --sks-tei data/tokenized_dfm10_sks_tei \
  --folketing data/tokenized_dfm10_folketing \
  --dbc-repaired data/tokenized_dfm10_dbc_repaired \
  --openmath-repaired data/tokenized_dfm10_openmathinstruct2_repaired \
  --dolci-tool-use-repaired data/tokenized_dfm10_dolci_tool_use_repaired \
  --govreport-repaired data/tokenized_dfm10_govreport_repaired \
  --wiki-cat-sum-repaired data/tokenized_dfm10_wiki_cat_sum_repaired \
  --danmarks-statistik-bt-repaired data/tokenized_dfm10_danmarks_statistik_bt_repaired \
  --nordjylland-news-repaired data/tokenized_dfm10_nordjylland_news_repaired \
  --dst-table-prompts-repaired data/tokenized_dfm10_dst_table_prompts_repaired \
  --nemotron-swe-repaired data/tokenized_dfm10_nemotron_swe_repaired \
  --dynaword-instruct-repaired data/tokenized_dfm10_dynaword_instruct_repaired \
  --code-meta-reasoning-repaired data/tokenized_dfm10_code_meta_reasoning_repaired \
  --opus-repaired data/tokenized_dfm10_opus_repaired \
  --university-portals-repaired data/tokenized_dfm10_university_portals_repaired \
  --scientific-summaries-repaired data/tokenized_dfm10_scientific_summaries_repaired \
  --machine-translation-da-uk-repaired data/tokenized_dfm10_machine_translation_da_uk_repaired \
  --qrecc-ii-repaired data/tokenized_dfm10_qrecc_ii_repaired \
  --scibench-repaired data/tokenized_dfm10_scibench_repaired \
  --openstax-sft data/tokenized_dfm10_openstax_sft \
  --mimir-grounded-expanded-sft data/tokenized_dfm10_mimir_grounded_expanded_sft \
  --mimir-benchmark-campaigns data/tokenized_dfm10_mimir_benchmark_campaigns \
  --danish-lexical data/tokenized_dfm10_danish_lexical \
  --tidsskrift-open data/tokenized_dfm10_tidsskrift_open \
  --tidsskrift-open-chats data/tokenized_dfm10_tidsskrift_open_chats \
  --synthetic-values-model-charter data/tokenized_dfm10_synthetic_values_model_charter \
  --synthetic-values-model-charter-da data/tokenized_dfm10_synthetic_values_model_charter_da \
  --danish-persona-chats data/tokenized_dfm10_danish_persona_chats \
  --domsdatabasen-grounded-chats data/tokenized_dfm10_domsdatabasen_grounded_chats \
  --medical data/tokenized_dfm10_medical \
  --force

if [[ "${DFM10_SAMPLE:-0}" == "1" ]]; then
  echo "Sampling DFM10 (${DFM10_EPOCHS:-10} epochs)..."
  (
    cd data_io
    python sample_tokenized.py \
      tokenized_path=../data/tokenized_dfm10 \
      output_path=../data/sampled_dfm10 \
      epochs="${DFM10_EPOCHS:-10}" \
      concat_workers="${DFM10_CONCAT_WORKERS:-4}" \
      default_long_context=drop \
      prefix_config_path=prefix_config_dfm10.yaml \
      > ../data/show_analytics_dfm10.md
  )
else
  echo "DFM10 tokenized tree is ready. Set DFM10_SAMPLE=1 to sample it."
fi
