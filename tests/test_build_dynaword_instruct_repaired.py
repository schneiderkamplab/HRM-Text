from __future__ import annotations

import argparse
import json

from scripts.build_dynaword_instruct_repaired import finalize, strict_pass


def judgment(*, usable: bool = True, language: int = 5, coherence: int = 5, value: int = 5) -> dict:
    return {
        "usable_for_training": usable,
        "language_quality": {"score": language},
        "instruction_answer_coherence": {"score": coherence},
        "training_value": {"score": value},
    }


def write_jsonl(path, rows) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def plan_row(sample_id: str, action: str, prompt: str, target: str, row: int) -> dict:
    return {
        "sample_id": sample_id,
        "source_id": "oliverkinch/da-instruct-dynaword",
        "source_file": "source.parquet",
        "source_row": row,
        "source_example_id": f"example-{row}",
        "source_meta": {},
        "prompt": prompt,
        "response": target,
        "action": action,
    }


def test_strict_pass_requires_all_thresholds() -> None:
    assert strict_pass(judgment())
    assert not strict_pass(judgment(coherence=3))
    assert not strict_pass(judgment(value=3))
    assert not strict_pass(judgment(usable=False))


def test_finalize_prefers_clean_rows_and_caps_prompts_per_target(tmp_path) -> None:
    plan = tmp_path / "plan.jsonl"
    audit = tmp_path / "audit.jsonl"
    output = tmp_path / "output"
    rows = [
        plan_row("clean", "keep", "Original prompt", "Shared target", 0),
        plan_row("repair", "repair_prompt", "Bad prompt", "Shared target", 1),
        plan_row("third", "repair_prompt", "Bad prompt 2", "Shared target", 2),
        plan_row("drop", "drop_bad_target", "Prompt", "Bad target", 3),
    ]
    write_jsonl(plan, rows)
    write_jsonl(
        audit,
        [
            {"sample_id": "repair", "prompt": "Repaired prompt", "judgment": judgment()},
            {"sample_id": "third", "prompt": "Third prompt", "judgment": judgment()},
        ],
    )

    finalize(
        argparse.Namespace(
            plan=plan,
            repair_audit=audit,
            output_root=output,
            max_prompts_per_target=2,
        )
    )

    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["final_rows"] == 2
    assert manifest["dispositions"] == {
        "kept_original": 1,
        "prompt_repaired_and_reaudited": 1,
    }
    assert manifest["rejected"]["drop_bad_target"] == 1
    assert manifest["rejected"]["target_prompt_cap"] == 1
