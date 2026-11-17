import json
import unittest
from pathlib import Path
from scripts.dfm16_role_pilot import controls, RoleAudit, PilotGenerate

class RolePilotTests(unittest.TestCase):
    def test_pairs_and_blind_payload(self):
        bank=list(controls());self.assertEqual(len(bank),56)
        for language in ('en','da','hi','ja'):
            self.assertEqual(sum(r['language']==language and r['label']=='clear' for r in bank),7)
        audit=RoleAudit(Path('/tmp/unused'),Path('/tmp/unused-out'),'http://localhost')
        audit.model='odin-2-large'
        for r in bank:
            payload=audit.prepare(dict(r,variant='role'))
            evidence=json.loads(payload['messages'][1]['content'])
            self.assertNotIn('label',evidence);self.assertNotIn('reviewer',evidence)
            self.assertEqual(payload['reasoning_effort'],'none');self.assertEqual(payload['max_completion_tokens'],32)
            self.assertNotIn('response_format',payload)
    def test_correction_and_revision_scopes(self):
        bank=list(controls())
        for r in bank:
            if r['criterion']=='answer_language':self.assertIn('correction',r['evidence']['obligation'])
            if r['id'].split('-')[1]=='5':self.assertIn('superseded',r['evidence']['obligation'])
    def test_first_invalid_contract_candidate_preserved(self):
        body={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'messages':[{'role':'user','content':'Write 80-120 words.'},{'role':'assistant','content':'Too short.'}]})}}]}
        row={'revisions':0,'task':'creative','language':'en','specification':{'length_words':'80-120'}}
        candidate,cpu=PilotGenerate.decode(body,row)
        self.assertEqual(cpu['status'],'fail');self.assertEqual(candidate['messages'][1]['content'],'Too short.')
    def test_noop_preservation_pair(self):
        for r in controls():
            if r['id'].split('-')[1]=='6':
                a=r['evidence']['conversation'][1]['content'].split('\n\n')[1]
                b=r['evidence']['conversation'][3]['content'].split('\n\n')[1]
                self.assertEqual(a==b,r['label']=='clear')
