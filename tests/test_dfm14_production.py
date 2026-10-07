import json
from pathlib import Path
import tempfile
import unittest

from dfm14.production import plan, recover, knowledge_request, restart_contract


class ProductionTests(unittest.TestCase):
    def test_targets_and_no_overlapping_slots(self):
        groups,jobs=plan()
        self.assertEqual(sum(g['target'] for g in groups),1270000)
        for group in groups:
            chunks=[j for j in jobs if (j['language'],j['family'])==(group['language'],group['family'])]
            self.assertEqual(chunks[0]['start'],0)
            self.assertEqual(chunks[-1]['end'],group['target'])
            self.assertTrue(all(a['end']==b['start'] for a,b in zip(chunks,chunks[1:])))

    def test_journal_partial_tail_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'attempts.jsonl'
            line=json.dumps(dict(slot=0,attempt=0,status='accepted'))+'\n'
            p.write_text(line+'{"slot":')
            self.assertEqual(len(recover(p)),1)
            self.assertEqual(p.read_text(),line)
            p.write_text(line*2)
            with self.assertRaises(ValueError):recover(p)

    def test_knowledge_prompt_contract(self):
        payload,schema=knowledge_request(dict(family='math',source={}))
        self.assertIn('\\boxed{',payload['messages'][0]['content'])
        self.assertFalse(payload['chat_template_kwargs']['enable_thinking'])
        self.assertEqual(schema['required'],['user','assistant'])

    def test_restart_preserves_accepted_bytes_and_archives_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'jobs'/'example';folder.mkdir(parents=True)
            accepted=json.dumps(dict(slot=0,attempt=5,status='accepted',candidate={'text':'keep'}))+'\n'
            failed=json.dumps(dict(slot=1,attempt=0,status='error'))+'\n'
            (folder/'attempts.jsonl').write_text(accepted+failed)
            (folder/'receipt.json').write_text('{}')
            (root/'manifest.json').write_text('{}')
            restart_contract(root)
            manifest=json.loads((root/'manifest.json').read_text())
            self.assertEqual(manifest['attempts_per_slot'],2)
            self.assertEqual(manifest['retained_accepted'],1)
            self.assertEqual((folder/'attempts.jsonl').read_text(),accepted)
            self.assertEqual((Path(manifest['restart_archive'])/'jobs/example/attempts.jsonl').read_text(),accepted+failed)
            self.assertFalse((folder/'receipt.json').exists())


if __name__=='__main__':unittest.main()
