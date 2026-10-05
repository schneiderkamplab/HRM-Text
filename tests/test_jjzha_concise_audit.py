import unittest
from unittest.mock import patch

from scripts.audit_dfm13_jjzha import REVIEW_PROMPT, ISSUES, review_request


class ConciseAuditTests(unittest.TestCase):
    def test_request_is_short_nonthinking_and_verdict_first(self):
        with patch('scripts.audit_dfm13_jjzha.base.visible', return_value={'target': 'Hello'}):
            request = review_request({}, 'jjzha_imdb_dutch', 'test-model')
        self.assertEqual(request['max_tokens'], 256)
        self.assertEqual(request['chat_template_kwargs'], {'enable_thinking': False})
        self.assertEqual(request['model'], 'test-model')
        properties = request['response_format']['json_schema']['schema']['properties']
        self.assertEqual(list(properties), ['verdict', 'issues', 'reason'])
        self.assertNotIn('maxLength', properties['reason'])
        self.assertIn('positive/negative', request['messages'][0]['content'])

    def test_prompt_does_not_request_reasoning_first(self):
        self.assertIn('verdict FIRST', REVIEW_PROMPT)
        self.assertIn('at most 30 words', REVIEW_PROMPT)
        self.assertNotIn('reason FIRST', REVIEW_PROMPT)

    def test_issue_labels_are_unique(self):
        self.assertEqual(len(ISSUES), len(set(ISSUES)))
        self.assertEqual(set(ISSUES), {
            'language', 'incorrect', 'instruction', 'unsupported', 'format', 'incomplete'})
