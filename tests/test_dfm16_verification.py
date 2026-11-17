import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.dfm16_verification import calendar, isolated
from scripts.prepare_dfm16_atomic import key
from scripts.prepare_dfm16_verified_answers import adapt, LEGACY
from scripts.dfm16_answer_adapter import Answers


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.expected = {'0': dict(event_id=0, duration=30, min_time='10:00', max_time='16:00', constraint='before 11am')}
        self.events = [dict(event_id=0, event_name='Planning', start_time='10:00', duration=30)]

    def test_calendar_accept(self):
        self.assertTrue(calendar(json.dumps(self.events), self.expected))

    def test_calendar_missing_duplicate_and_extra(self):
        for events in ([], self.events*2, self.events+[dict(self.events[0], event_id=1)]):
            self.assertFalse(calendar(json.dumps(events), self.expected))

    def test_calendar_overlap(self):
        self.expected['1'] = dict(self.expected['0'], event_id=1)
        self.assertFalse(calendar(json.dumps(self.events+[dict(self.events[0], event_id=1)]), self.expected))

    def test_calendar_constraints(self):
        for constraint, start, passed in [('before 11am','10:45',False), ('after 2pm','14:00',True),
                ('at 3:30pm','15:30',True), ('at 3:30pm','15:00',False),
                ('between 10am and 12pm','11:30',True), ('between 10am and 12pm','11:45',False)]:
            self.expected['0']['constraint'] = constraint
            self.events[0]['start_time'] = start
            self.assertEqual(calendar(json.dumps(self.events), self.expected), passed)

    def test_calendar_duration_and_unknown_constraint(self):
        self.events[0]['duration'] = 15
        self.assertFalse(calendar(json.dumps(self.events), self.expected))
        self.events[0]['duration'] = 30
        self.expected['0']['constraint'] = 'whenever'
        with self.assertRaises(ValueError):
            calendar(json.dumps(self.events), self.expected)

    def test_atomic_normalization(self):
        self.assertEqual(key(' PersonX   eats.', 'xWant', ' Sleep '), key('personx eats', 'xWant', 'sleep'))
        self.assertNotEqual(key('a','xWant','b'), key('a','xNeed','b'))

    def test_synlogic_prompt_without_legacy_tags(self):
        row = adapt(dict(provenance=dict(repo_id='MiniMaxAI/SynLogic'), source=dict(
            prompt=[dict(role='user',content=LEGACY+'\nPuzzle')],data_source='sudoku',
            extra_info=dict(game_data_str=json.dumps(dict(question='Puzzle',answer='private'))))))
        self.assertNotIn('<think>', row['messages'][0]['content'])
        self.assertNotIn('private', row['messages'][0]['content'])

    def test_math_reference_private(self):
        row = adapt(dict(provenance=dict(repo_id='allenai/Dolci-Instruct-RL-7B'),source=dict(
            prompt='user: What is one plus one?', dataset=['math'],ground_truth=['2'])))
        self.assertEqual(row['verification'],dict(kind='math',answer='2'))
        self.assertIn('\\boxed',row['messages'][0]['content'])

    def test_answer_preserves_tools_no_thinking(self):
        adapter = Answers.__new__(Answers)
        payload = adapter.request(dict(messages=[],tools=[{'x':1}],max_tokens=123))
        self.assertEqual(payload['max_tokens'],123)
        self.assertFalse(payload['chat_template_kwargs']['enable_thinking'])
        self.assertNotIn('response_format',payload)


class IsolatedTests(unittest.TestCase):
    def test_code_pass_and_fail(self):
        self.assertTrue(isolated('code','def add(a,b): return a+b',dict(tests=['assert add(1,2)==3'])))
        self.assertFalse(isolated('code','def add(a,b): return 0',dict(tests=['assert add(1,2)==3'])))

    def test_repository_not_readable(self):
        path = str(Path('AGENTS.md').resolve())
        with self.assertRaisesRegex(ValueError, 'PermissionError'):
            isolated('code',f'open({path!r}).read()',dict(tests=['assert True']))

    def test_network_namespace(self):
        code = "import socket\ns=socket.socket()\ns.settimeout(1)\ns.connect(('1.1.1.1',443))"
        with self.assertRaisesRegex(ValueError, 'Network is unreachable'):
            isolated('code',code,dict(tests=['assert True']))

    def test_math_and_ifeval(self):
        self.assertTrue(isolated('math',r'\boxed{2}',dict(answer='2')))
        self.assertFalse(isolated('math',r'\boxed{3}',dict(answer='2')))
        spec = dict(constraints=[dict(instruction_id=['keywords:existence'],kwargs=[dict(keywords=['apple'])])])
        self.assertTrue(isolated('ifeval','apple',spec))
        self.assertFalse(isolated('ifeval','pear',spec))


if __name__ == '__main__':
    unittest.main()
