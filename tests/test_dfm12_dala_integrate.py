from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from dfm12.dala_integrate import (LANGUAGES, STANDARDS, check_pair, conversations,
                                 convert_shard, init_worker, integrate, screen, text_hash)
from dfm12.io import file_hash, load, write_json


def pair(language="nb", split="train", identifier="p", text="Good words"):
    return {"language": language, "split": split, "pair_id": identifier,
            "document_id": identifier, "document_sha256": identifier,
            "source_dataset": "repo", "source_revision": "revision", "source_file": "file",
            "source_name": "constituent", "license": "owner-authorized", "url": "source",
            "original": text, "corrupted": "Bad" + text[4:],
            "edits": [{"start": 0, "end": 4, "original": text[:4], "replacement": "Bad",
                       "corrupted_start": 0, "corrupted_end": 3, "corruption_type": "spelling"}]}


def manifest(language="nb"):
    return {"source_snapshots": [{"repo_id": "repo", "revision": "revision", "file": "file"}],
            "prompts": {t: f"{t} {STANDARDS[language]}" for t in ("acceptability", "correction")}}


class DaLAIntegrationTests(unittest.TestCase):
    def test_views_all_standards(self):
        for language in LANGUAGES:
            p = pair(language)
            converted = list(conversations(p, manifest(language)["prompts"], "sha"))
            self.assertEqual(len(converted), 4)
            self.assertEqual([r["messages"][-1]["content"] for r in converted], ["yes", "no", p["original"], p["original"]])
            self.assertEqual(len({r["id"] for r in converted}), 4)
            self.assertEqual(converted[2]["messages"][0]["content"].split("\n\n")[-1], p["original"])
            self.assertTrue(all(r["language"] == language and r["provenance"]["split"] == "train" for r in converted))
            self.assertTrue(all(r["provenance"]["license"] == "owner-authorized" for r in converted))

    def test_wrong_standard_and_heldout_rejected(self):
        with self.assertRaises(ValueError):
            list(conversations(pair("nn"), manifest("nb")["prompts"], "sha"))
        with self.assertRaises(ValueError):
            list(conversations(pair(split="test"), manifest()["prompts"], "sha"))
        with self.assertRaises(ValueError):
            list(conversations(pair("pl"), manifest()["prompts"], "sha"))

    def test_normalization(self):
        self.assertEqual(text_hash("CAF\u00c9  word"), text_hash("cafe\u0301\nword"))

    def test_reconstruction_and_provenance(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.execute("CREATE TABLE documents (lang TEXT,id TEXT,payload TEXT)")
        p = pair()
        db.execute("INSERT INTO documents VALUES (?,?,?)", ("nb", "p", json.dumps(p)))
        check_pair(p, "nb", "train", db, manifest())
        changed = deepcopy(p)
        changed["corrupted"] = "Not reconstructed"
        with self.assertRaises(ValueError):
            check_pair(changed, "nb", "train", db, manifest())
        changed = deepcopy(p)
        changed["source_revision"] = "different"
        with self.assertRaises(ValueError):
            check_pair(changed, "nb", "train", db, manifest())

    def test_screen_blocks_heldout_other_language_and_late_flags(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = {"sources": {}, "late_exclusions": {}}
            for lang in LANGUAGES:
                source = root / lang
                p = pair(lang, identifier=lang, text="Good unique " + lang)
                held = pair(lang, "test", "test-" + lang, "Good held " + lang)
                train = [p]
                if lang == "nb":
                    train.append(pair(lang, identifier="cross-held", text="Good held nn"))
                    excluded = pair(lang, identifier="late", text="Good late flag")
                    train.append(excluded)
                    inputs["late_exclusions"][lang] = [{"original_sha256": hashlib.sha256(excluded["original"].encode()).hexdigest()}]
                m = manifest(lang)
                m["splits"] = {"train": {"pairs": len(train)}, "validation": {"pairs": 0}, "test": {"pairs": 1}}
                source.mkdir()
                (source / "documents.jsonl").write_text("".join(json.dumps(p) + "\n" for p in train + [held]))
                for split, values in (("train", train), ("test", [held]), ("validation", [])):
                    (source / split).mkdir()
                    (source / split / "pairs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in values))
                inputs["sources"][lang] = {"raw": str(source), "selected": str(source), "raw_manifest": m, "selected_manifest": m}
            output = root / "output"
            output.mkdir()
            result = screen(inputs, output)
            self.assertEqual(result["counts"]["nb"]["heldout_text_pairs"], 1)
            self.assertEqual(result["counts"]["nb"]["late_excluded_pairs"], 1)
            self.assertEqual(result["counts"]["nb"]["screened_pairs"], 1)
            self.assertEqual(screen(inputs, output), result)

    def test_actual_raw_gemma_worker_arrays_and_resume(self):
        import numpy as np
        metadata = Path("data/sampled_dfm11/metadata.json")
        if not metadata.exists():
            self.skipTest("Raw inherited tokenizer unavailable")
        info = load(metadata)["tokenizer_info"]
        init_worker(info)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = pair()
            path = root / "part-00000.jsonl"
            path.write_text(json.dumps(p) + "\n")
            shard = {"path": str(path), "language": "nb", "sha256": file_hash(path)}
            source = {"selected_manifest": manifest(), "selected_receipt": {"sha256": "fixture"}}
            result = convert_shard((shard, source, str(root)))
            self.assertEqual(result["counts"]["converted_pairs"], 1)
            for task in ("acceptability", "correction"):
                directory = root / "tokenized_unaudited" / f"dala-nb-{task}" / "part-00000"
                tokens = np.load(directory / "tokens.npy")
                starts = np.load(directory / "resp_start.npy")
                lengths = np.load(directory / "resp_len.npy")
                self.assertEqual(len(starts), 2)
                self.assertTrue(np.all(starts + lengths <= len(tokens)))
            self.assertEqual(convert_shard((shard, source, str(root))), result)

    def test_end_to_end_waiting_finalizer_and_audit_discovery(self):
        import os
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from dfm12.dala_verify import verify
        from dfm12.dala_refresh import apply_local_integration, main as refresh_main
        from dfm12.audit_readiness import discover
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            producer, output = root / "producer", root / "integration"
            base = producer / "wiki/artifacts/six-language-expansion"
            runs = {l: "recovery_v1" for l in LANGUAGES}
            write_json(base / "current-run.json", {"run_id": "recovery_v1", "language_runs": runs,
                "finalization": "wiki/artifacts/six-language-expansion/recovery_v1/finalization.json"})
            write_json(base / "recovery_v1/finalization.json", {"status": "waiting_for_builds", "language_runs": runs,
                                                               "run_id": "recovery_v1"})
            write_json(base / "scale_v1/late-review-exclusions.json", {})
            for lang in LANGUAGES:
                source = producer / "la_output" / lang
                source.mkdir(parents=True)
                train = pair(lang, identifier=lang, text="Good training " + lang)
                held = pair(lang, "test", "test-" + lang, "Good heldout " + lang)
                (source / "documents.jsonl").write_text(json.dumps(train) + "\n" + json.dumps(held) + "\n")
                write_json(source / "rules.json", {})
                m = manifest(lang)
                m.update(language=lang, schema_version="2", artifacts={},
                         verification={"pairs": 2, "exact_edit_reconstruction": True,
                                       "correction_roundtrip": True, "document_split_isolation": True}, splits={})
                for split, values in (("train", [train]), ("test", [held]), ("validation", [])):
                    (source / split).mkdir()
                    (source / split / "pairs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in values))
                    m["splits"][split] = {"pairs": len(values)}
                for path in source.rglob("*.json*"):
                    m["artifacts"][str(path.relative_to(source))] = {"sha256": file_hash(path), "bytes": path.stat().st_size}
                write_json(source / "manifest.json", m)
                write_json(base / f"recovery_v1/{lang}-status.json", {"language": lang, "exit_code": 0,
                           "output": str(source.relative_to(producer))})
            result = integrate(producer, output, workers=1)
            self.assertEqual(len(result["components"]), 6)
            self.assertFalse(result["producer_finalized"])
            verified = verify(output)
            self.assertEqual(sum(verified["counts"].values()), 12)
            catalog, pending = discover(root / "empty-catalog", [output / "integration.json"])
            self.assertEqual(len(catalog), 6)
            self.assertIn("additional-dala", pending)
            registration = {"sources": {f"dala-{l}": {"status": "pending", "blockers": ["producer_wait"]}
                                        for l in (*LANGUAGES, "pl", "sv", "is")}, "counts": {}, "evidence": {}}
            registered = apply_local_integration(registration, output / "integration.json")
            self.assertEqual(registered["counts"]["imported_conversations"], 12)
            self.assertEqual(registered["sources"]["dala-nn"]["status"], "integrated_unaudited")
            self.assertEqual(registered["sources"]["dala-pl"]["status"], "pending")
            cfg = root / "registry-config.json"
            registry_path = root / "registration.json"
            write_json(cfg, {"producer_root": str(producer),
                "current_run": "wiki/artifacts/six-language-expansion/current-run.json",
                "sources": {f"dala-{l}": {"language": l} for l in (*LANGUAGES, "pl", "sv", "is")}})
            argv = ["dala_refresh", "--config", str(cfg), "--output", str(registry_path)]
            with redirect_stdout(StringIO()):
                with patch("sys.argv", argv + ["--integration-manifest", str(output / "integration.json")]):
                    refresh_main()
                with patch("sys.argv", argv):
                    refresh_main()
            self.assertEqual(load(registry_path)["sources"]["dala-nb"]["status"], "integrated_unaudited")
            write_json(base / "scale_v1/late-review-exclusions.json", {"nb": [{"original_sha256": "new"}]})
            with self.assertRaisesRegex(ValueError, "late exclusions changed"):
                verify(output)


if __name__ == "__main__":
    unittest.main()
