import json
from pathlib import Path
import tempfile
import unittest

import httpx

from audit_pipeline.runtime import run
from dfm12.io import file_hash, write_json, rows
from scripts.dfm16_story_calibration import (
    FocusedAudit, RepairAudit, aggregate, bound, checks, deterministic,
    immutable, import_labels, metrics, policy_vote, sample_validation,
    immutable_rows, RUBRIC,
)


def parent():
    return dict(id='p', seed='An intentionally misspelled story.', language='en', task='revision',
        provenance={'source_family':'p'}, messages=[
            {'role':'user','content':'Correct this deliberately misspelled text: teh cat.'},
            {'role':'assistant','content':'The cat.'},
            {'role':'user','content':'Now replace the cat with a dog.'},
            {'role':'assistant','content':'The dog.'}])


def body(text, finish='stop'):
    return {'choices':[{'finish_reason':finish,'message':{'content':text}}]}


class CalibrationTests(unittest.TestCase):
    def test_revision_full_context_and_intentional_error_rules(self):
        p=parent()
        last=list(checks(p))[-1]
        self.assertEqual(last['evidence']['conversation'],p['messages'])
        self.assertIn('Intentionally flawed',RUBRIC)
        self.assertEqual(deterministic(p),[])
        self.assertEqual(len([c for c in checks(p) if '/user/' in c['id']]),6)

    def test_preservation_undo_and_ambiguous_constraints(self):
        p=parent()
        p['trusted_constraints']=[{'kind':'exact','turn':3,'reference_turn':1},
            {'kind':'sentences','turn':3,'ambiguous':True}]
        self.assertEqual([c['status'] for c in deterministic(p)],['fail','semantic'])
        p['messages'][3]['content']='The cat.'
        self.assertEqual(deterministic(p)[0]['status'],'pass')
        p['trusted_constraints']=[{'kind':'paragraphs','turn':3,'reference_turn':1,'preserve':[1]}]
        p['messages'][1]['content']='A\n\nB'
        p['messages'][3]['content']='C\n\nB'
        self.assertEqual(deterministic(p)[0]['status'],'pass')
        p['messages'][3]['content']='C\n\nChanged'
        self.assertEqual(deterministic(p)[0]['status'],'fail')

    def test_multilingual_sentence_counts(self):
        for content in ('यह पहली पंक्ति है। यह दूसरी पंक्ति है।', '一文です。二文です。', 'First sentence. Second sentence.'):
            p=parent();p['messages'][1]['content']=content
            p['trusted_constraints']=[{'kind':'sentences','turn':1,'min':2,'max':2,'segmentation':'terminal-punctuation-v1'}]
            self.assertEqual(deterministic(p)[0]['status'],'pass')

    def test_repair_only_flagged_user_and_seed(self):
        p=parent();candidate={'messages':json.loads(json.dumps(p['messages'])), 'seed':p['seed']}
        candidate['messages'][0]['content']='Correct this deliberately misspelled text: teh dog.'
        with self.assertRaises(ValueError):
            RepairAudit.decode(body(json.dumps(candidate)),{'original':p,'allowed_turns':[3]})
        repaired=RepairAudit.decode(body(json.dumps(candidate)),{'original':p,'allowed_turns':[0]})
        self.assertNotEqual(repaired['messages'][0],p['messages'][0])
        candidate['seed']='Changed seed'
        with self.assertRaises(ValueError):
            RepairAudit.decode(body(json.dumps(candidate)),{'original':p,'allowed_turns':[0]})

    def test_odin_provider_controls(self):
        a=FocusedAudit(Path('.'),Path('.'),'https://api.odincore.ai/v1')
        a.model='odin-2-large'
        payload=a.prepare(next(checks(parent())))
        self.assertEqual(payload['reasoning_effort'],'none')
        self.assertEqual(payload['max_completion_tokens'],32)
        self.assertFalse(payload['include_reasoning'])
        self.assertNotIn('max_tokens',payload)
        self.assertNotIn('chat_template_kwargs',payload)

    def test_invalid_verdicts_and_thinking(self):
        for value in ('yes','accept.','{"decision":"accept"}','Accept'):
            with self.assertRaises(ValueError): FocusedAudit.parse_review(body(value))
        with self.assertRaises(ValueError): FocusedAudit.parse_review(body('accept','length'))
        b=body('accept'); b['choices'][0]['message']['reasoning']='hidden'
        with self.assertRaises(ValueError): FocusedAudit.parse_review(b)

    def test_fixed_policies_missing_and_disagreement(self):
        votes={'qwen27b':'reject','flash':'accept','odin':'accept'}
        self.assertEqual(policy_vote(votes,'majority'),'accept')
        self.assertEqual(policy_vote(votes,'odin_confirmation'),'accept')
        self.assertEqual(policy_vote(votes,'qwen_odin_unanimity'),'unresolved')
        self.assertEqual(policy_vote({'qwen27b':'accept'},'majority'),'unresolved')
        self.assertEqual(aggregate(['accept','unresolved']),'unresolved')

    def test_metrics_are_conversation_level_and_unresolved_withheld(self):
        m=metrics([{'label':'clear','decision':'unresolved'}, {'label':'bad','decision':'accept'},
                   {'label':'borderline','decision':'reject'}])
        self.assertEqual(m['clean_withholding']['rate'],1)
        self.assertEqual(m['false_acceptance']['rate'],1)
        self.assertEqual(m['accepted_contamination']['rate'],1)
        self.assertFalse(m['demonstrated'])
        self.assertAlmostEqual(bound(0,100),1-.05**.01)
        self.assertIsNone(bound(0,0))

    def test_repair_preserves_requests_and_original(self):
        p=parent(); candidate={'messages':json.loads(json.dumps(p['messages']))}
        candidate['messages'][3]['content']='The dog slept.'
        repaired=RepairAudit.decode(body(json.dumps(candidate)),{'original':p})
        self.assertEqual(p['messages'][3]['content'],'The dog.')
        self.assertNotEqual(repaired['messages'],p['messages'])
        candidate['messages'][0]['content']='Changed request'
        with self.assertRaises(ValueError): RepairAudit.decode(body(json.dumps(candidate)),{'original':p})
        self.assertIsNone(RepairAudit.decode(body('unrepairable'),{'original':p}))
        self.assertIn('original_conversation',list(checks(repaired,p))[0]['evidence'])

    def test_immutability_and_label_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp)
            immutable(stage/'x.json',{'x':1}); immutable(stage/'x.json',{'x':1})
            with self.assertRaises(ValueError): immutable(stage/'x.json',{'x':2})
            immutable_rows(stage/'inputs.jsonl',[parent()])
            immutable_rows(stage/'incoming.jsonl',[{'id':'p','label':'clear','note':'read all turns','reviewer':'assistant-manual','blind':True}])
            import_labels(stage,stage/'incoming.jsonl')
            self.assertTrue((stage/'labels-receipt.json').exists())

    def test_seed_family_exclusion_and_shortfall(self):
        p=parent()
        with self.assertRaisesRegex(ValueError,'Insufficient untouched'):
            sample_validation([dict(p,id='variant')],[p])
        pool=[]
        for language in ('da','en','hi','ja'):
            for task in ('creative','qa','revision','rewrite','summary'):
                for i in range(40):
                    key=f'{language}-{task}-{i}'
                    pool.append(dict(id=key,language=language,task=task,provenance={'source_family':key}))
        selected=sample_validation(pool,[])
        self.assertEqual(len(selected),800)
        self.assertEqual(selected,sample_validation(pool,[]))


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_overflow_invalid_retry_restart_deduplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=list(checks(parent()))[:2]
            immutable_rows(root/'input.jsonl',source)
            write_json(root/'manifest.json',{'chunks':[{'job_id':'c','input':'input.jsonl',
                'rows':2,'sha256':file_hash(root/'input.jsonl'),'task':'test'}]})
            calls=[]
            async def handler(request):
                if request.url.path.endswith('/models'):
                    return httpx.Response(200,json={'data':[{'id':'test'}]})
                calls.append(request)
                # Context overflow is operationally unresolved, never a rejection.
                if len(calls)<=2: return httpx.Response(400,json={'error':'context overflow'})
                return httpx.Response(200,json=body('accept.'))
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                a=FocusedAudit(root,root/'audit','http://test/v1'); a.model='test'
                await run(a,'http://test/v1',1,client=client,signals=False)
                results=list(rows(root/'audit/c/results.jsonl'))
                self.assertEqual(len(calls),4)
                self.assertTrue(all(r['attempt']==2 and 'review' not in r for r in results))
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                a=FocusedAudit(root,root/'audit','http://test/v1'); a.model='test'
                await run(a,'http://test/v1',1,client=client,signals=False)
                self.assertEqual(len(calls),4)
                self.assertEqual(len(list(rows(root/'audit/c/results.jsonl'))),2)


if __name__=='__main__': unittest.main()
