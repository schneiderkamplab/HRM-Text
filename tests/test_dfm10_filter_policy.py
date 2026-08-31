from pathlib import Path

import yaml

from scripts.dfm10_quality_audit import task_policy


POLICY_PATH = Path("data_io/prefix_config_dfm10.yaml")


def policy(name: str) -> dict:
    return task_policy(name, yaml.safe_load(POLICY_PATH.read_text()))


def test_specific_sapient_exclusions_precede_broad_rule() -> None:
    names = (
        "sapient-synth-flan-dialog-zsopt-data-qrecc-ii__data__train.jsonl.gz",
        "sapient-synth-flan-dialog-fsopt-data-qrecc-ii__data__train.jsonl.gz",
        "sapient-synth-platypus-scibench__data__train.jsonl.gz",
        "sapient-synth-flan-niv2-zsopt-data-task871-msmarco-question-generation__data__train.jsonl.gz",
        "sapient-synth-flan-niv2-fsopt-data-task871-msmarco-question-generation__data__train.jsonl.gz",
    )
    assert all(policy(name).get("max_per_file") == 0 for name in names)


def test_repaired_replacements_are_enabled() -> None:
    names = (
        "sapient_qrecc_ii_repaired__zsopt.parquet",
        "sapient_scibench_repaired__train.parquet",
        "scientific_summaries_repaired__titled_00001.parquet",
        "machine_translation_da_uk_repaired__part-00000.parquet",
    )
    assert all(policy(name).get("max_per_file", 1) != 0 for name in names)


def test_audited_openstax_sft_is_enabled_once() -> None:
    assert policy("openstax_mimir_sft__data__part-00000-of-00016.jsonl")["repeat"] == 1


def test_every_filter_source_has_a_decision() -> None:
    decisions = yaml.safe_load(Path("config/dfm10_filter_source_decisions.yaml").read_text())
    assert len(decisions) == 32
    assert all(str(value).strip() for value in decisions.values())
