import json
from pathlib import Path

import pytest

from scripts import prepare_dfm13_jjzha as m

SPECS = {s['name']: s for s in json.loads((m.ROOT/'config/dfm13_jjzha_sources.json').read_text())['sources']}


def test_spans_offsets_and_adjacent_entities():
    assert m.spans(['a','b','c','d'], ['B','I','B','O']) == [
        dict(label='SPAN', start_token=0, end_token=2, text='a b'),
        dict(label='SPAN', start_token=2, end_token=3, text='c')]


@pytest.mark.parametrize('tags', [['I'], ['X'], ['B','I-X']])
def test_malformed_bio_not_repaired(tags):
    with pytest.raises(ValueError):
        m.spans(['a']*len(tags), tags)


def test_danish_annotation_conversion():
    messages=m.convert(dict(tokens=['Python'], tags_skill=['O'], tags_knowledge=['B']), SPECS['jjzha_kompetencer'])
    assert messages[0]['content'].startswith('Udtræk')
    assert json.loads(messages[1]['content'])['tags_knowledge'][0]['text']=='Python'


def test_exam_one_based_answer_and_holdouts():
    row=dict(question='Q',options=['wrong','correct'],answer='2',split='train')
    assert m.convert(row,SPECS['jjzha_dutch_exam'])[1]['content']=='B. correct'
    with pytest.raises(ValueError):m.convert(dict(row,split='test'),SPECS['jjzha_dutch_exam'])
    with pytest.raises(ValueError):m.convert(dict(row,answer='0'),SPECS['jjzha_dutch_exam'])


def test_imdb_overlap_ignores_template():
    assert m.key({'inputs':'question A\n\nreview  text'},'instruct') == m.key({'inputs':'question B\n\nreview text'},'instruct')


def test_chat_tool_payload_never_dropped():
    row=dict(messages=[dict(role='user',content='hi'),dict(role='assistant',content='x',function_calls=[{}])])
    with pytest.raises(ValueError):m.convert(row,SPECS['jjzha_croco'])


def test_registry_preserves_math_and_holds_candidates(tmp_path):
    config=tmp_path/'sources.json'
    original=dict(name='hendrycks_math_worked',repeat=5)
    m.write_json(config,dict(additions=[original]))
    manifest=dict(spec=SPECS['jjzha_croco'],status='pending_audit',output='/tmp/candidates.jsonl',output_sha256='hash',counts={'output_rows':3})
    m.register([manifest],config)
    result=json.loads(config.read_text())
    assert result['additions']==[original]
    assert result['pending_audit'][0]['name']=='jjzha_croco'


def test_native_template(tmp_path):
    import jinja2
    from tokenizers import Tokenizer
    from scripts import tokenize_chat_template as t
    root=m.ROOT/'data/dfm11_tokenizer'
    tok=Tokenizer.from_file(str(root/'tokenizer.json'))
    template=jinja2.Environment().from_string((root/'chat_template.jinja').read_text())
    row={'messages':m.convert(dict(question='Een plus een?',options=['1','2'],answer='2',split='train'),SPECS['jjzha_dutch_exam']), 'target_message_index':1}
    path=tmp_path/'train.jsonl';path.write_text(json.dumps(row)+'\n')
    examples=list(t.read_jsonl(path));assert len(examples)==1
    encoded=t.tokenize_example(tok,template,examples[0],False)
    assert encoded and 'B. 2' in tok.decode(encoded[1],skip_special_tokens=True)
