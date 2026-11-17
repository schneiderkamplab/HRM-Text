import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dfm12.io import load, write_json
from scripts.run_dfm16_context_calibration import reuse_votes, BoundedOdin


class ImportTests(unittest.TestCase):
    def test_provider_token_metadata_bound(self):
        body={'choices':[{'finish_reason':'stop','message':{'content':'accept'}}],
              'usage':{'completion_tokens':2,'completion_tokens_details':{'reasoning_tokens':1}}}
        self.assertEqual(BoundedOdin.parse_review(body),{'decision':'accept'})
        body['usage']['completion_tokens_details']['reasoning_tokens']=2
        with self.assertRaises(ValueError):BoundedOdin.parse_review(body)
        body['usage']['completion_tokens_details']['reasoning_tokens']=0
        body['usage']['completion_tokens']=33
        with self.assertRaises(ValueError):BoundedOdin.parse_review(body)

    def test_preserve_upstream_lineage_and_idempotent_local_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);old=base/'old';new=base/'new'
            for root in (old,new):
                write_json(root/'design.json',dict(rubric='same',criteria={},models={},retries=1))
                (root/'development').mkdir(exist_ok=True)
                (root/'development/checks.jsonl').write_text('same checks\n')
            for name in ('qwen27b','flash'):
                source=old/'development/votes'/name
                write_json(source/'audit/pipeline/state.json',dict(phase='complete'))
                write_json(source/'reuse.json',dict(source='ancestor',complete=True))
                write_json(new/'development/votes'/name/'reuse.json',dict(source='ancestor',complete=True))
            with patch('scripts.run_dfm16_context_calibration.audited_records',return_value=[]):
                reuse_votes(new,old)
                for name in ('qwen27b','flash'):
                    target=new/'development/votes'/name
                    self.assertEqual(load(target/'reuse.json')['source'],str(old/'development/votes'/name))
                    self.assertEqual(load(target/'upstream-reuse.json')['source'],'ancestor')
                reuse_votes(new,old)
            self.assertFalse((new/'development/votes/odin').exists())


if __name__=='__main__':unittest.main()
