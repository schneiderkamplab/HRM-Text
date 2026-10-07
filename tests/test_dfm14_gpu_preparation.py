import json
from pathlib import Path
import tempfile
import unittest
import asyncio

import httpx

from dfm12.io import file_hash, write_json
from dfm14.audit_protocol import validate_review
from dfm14.catalog import LANGUAGES, supplements
from dfm14.prepare import normalize
from dfm14.prepare_gpu import prepare_language, validate_candidate
from dfm14.transforms import transform
from dfm14.audit import recover_journal, review
from dfm14.institutional import blocks
from dfm14.generation_prepare import factory, reservoir


class GPUPreparationTests(unittest.TestCase):
    def test_synthetic_specs_are_isolated_and_native(self):
        from dfm12 import multilingual_tasks as tasks
        before = dict(tasks.LANGUAGES)
        source = dict(id="seed",text="Evidence. "*100,messages=[dict(role="user",content="Q"),dict(role="assistant",content="A")])
        for language in LANGUAGES:
            for family in tasks.QUOTAS:
                spec=factory(language,family,0,0,{language:[source],"openhermes":[source]},
                    dict(contract_version=4,cohort="test",quotas={f:100 for f in tasks.QUOTAS}))
                self.assertEqual(spec["language"], LANGUAGES[language])
                self.assertEqual(tasks.request(spec)["chat_template_kwargs"], {"enable_thinking":False})
        self.assertEqual(tasks.LANGUAGES,before)
        selected=reservoir([dict(id=str(i)) for i in range(100)],10)
        self.assertEqual(selected,reservoir([dict(id=str(i)) for i in reversed(range(100))],10))

    def test_xml_boundaries_are_not_invented(self):
        prose = "Useful institutional sentence with enough text for an intact source paragraph and its complete context. "
        xml = ("<html>" + "".join(f'<p id="{i}"><s lang="ga"><w>{text}</w></s></p>'
                for i,text in enumerate([prose*3,"...",prose*4])) + "</html>").encode()
        result = list(blocks(xml,"ga"))
        self.assertEqual([x[0] for x in result], [["0"],["2"]])

    def test_journal_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"journal.jsonl"
            path.write_bytes(b'{"audit_id":"a"}\n{"audit_id":')
            self.assertEqual(set(recover_journal(path,{"a"})), {"a"})
            self.assertEqual(path.read_bytes(), b'{"audit_id":"a"}\n')
            with self.assertRaises(ValueError):
                recover_journal(path,{"b"})

    def test_mock_http_audit(self):
        decision = dict(decision="accept",language_quality=3,instruction_coherence=3,training_value=3,reason="Good")
        async def run():
            def response(request):
                payload=json.loads(request.content)
                self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking":False})
                return httpx.Response(200,json=dict(choices=[dict(finish_reason="stop",message=dict(content=json.dumps(decision)))]))
            async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
                return await review(client,"http://fixture/v1","model",dict(id="x",audit_id="a",language="ga",
                    task="instruction",messages=[]),asyncio.Semaphore(1))
        result=asyncio.run(run())
        self.assertEqual(result["review"], decision)
        self.assertEqual(result["status"], "reviewed")

    def test_curated_supplements_cover_all_languages(self):
        self.assertEqual({x for s in supplements() for x in s["languages"]}, set(LANGUAGES))
        for s in supplements():
            self.assertTrue(all("train" in p for p in s["patterns"]))

    def test_eurlex_document_not_summary(self):
        source = next(s for s in supplements() if s["languages"] == ["ga"])
        row = normalize(dict(reference="abc " * 100, summary="not the target", celex_id="123"), source)
        self.assertEqual(row["text"], "abc " * 100)
        self.assertEqual(row["title"], "123")

    def test_transformation_reconstruction(self):
        text = "A sentence with enough words and enough letters for this transformation. " * 10
        row = transform(text, "ga", "span-filling", {})
        row["rendered_tokens"] = 150
        validate_candidate(row)
        row["messages"][-1]["content"] += "wrong"
        with self.assertRaisesRegex(ValueError, "reconstruction"):
            validate_candidate(row)

    def test_review_protocol(self):
        base = dict(decision="accept", language_quality=3, instruction_coherence=3, training_value=2, reason="Useful")
        self.assertEqual(validate_review(base), base)
        for changes in (dict(language_quality=True), dict(training_value=1), dict(reason=""), dict(decision="maybe")):
            with self.assertRaises(ValueError):
                validate_review(dict(base, **changes))

    def test_dedup_hashes_resume_and_disjoint_ids(self):
        from tokenizers import Tokenizer, models, pre_tokenizers
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tok = Tokenizer(models.WordLevel({"[UNK]":0}, unk_token="[UNK]"))
            tok.pre_tokenizer = pre_tokenizers.Whitespace()
            tok.save(str(root / "tokenizer.json"))
            row = dict(id="one", language="ga", task="instruction", messages=[
                dict(role="user",content="Question"),dict(role="assistant",content="Answer")],
                provenance=dict(repo="fixture"), rendered_tokens=4,
                training_ready=False, admission_authorized=False)
            path = root / "input.jsonl"
            path.write_text("\n".join(json.dumps(x) for x in [row, row, dict(row, id="two",
                messages=[dict(role="user",content="Another"),dict(role="assistant",content="Answer")])]))
            job = dict(language="ga", output=str(root / "output"), tokenizer=str(root / "tokenizer.json"),
                inputs=[dict(path=str(path), sha256=file_hash(path))], chunk_rows=1)
            first = prepare_language(job)
            self.assertEqual(first["counts"]["duplicate"], 1)
            self.assertEqual(first["counts"]["instruction"], 2)
            self.assertEqual(prepare_language(job), first)
            ids = [json.loads((root/"output"/c["input"]).read_text())["audit_id"] for c in first["chunks"]]
            self.assertEqual(len(set(ids)), 2)
            (root / "output" / first["chunks"][0]["input"]).write_text("changed")
            with self.assertRaisesRegex(ValueError, "Changed completed"):
                prepare_language(job)


if __name__ == "__main__":
    unittest.main()
