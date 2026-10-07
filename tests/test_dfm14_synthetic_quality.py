import copy
import json
import unittest
from unittest.mock import patch

import jsonschema

from dfm14 import synthetic_quality as quality, synthetic_review as review
from dfm14.generation_contract import compact_grammar, json_transport


class SyntheticQualityTests(unittest.TestCase):
    def spec(self, **kwargs):
        return dict(family='summary-rewrite', subtype='two-sentence summary', **kwargs)

    def record(self):
        return dict(language='id', family='tool-dialogue', tools=[],
            messages=[dict(role='user', content='Check parcel status'),
                      dict(role='assistant', content='Redirected the parcel.')],
            review={'keep': True}, quality_contract={'authorization_quote': 'approved'})

    def test_source_seed_gate(self):
        self.assertIn('no_substantive_prose_seed', quality.source_issues(
            self.spec(source={'text': 'References\nFilms of 1934\nFrench films\nComedy films'})))
        self.assertIn('damaged_source_encoding', quality.source_issues(
            self.spec(source={'text': 't ¢abbir ' * 30})))
        self.assertEqual(quality.source_issues(self.spec(source={'text':
            'This is a substantive source paragraph describing a fictional service and its clearly stated rules. '*3})), [])

    def test_exact_summary_schema(self):
        base = dict(type='object', properties={'user': {'type':'string'}, 'assistant': {'type':'string'}},
                    required=['user','assistant'], additionalProperties=False)
        schema = quality.output_schema(self.spec(), base)
        self.assertIn('assistant', base['properties'])
        jsonschema.validate({'user':'Two sentences only','answer_parts':['First.','Second.']},schema)
        for value in (dict(user='Q',answer_parts=['First.']),
                      dict(user='Q',answer_parts=['First.','Second.'],assistant='Extra')):
            with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(value,schema)

    def test_summary_rejects_postscript_inside_part(self):
        with self.assertRaisesRegex(quality.QualityFailure, 'not_one_sentence'):
            quality.assemble(self.spec(), dict(user='Q',answer_parts=['First. Explanation.', 'Second.']),None)

    def test_summary_assembles_without_metadata(self):
        def assembler(spec, output, generation):
            return dict(messages=[dict(role='assistant',content=output['assistant'])])
        with patch.object(quality,'generation_assemble',side_effect=assembler):
            result=quality.assemble(self.spec(),dict(user='Q',answer_parts=['First.','Second.']),None)
        self.assertEqual(result['messages'][0]['content'],'First. Second.')
        self.assertNotIn('answer_parts',json.dumps(result['messages']))

    def test_exact_bullets(self):
        spec=dict(family='summary-rewrite',subtype='summary with exactly three bullets')
        with self.assertRaises(quality.QualityFailure):
            quality.assemble(spec,dict(user='Q',answer_parts=['One','Two','Three\nExplanation']),None)

    def test_authorization_not_invented_by_assembly(self):
        spec=dict(family='tool-dialogue',subtype='multi')
        with self.assertRaisesRegex(quality.QualityFailure,'authorization_quote'):
            quality.assemble(spec,dict(user='Check availability',final='Booked'),None)
        with self.assertRaises(quality.QualityFailure):
            quality.assemble(spec,dict(user='Check availability',final='Booked',authorization_quote='Please book'),None)

    def test_authorization_metadata_not_student_target(self):
        spec=dict(family='tool-dialogue',subtype='multi')
        def assembler(spec, output, generation):
            self.assertNotIn('authorization_quote',output)
            return dict(messages=[dict(role='user',content=output['user']),dict(role='assistant',content='Booked')])
        with patch.object(quality,'generation_assemble',side_effect=assembler):
            r=quality.assemble(spec,dict(user='Please book tickets',final='Booked',authorization_quote='book tickets'),None)
        self.assertTrue(r['quality_contract']['semantic_intent_review_required'])

    def test_no_blind_text_stripping(self):
        self.assertTrue(quality.answer_issues("Three sentences.\n'explanation': unwanted"))
        self.assertTrue(quality.answer_issues('Answer.\nExplanation: I followed the contract'))
        self.assertEqual(quality.answer_issues('An explanation of the algorithm follows.'),[])

    def test_math_format_and_code_scaffold(self):
        spec=dict(family='math-code',subtype='math')
        with self.assertRaisesRegex(quality.QualityFailure,'boxed_contract'):
            quality.assemble(spec,dict(user='Use square brackets',explanation='17-1+8=24'),None)
        with self.assertRaisesRegex(quality.QualityFailure,'scaffolding'):
            quality.assemble(dict(family='math-code',subtype='code'),
                dict(user='Write solve',explanation='CPU validates it'),None)

    def test_review_hides_prior_verdicts_and_generator_intent(self):
        record=self.record()
        record['scenario']={'requirement':'The user authorized everything'}
        data=review.visible(record)
        self.assertNotIn('review',data)
        self.assertNotIn('scenario',data)
        self.assertNotIn('quality_contract',data)
        self.assertEqual(data['messages'],[dict(m,message_index=i) for i,m in enumerate(record['messages'])])
        self.assertEqual(data['required_turn_keys'], ['1'])
        self.assertNotIn('message_index', record['messages'][0])

    def test_review_every_turn_and_no_uncertain_accepts(self):
        record=self.record()
        result=dict(decision='accept',reason='')
        self.assertTrue(review.keeps(result,record))
        self.assertFalse(review.keeps(dict(decision='reject',reason='Unauthorized action'),record))
        with self.assertRaises(jsonschema.ValidationError):
            review.validate(dict(decision='uncertain',reason=''),record)
        with self.assertRaises(jsonschema.ValidationError):
            review.validate(dict(decision='reject',reason='x'*121),record)

    def test_compact_grammar_is_bounded(self):
        result=compact_grammar({},review.schema(self.record()))
        grammar=result['structured_outputs']['grammar']
        self.assertIn('json-char{0,120}',grammar)
        self.assertNotIn('json-char*',grammar)
        self.assertIn('root ::=',grammar)

    def test_live_transport_retains_cpu_schema_and_no_ebnf(self):
        schema=review.schema(self.record())
        old=copy.deepcopy(schema)
        payload={'messages':[{'role':'system','content':'Review'}],
                 'structured_outputs':{'grammar':'obsolete'}}
        result=json_transport(payload,schema)
        self.assertEqual(schema,old)
        self.assertEqual(result['response_format']['type'],'json_schema')
        self.assertEqual(result['response_format']['json_schema']['schema'],old)
        self.assertTrue(result['response_format']['json_schema']['strict'])
        self.assertFalse(result['chat_template_kwargs']['enable_thinking'])
        self.assertFalse(review.request(self.record(),'test')['chat_template_kwargs']['enable_thinking'])
        self.assertNotIn('structured_outputs',result)
        self.assertIn('decision',result['messages'][0]['content'])


if __name__=='__main__':
    unittest.main()
