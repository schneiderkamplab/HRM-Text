from __future__ import annotations

from scripts.merge_standard_eval_shards import compute_merged_mmlu


def test_mmlu_merge_sums_subject_counts_and_recomputes_macro_average() -> None:
    merged = compute_merged_mmlu(
        [
            {
                "n": 2,
                "n_math": 3,
                "acc_math": 2 / 3,
                "invalid_math": 1 / 3,
                "n_law": 2,
                "acc_law": 0.5,
                "invalid_law": 0.0,
            },
            {
                "n": 2,
                "n_math": 2,
                "acc_math": 0.5,
                "invalid_math": 0.0,
                "n_law": 3,
                "acc_law": 2 / 3,
                "invalid_law": 1 / 3,
            },
        ]
    )

    assert merged["n"] == 2
    assert merged["n_math"] == 5
    assert merged["n_law"] == 5
    assert merged["acc_math"] == 0.6
    assert merged["acc_law"] == 0.6
    assert merged["acc"] == 0.6
    assert merged["invalid_math"] == 0.2
    assert merged["invalid_law"] == 0.2
    assert merged["invalid"] == 0.2
