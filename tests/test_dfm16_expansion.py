import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.dfm16_story_adapter import decode_candidate, generation_payload
from scripts.prepare_dfm16_expansion import convert_row, normalize_schema, swe_messages
from dfm14.native_instructions import convert


class ExpansionTests(unittest.TestCase):
    def test_balanced_targets(self):
        config = json.loads(Path('config/dfm16_expansion.json').read_text())
        self.assertFalse(config['sampling_authorized'])
        stories = config['simple_stories']
        self.assertEqual(sum(stories['accepted_targets'].values()), 300000)
        self.assertEqual(sum(stories['task_percentages'].values()), 100)
        self.assertEqual(stories['accepted_targets'], dict(en=200000, da=50000, ja=25000, hi=25000))

    def test_generation_no_thinking_or_grammar(self):
        payload = generation_payload(dict(language='da', task='revision', revisions=2,
                                          variant=0, seed='A story.'), 'teacher')
        self.assertEqual(payload['chat_template_kwargs'], dict(enable_thinking=False))
        self.assertNotIn('response_format', payload)
        self.assertNotIn('structured_outputs', payload)

    def test_story_turn_validation(self):
        row = dict(language='en', task='summary', id='x', provenance={})
        messages = [dict(role='user', content='Summarize this story.'), dict(role='assistant', content='Summary.')]
        body = dict(choices=[dict(finish_reason='stop', message=dict(content=json.dumps(dict(messages=messages))))])
        with patch('scripts.dfm16_story_adapter.count', return_value=50):
            self.assertEqual(decode_candidate(body, row, None)['rendered_tokens'], 50)
            row['revisions'] = 2
            with self.assertRaisesRegex(ValueError, 'turn_count'):
                decode_candidate(body, row, None)

    def test_native_reasoning(self):
        row = dict(conversations=[dict(from_='unused')])
        row['conversations'] = [{'from':'human', 'value':'Solve.'}, {'from':'gpt', 'value':'<think>Reason.</think>Answer.'}]
        result = convert_row('open-thoughts/OpenThoughts3-1.2M', row)
        self.assertEqual(result['messages'][-1]['reasoning_content'], 'Reason.')
        self.assertEqual(result['messages'][-1]['content'], 'Answer.')

    def test_reference_action_and_terminal_calls(self):
        tool = dict(type='function', name='lookup', parameters=dict(type='object', properties={}))
        row = dict(responses_create_params=dict(input=[dict(role='user', content='Look up.')], tools=[tool]),
                   expected_action=dict(type='function_call', name='lookup', arguments='{}'))
        result = convert_row('nvidia/example', row)
        self.assertEqual(result['messages'][-1]['tool_calls'][0]['function']['arguments'], {})
        with self.assertRaisesRegex(ValueError, 'unresolved_terminal'):
            convert(dict(messages=result['messages'], tools=result['tools']))

    def test_missing_answer_not_fabricated(self):
        self.assertIsNone(convert_row('nvidia/example', dict(responses_create_params=dict(
            input=[dict(role='user', content='Do something.')]))))

    def test_unsuccessful_swe_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unsuccessful'):
            convert_row('SWE-bench/SWE-smith-trajectories', dict(resolved=False))

    def test_schema_aliases_do_not_change_values(self):
        value = normalize_schema(dict(type='dict', properties=dict(x=dict(type='str, optional', default='int'))))
        self.assertEqual(value, dict(type='object', properties=dict(x=dict(type='string', default='int'))))

    def test_swe_native_call_and_observation(self):
        system = ('You are helpful.\nYou have access to the following functions:\n'
                  '---- BEGIN FUNCTION #1: bash ----\nDescription: Execute a shell command.\n'
                  'Parameters:\n  (1) command (string, required): Shell command.\n---- END FUNCTION #1 ----\n'
                  'If you choose to call a function use this syntax.')
        messages = [dict(role='system', content=system), dict(role='user', content='Inspect.'),
                    dict(role='assistant', content='<function=bash><parameter=command>pwd</parameter></function>'),
                    dict(role='user', content='OBSERVATION:\n/testbed'), dict(role='assistant', content='Done.')]
        native, tools = swe_messages(dict(messages=messages))
        self.assertEqual(native[3]['role'], 'tool')
        self.assertEqual(native[3]['tool_call_id'], native[2]['tool_calls'][0]['id'])
        self.assertNotIn('BEGIN FUNCTION', native[0]['content'])
        self.assertEqual(tools[0]['function']['parameters']['required'], ['command'])


if __name__ == '__main__':
    unittest.main()
