import copy
import json

import pytest

from scripts import finalize_dfm13_jjzha as m


def row():
    return dict(id='example', target_message_index=1,
                messages=[dict(role='user', content='Vraag'), dict(role='assistant', content='Antwoord')],
                metadata=dict(source_dataset='Wildchat'))


def test_repair_preserves_context_and_input():
    original = row()
    before = copy.deepcopy(original)
    fixed = m.repaired(original, 'Correct antwoord')
    assert original == before
    assert fixed['messages'][:-1] == original['messages'][:-1]
    assert fixed['messages'][-1]['content'] == 'Correct antwoord'


@pytest.mark.parametrize('content', ['', '  ', '<start_of_turn>model', '[INST]test'])
def test_bad_repairs_are_not_accepted(content):
    with pytest.raises(ValueError):
        m.repaired(row(), content)


def test_policy_survives_model_keep():
    value = row()
    assert m.policy(value)
    for family in ['FLAN', 'translated Tasksource']:
        value['metadata']['source_dataset'] = family
        assert not m.policy(value)


def test_repair_has_no_thinking_or_prompt_mutation():
    request = m.repair_request(row(), 'A bounded factual error')
    assert request['chat_template_kwargs'] == {'enable_thinking': False}
    assert request['max_tokens'] == 8192
    assert 'needs_review' in request['response_format']['json_schema']['schema']['properties']['status']['enum']


def test_imdb_preserves_binary_labels():
    value = row()
    value['metadata']['source'] = 'jjzha/imdb-dutch-instruct'
    prompt = m.repair_request(value, 'Wrong sentiment')['messages'][0]['content']
    assert 'BINARY' in prompt
    assert 'positief or negatief' in prompt
    assert 'needs_review' in prompt


def test_export_excludes_unresolved_and_requires_review(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    campaign = tmp_path/'campaign'
    campaign.mkdir()
    spec = dict(repo_id='example/source', revision='pinned', license='cc-by-4.0')
    m.write_json(campaign/'prepared.json', dict(manifests={'jjzha_test': dict(spec=spec, status='pending_audit')}))
    db = m.db_open(campaign)
    for i, status in enumerate(['accepted', 'rejected', 'held', 'error', 'policy_excluded']):
        value = row()
        value['id'] = str(i)
        value['metadata']['language'] = 'nl'
        db.execute('INSERT INTO jobs VALUES(?,?,?,?,?)',
                   (str(i), 'jjzha_test', json.dumps(value), status, json.dumps({'audit': {'verdict': 'keep'}})))
    db.commit()
    db.close()
    m.publish(campaign, False)
    output = tmp_path/'exports_dfm13/dfm13-jjzha-test/data/train.jsonl'
    assert len(output.read_text().splitlines()) == 1
    assert json.loads(output.read_text())['id'] == '0'
