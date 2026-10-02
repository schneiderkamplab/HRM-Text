import json
from pathlib import Path
import tempfile
import unittest

from dfm12.dala_refresh import TERMINAL, contained, inspect, validate_final
from dfm12.io import file_hash, write_json


class DaLARefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run = "recovery_v1"
        self.base = self.root / "wiki/artifacts/six-language-expansion"
        self.cfg = {"current_run": "wiki/artifacts/six-language-expansion/current-run.json",
                    "sources": {"dala-nb": {"language": "nb", "dataset_name": "local-nb"}}}
        write_json(self.base / "current-run.json", {
            "run_id": self.run, "finalization": str((self.base / self.run / "finalization.json").relative_to(self.root))})
        self.final = {"run_id": self.run, "status": "waiting_for_builds", "language_runs": {"nb": self.run}}
        self.publish_final()

    def publish_final(self):
        write_json(self.base / self.run / "finalization.json", self.final)

    def raw_build(self):
        output = self.root / "la_output/nb_dynaword_recovery_v1"
        write_json(output / "manifest.json", {"schema_version": "2", "language": "nb",
            "verification": {"pairs": 10}, "splits": {"train": {"pairs": 8, "acceptability_rows": 16, "correction_rows": 16}}})
        write_json(self.base / self.run / "nb-status.json", {
            "language": "nb", "exit_code": 0, "output": str(output.relative_to(self.root)),
            "status": "candidate_build_complete_requires_final_audit"})
        return output

    def final_build(self):
        self.raw_build()
        output = self.root / "la_output/six_language_candidates_recovery_v1/nb"
        manifest = {"schema_version": "2", "language": "nb", "verification": {"pairs": 10, "document_split_isolation": True},
                    "source_snapshots": [{"revision": "pinned"}], "cross_dataset_isolation": {"method": "exact/near"},
                    "late_agent_review": {"sha256": "fixture"}, "artifacts": {}}
        files = ["documents.jsonl", "rules.json"]
        for split in ("train", "validation", "test"):
            files.extend(f"{split}/{name}.jsonl" for name in ("pairs", "acceptability_it", "correction_it"))
        for relative in files:
            path = output / relative
            write_json(path, {})
            manifest["artifacts"][relative] = {"bytes": path.stat().st_size, "sha256": file_hash(path)}
        write_json(output / "manifest.json", manifest)
        isolation = {"nb": {"output": str(output.relative_to(self.root)), "retained_pairs": 10}}
        write_json(output.parent / "isolation.json", isolation)
        self.final.update(status=TERMINAL, outputs={"nb": str(output.relative_to(self.root))},
                          cross_dataset_isolation=str((output.parent / "isolation.json").relative_to(self.root)))
        self.publish_final()
        return output

    def test_pending_raw_build_never_importable(self):
        self.raw_build()
        result = inspect(self.cfg, self.root)
        source = result["sources"]["dala-nb"]
        self.assertEqual(source["raw_build_not_importable"]["pairs"], 10)
        self.assertEqual(source["status"], "pending")
        self.assertEqual(source["train_files"], [])
        self.assertFalse(source["import_enabled"])
        self.assertFalse(result["policy"]["license_hold"])

    def test_missing_completion_ignores_old_run(self):
        write_json(self.base / "scale_v1/nb-status.json", {"exit_code": 0})
        source = inspect(self.cfg, self.root)["sources"]["dala-nb"]
        self.assertIn("current_build_completion_receipt_missing", source["blockers"])

    def test_final_checksum_verified_train_only_registration(self):
        self.final_build()
        result = inspect(self.cfg, self.root)
        source = result["sources"]["dala-nb"]
        self.assertEqual(result["counts"]["ready_sources"], 1)
        self.assertEqual(len(source["train_files"]), 2)
        self.assertTrue(all("/train/" in f for f in source["train_files"]))
        self.assertEqual(result["counts"]["imported_conversations"], 0)
        self.assertEqual(source["audit_status"], "unaudited")

    def test_changed_heldout_artifact_blocks_registration(self):
        output = self.final_build()
        write_json(output / "test/pairs.jsonl", {"modified": True})
        source = inspect(self.cfg, self.root)["sources"]["dala-nb"]
        self.assertEqual(source["status"], "pending")
        self.assertEqual(source["train_files"], [])
        self.assertIn("checksum/size mismatch", " ".join(source["blockers"]))

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            contained(self.root, "../outside")

    def test_smoke_is_not_production(self):
        output = self.final_build()
        with self.assertRaises(ValueError):
            validate_final(self.root, "la_output/six_language_isolation_smoke/nb", "nb", {}, self.run)

    def test_invalid_json_is_pending(self):
        (self.base / self.run / "finalization.json").write_text("{")
        self.assertEqual(inspect(self.cfg, self.root)["counts"]["ready_sources"], 0)

    def test_wrong_standard_not_relabelled(self):
        output = self.raw_build()
        manifest = json.loads((output / "manifest.json").read_text())
        manifest["language"] = "nn"
        write_json(output / "manifest.json", manifest)
        self.assertEqual(inspect(self.cfg, self.root)["counts"]["ready_sources"], 0)
        source = inspect(self.cfg, self.root)["sources"]["dala-nb"]
        self.assertIn("Wrong language", " ".join(source["blockers"]))


if __name__ == "__main__":
    unittest.main()
