import unittest
import tempfile
from pathlib import Path

from dfm14.catalog import LANGUAGES, sources
from dfm14.prepare import HELDOUT, normalize, source_rows
from dfm14.transforms import PROMPTS, TASKS, transform


class PreparationTests(unittest.TestCase):
    def test_grounding_registry_is_curated(self):
        self.assertEqual({s["repo"] for s in sources() if s["kind"] == "document"}, {
            "wikimedia/wikipedia", "danish-foundation-models/faroese-dynaword",
            "SlayerLab/polish-dynaword", "MatinaAI/matina_persian_text_corpus"})

    def test_all_languages_have_instruction_and_document_candidates(self):
        for language in LANGUAGES:
            for kind in ("instruction", "document"):
                self.assertTrue(any(s["kind"] == kind and language in s["languages"] for s in sources()))

    def test_complete_chat_preserved(self):
        source = dict(languages=["ru"], kind="instruction")
        messages = [dict(role="system", content="Be useful."), dict(role="user", content="Hi"),
                    dict(role="assistant", content="Hello"), dict(role="user", content="Again"),
                    dict(role="assistant", content="Hello again")]
        self.assertEqual(normalize(dict(messages=messages), source)["messages"], messages)

    def test_language_filter_is_required(self):
        source = dict(languages=["hi"], kind="instruction", language_field="language")
        with self.assertRaisesRegex(ValueError, "missing_language"):
            normalize(dict(instruction="q", output="a"), source)
        self.assertEqual(normalize(dict(language="hin", inputs="q", targets="a"), source)["language"], "hi")

    def test_tools_and_reasoning_not_silently_discarded(self):
        source = dict(languages=["en"], kind="instruction")
        for row in [dict(tools=[{}]), dict(messages=[dict(role="assistant", tool_calls=[{}])]),
                    dict(instruction="q", output="<think>r</think>a")]:
            with self.assertRaisesRegex(ValueError, "requires_native"):
                normalize(row, source)

    def test_heldout_paths(self):
        self.assertTrue(HELDOUT.search("data/test-0000.parquet"))
        self.assertFalse(HELDOUT.search("data/train-0000.parquet"))

    def test_json_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            path.write_text('{"x": 1}\n{"x": 2}')
            self.assertEqual(list(source_rows(path)), [{"x": 1}, {"x": 2}])
            path.write_text('[{"x": 1}, {"x": 2}]')
            self.assertEqual(list(source_rows(path)), [{"x": 1}, {"x": 2}])

    def test_korean_roles(self):
        record = normalize(dict(text="<sys>System\n<usr>Question\n<bot>Answer"),
            dict(repo="heegyu/open-korean-instructions", kind="instruction", languages=["ko"]))
        self.assertEqual([m["role"] for m in record["messages"]], ["system", "user", "assistant"])

    def test_turkish_columns(self):
        record = normalize({"talimat":"Question", " giriş":"Context", " çıktı":"Answer"},
            dict(kind="instruction", languages=["tr"], field_mapping={"talimat":"instruction", "giriş":"input", "çıktı":"output"}))
        self.assertEqual(record["messages"][0]["content"], "Question\n\nContext")

    def test_transform_targets(self):
        self.assertEqual(set(PROMPTS), set(LANGUAGES) | {'fo', 'pl', 'fa'})
        for language, text in [("zh", "第一句话。第二句话。第三句话。第四句话。第五句话。第六句话。"),
                               ("hi", "यह एक छोटा वाक्य है। यहाँ दूसरा वाक्य है। अंत में तीसरा वाक्य है।")]:
            for task in TASKS[:3]:
                result = transform(text, language, task, {})
                answer = result["messages"][-1]["content"]
                if task == "denoising":
                    self.assertEqual(answer, text)
                else:
                    bounds = result["audit_context"]["transformation"]
                    self.assertEqual(text[bounds["start"]:bounds["end"]], answer)
        with self.assertRaisesRegex(ValueError, "paragraphs"):
            transform("one paragraph", "ru", "paragraph-reordering", {})


if __name__ == "__main__":
    unittest.main()
