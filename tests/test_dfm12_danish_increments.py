import unittest
import argparse
from pathlib import Path
import tempfile
from unittest.mock import patch

from dfm12.danish_increments import fingerprint, language_label, lineage, policy_for, run
from dfm12.io import file_hash, load, write_json


class DanishIncrementTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(fingerprint([{"role": "user", "content": "caf\u00e9  x"}]),
                         fingerprint([{"role": "user", "content": "cafe\u0301\nx"}]))
        self.assertNotEqual(fingerprint([{"role": "user", "content": "A"}]),
                            fingerprint([{"role": "assistant", "content": "A"}]))

    def test_nontext_fails_closed(self):
        with self.assertRaises(ValueError):
            fingerprint([{"role": "user", "content": None}])

    def test_language(self):
        self.assertEqual(language_label(["dan", "eng"]), "da+en")
        self.assertEqual(language_label(["eng"]), "en")
        self.assertEqual(language_label(["deu", "fra", "ita"]), "de+fr+it")
        self.assertEqual(language_label(None), "und")

    def test_inherited_direct_route(self):
        evidence = {"files": {"data/wiki-instruct-da/x.parquet": {"revision": "pin"}},
                    "tasks": {"synquid_wiki_instruct_da__x": {"examples": 10}}}
        result = lineage("data/wiki-instruct-da/x.parquet", {"revision": "pin"}, evidence, [])
        self.assertEqual(result["route"], "synquid_wiki_instruct_da__")
        with self.assertRaises(ValueError):
            lineage("data/wiki-instruct-da/x.parquet", {"revision": "new"}, evidence, [])
        with self.assertRaises(ValueError):
            lineage("data/wiki-instruct-da/x.parquet", {"revision": "pin"}, evidence,
                    [{"prefix": "synquid_", "max_per_file": 0}])

    def test_policy_first_match(self):
        policy = [{"prefix": "x_y", "max_per_file": 0}, {"prefix": "x", "repeat": 1}]
        self.assertEqual(policy_for("x_y_z", policy)["max_per_file"], 0)

    def test_disk_index_and_resume(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            relative = "data/da-refusals/test.parquet"
            path = root / "downloads" / relative
            path.parent.mkdir(parents=True)
            messages = [{"role": "user", "content": "Hi"},
                        {"role": "assistant", "content": "Hello"}]
            pq.write_table(pa.Table.from_pylist([
                {"messages": messages, "language": ["eng"]},
                {"messages": messages, "language": ["eng"]}]), path)
            source = {"revision": "pin", "files": [relative]}
            registry = root / "registry.json"
            write_json(registry, {"sources": {"dyna-instruct-da-increments": source}})
            write_json(root / "inherited-evidence.json", {
                "files": {relative: {"revision": "pin", "etag": file_hash(path)}},
                "policy": "[]", "tasks": {"dfm_dyna_instruct__data__da-refusals__test": {"examples": 2}}})
            info = {"tokenizer_path": str(registry), "chat_template_path": str(registry)}
            args = argparse.Namespace(root=root, registry=registry, port=6977, host="unused",
                                      remote_root="unused", remote_python="unused")

            def fixture_load(path):
                if str(path) == "data/sampled_dfm11/metadata.json":
                    return {"tokenizer_info": info}
                return load(path)

            with patch("dfm12.danish_increments.load", side_effect=fixture_load), \
                    patch("dfm12.danish_increments.subprocess.run"), \
                    patch("builtins.print"):
                run(args)
                before = load(root / "receipt.json")
                run(args)
            self.assertEqual(before, load(root / "receipt.json"))
            self.assertEqual(before["input_rows"], 2)
            self.assertEqual(before["unique_normalized_conversations"], 1)
            self.assertEqual(before["candidate_conversations"], 0)
            self.assertFalse(before["full_dfm11_dedup_complete"])
            self.assertEqual((root / "candidates_unaudited.jsonl").stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
