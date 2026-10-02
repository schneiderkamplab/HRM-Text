import json

import numpy as np
import pytest

from dfm12.io import file_hash, write_json
from dfm12.token_accounting import inherited_budget, scan_candidates, tokenized_totals


def fixture_report(tmp_path):
    report = tmp_path / "report.log"
    header = "| Name | Rows (%) | Tokens (%) | Cov Rows (%) | Cov Toks (%) | Cov IToks (%) | Cov RToks (%) |\n"
    report.write_text("### Category Coverage Stats\n" + header +
                      "| **GLOBAL** | 5 | 100 | 20 | 801 | 600 | 201 |\n" +
                      "### Task Coverage Stats\n" + header +
                      "| **opus_da_en_repaired__a** | 3 | 60 | 10 | 401 | 300 | 101 |\n" +
                      "| **other** | 2 | 40 | 10 | 400 | 300 | 100 |\n")
    root = tmp_path / "sampled"
    for i in range(10):
        epoch = root / f"epoch_{i}"
        epoch.mkdir(parents=True)
        np.save(epoch / "inst_len.npy", np.array([1, 2]))
    write_json(root / "metadata.json", {"total_length": 80})
    return report, root


def test_epoch_normalization_and_floor_caps(tmp_path):
    report, root = fixture_report(tmp_path)
    result = inherited_budget(report, root)
    assert result["T"] == {"numerator": 401, "denominator": 10, "tokens": 40.1}
    assert result["english_pair_cap"] == 10
    assert result["non_english_pair_cap"] == 2


def test_wrong_sample_report_fails_closed(tmp_path):
    report, root = fixture_report(tmp_path)
    write_json(root / "metadata.json", {"total_length": 81})
    with pytest.raises(ValueError, match="metadata"):
        inherited_budget(report, root)


def test_duplicate_report_not_double_counted(tmp_path):
    report, root = fixture_report(tmp_path)
    with report.open("a") as handle:
        handle.write("| **other** | 2 | 40 | 10 | 400 | 300 | 100 |\n")
    with pytest.raises(ValueError, match="Duplicate"):
        inherited_budget(report, root)


def test_translation_both_directions_counted_once(tmp_path):
    path = tmp_path / "candidates.jsonl"
    path.write_text(json.dumps(dict(language="sv", reverse_language="en", task="translation",
                                    messages=[], reverse_messages=[], rendered_tokens=123)) + "\n")
    result = scan_candidates([path], {"sha256": file_hash(path)})
    assert result["exact_tokens"] == 123
    assert result["conversations"] == 2
    assert result["groups"]["en+sv/translation"]["tokens"] == 123
    with pytest.raises(ValueError, match="checksum"):
        scan_candidates([path], {"sha256": "wrong"})


def test_missing_tokens_explicit_estimate_not_zero(tmp_path):
    path = tmp_path / "candidates.jsonl"
    path.write_text((json.dumps(dict(language="nl", task="instruction", messages=[])) + "\n") * 3)
    class Renderer:
        def count(self, messages):
            return 20
    result = scan_candidates([path], {}, Renderer(), 2)
    assert result["exact_tokens"] is None
    group = result["groups"]["nl/instruction"]
    assert group["estimated_tokens"] == 60
    assert group["method"] == "bounded_prefix_render_estimate"
    assert scan_candidates([path], {}, Renderer(), 3)["exact_tokens"] == 60


def test_nan_metadata_does_not_hide_valid_token_count(tmp_path):
    path = tmp_path / "candidates.jsonl"
    path.write_text(json.dumps(dict(language="pl", task="instruction", rendered_tokens=10,
                                    provenance={"upstream_score": float("nan")})) + "\n")
    assert scan_candidates([path], {})["exact_tokens"] == 10
    path.write_text(json.dumps(dict(rendered_tokens=float("nan"))) + "\n")
    with pytest.raises(ValueError, match="Invalid rendered_tokens"):
        scan_candidates([path], {})


def test_tokenized_storage_not_used_as_rendered_total(tmp_path):
    shard = tmp_path / "part-0"
    shard.mkdir()
    write_json(shard / "metadata.json", {})
    np.save(shard / "inst_len.npy", np.array([5, 10, 20], dtype=np.uint32))
    np.save(shard / "resp_len.npy", np.array([3, 7, 8], dtype=np.uint32))
    np.save(shard / "tokens.npy", np.zeros(40, dtype=np.int32))
    write_json(tmp_path / "completion.json", {"files": 1, "rows": 3})
    result = tokenized_totals(tmp_path, chunk_size=2)
    assert result["rendered_tokens"] == 53
    assert result["stored_tokens"] == 40
