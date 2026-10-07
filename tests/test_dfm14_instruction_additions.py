import json
import unittest
from dfm14.instruction_additions import grounded_messages, sources
from dfm14.prepare import normalize


class AdditionsTests(unittest.TestCase):
    def row(self):
        return {'conversation': [
            {'role': 'documents', 'content': json.dumps([{'doc_id': 0, 'title': 'Evidence', 'content': 'Full evidence.'}])},
            {'role': 'user', 'content': 'Question?'},
            {'role': 'assistant', 'content': '[0]'},
            {'role': 'assistant', 'content': 'Answer.'}]}

    def test_preserves_evidence_and_answer(self):
        row = self.row()
        messages = normalize(row, sources()[-1])['messages']
        self.assertEqual([m['role'] for m in messages], ['user', 'assistant'])
        self.assertIn(row['conversation'][0]['content'], messages[0]['content'])
        self.assertTrue(messages[1]['content'].endswith('Answer.'))

    def test_invalid_citation_held(self):
        row = self.row()
        row['conversation'][2]['content'] = '[10]'
        with self.assertRaisesRegex(ValueError, 'invalid_selected'):
            grounded_messages(row)

    def test_unexpected_turn_held(self):
        row = self.row()
        row['conversation'].pop()
        with self.assertRaisesRegex(ValueError, 'structure'):
            grounded_messages(row)

    def test_japanese_mapping(self):
        result = normalize({'text': 'Question', 'output': 'Answer'}, sources()[1])
        self.assertEqual(result['messages'][0]['content'], 'Question')

    def test_train_only(self):
        self.assertEqual(sources()[1]['patterns'], ['v1.0/train-*.parquet'])
        self.assertEqual(sources()[-1]['patterns'], ['data/train-*.parquet'])
