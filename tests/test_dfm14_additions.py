import unittest
from dfm14.native_instructions import convert
from dfm14.knowledge_adapters import swallow
from dfm14.audit_protocol_extended import messages
from dfm14.prepare_gpu import validate_candidate
from dfm14.parallel_expand import eligible, texts


class AdditionsTests(unittest.TestCase):
    def test_reasoning_and_tool_links_survive(self):
        tool = dict(type='function', function=dict(name='lookup', parameters=dict(type='object', properties={})))
        row = dict(tools=[tool], messages=[dict(role='user',content='Look up the status.'),
            dict(role='assistant',content=None,reasoning_content='I need the current status.',
                 tool_calls=[dict(id='a',type='function',function=dict(name='lookup',arguments='{}'))]),
            dict(role='tool',content='Available',tool_call_id='a',name='lookup'),
            dict(role='assistant',content='It is available.',reasoning_content=None)])
        result = convert(row)
        result.update(training_ready=False,admission_authorized=False,rendered_tokens=100)
        validate_candidate(result)
        self.assertEqual(result['messages'][1]['reasoning_content'],'I need the current status.')
        self.assertIn('lookup', messages(result)[1]['content'])
        bad = dict(row, tools=[])
        with self.assertRaises(ValueError): convert(bad)

    def test_delimited_science_pairs(self):
        result = swallow(dict(text='**Question 1**:\nWhy?\n\n**Answer 1**:\nBecause.\n\n**Question 2**:\nHow?\n\n**Answer 2**:\nLike this.'))
        self.assertEqual(len(result), 4)
        self.assertEqual(result[2]['content'], 'How?')
        for text in ('Unstructured text', '**Question 1**:\nWhy?\n**Answer 2**:\nBecause.'):
            with self.assertRaises(ValueError): swallow(dict(text=text))

    def test_pivot_boundaries(self):
        self.assertFalse(eligible('Yes.'))
        self.assertTrue(eligible('The museum closes its doors at six in the evening.'))
        self.assertEqual(texts(dict(language='en',reverse_language='zh',messages=[dict(content='English')],
                                   reverse_messages=[dict(content='Chinese')])), {'en':'English','zh':'Chinese'})


if __name__ == '__main__': unittest.main()
