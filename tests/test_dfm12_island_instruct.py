import hashlib
import unittest

from dfm12.cpu_island_instruct import adapt
from scripts.decontaminate_mimir_grounded_500k_exact import normalize_exact


class IslandAdapterTests(unittest.TestCase):
    def setUp(self):
        self.source = {"repo": "test", "revision": "pinned", "kind": "chat", "language": "is"}
        self.row = {"id": "one", "language": ["isl"], "source": "dynaword-reverse-instruct",
                    "messages": [{"role": "user", "content": "Question?"},
                                 {"role": "assistant", "content": "Answer."}]}

    def convert(self, hashes=None):
        return adapt(self.row, self.source, "train.parquet", 0, hashes or {})

    def test_full_multiturn_and_metadata(self):
        self.row["messages"] *= 2
        result = self.convert()
        self.assertEqual(result["messages"], self.row["messages"])
        self.assertEqual(len(result["messages"]), 4)
        self.assertEqual(result["audit_status"], "pending")
        self.assertNotIn("messages", result["provenance"]["upstream_metadata"])

    def test_language(self):
        for label in (None, ["isl", "eng"], ["fao"]):
            self.row["language"] = label
            with self.assertRaises(ValueError):
                self.convert()

    def test_identity_in_earlier_assistant(self):
        self.row["messages"][1]["content"] = "I am ChatGPT."
        self.row["messages"] += [{"role": "user", "content": "Continue"}, {"role": "assistant", "content": "Fine"}]
        with self.assertRaisesRegex(ValueError, "model_identity"):
            self.convert()

    def test_contamination(self):
        fp = hashlib.sha256(normalize_exact("Question?").encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, "exact_benchmark_overlap"):
            self.convert({fp: []})

    def test_ambiguous_model_names(self):
        self.row["messages"][1]["content"] = "Claude Monet was a painter."
        self.convert()
        for content in ("I am Claude.", "Eg eri Gemma.", "You are Mistral."):
            self.row["messages"][1]["content"] = content
            with self.assertRaisesRegex(ValueError, "model_identity"):
                self.convert()

    def test_format_and_tools(self):
        for text in ("[INST] Bad", "[TOOL_CALLS] Bad", "<|channel|> Bad", "broken\ufffd"):
            self.row["messages"][1]["content"] = text
            with self.assertRaises(ValueError):
                self.convert()
        self.row["messages"][1]["content"] = "Valid"
        self.row["tools"] = [{"name": "tool"}]
        with self.assertRaisesRegex(ValueError, "tool"):
            self.convert()

    def test_math_is_not_template(self):
        self.row["messages"][1]["content"] = "For all x, 0<|x-c|<delta."
        self.convert()

    def test_unknown_constituent(self):
        self.row["source"] = "benchmark"
        with self.assertRaisesRegex(ValueError, "unreviewed_constituent"):
            self.convert()


if __name__ == "__main__":
    unittest.main()
