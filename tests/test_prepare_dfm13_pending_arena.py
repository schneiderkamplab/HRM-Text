import copy
import json

import pytest

from scripts import prepare_dfm13_pending_arena as p


def turn(role, content):
    return dict(role=role, content=content)


def helpsteer():
    return dict(context=[turn('user','question')], response1='first', response2='second',
        overall_preference=-1, individual_preference=[], language='en', domain='general',
        original_response='original', edited_response='edited', feedback=[], change_summary='fixed')


@pytest.mark.parametrize('score,expected', [(-3,'first'),(-0.5,'first'),(0.5,'second'),(3,'second')])
def test_preference_direction(score, expected):
    row = helpsteer(); row['overall_preference'] = score
    out = p.convert('helpsteer3_preference',row,7,'rev')[0]
    assert out['messages'][-1]['content'] == expected
    assert out['metadata']['source_line'] == 7
    assert out['target_message_index'] == 1
    assert out['metadata']['admission_authorized'] is False


@pytest.mark.parametrize('score', [True, float('nan'), float('inf'), 4, '1'])
def test_invalid_preference(score):
    row=helpsteer();row['overall_preference']=score
    with pytest.raises((ValueError,TypeError)):
        p.convert('helpsteer3_preference',row,1,'rev')


def test_tie_not_both_good_and_edit_not_original():
    row=helpsteer();row['overall_preference']=0
    assert p.convert('helpsteer3_preference',row,1,'rev') == []
    out=p.convert('helpsteer3_edit',row,1,'rev')[0]
    assert out['messages'][-1]['content']=='edited'
    assert out['metadata']['change_summary']=='fixed'
    assert out['metadata']['split']=='train'


def test_comparia_both_good_preserves_history_no_future():
    history=[turn('user','before'),turn('assistant','context'),turn('user','now'),turn('assistant','answer'),
             turn('user','future'),turn('assistant','future answer')]
    row=dict(response_id='r', comparison_id='c', choice='both_good',turn=1,
        response_a=history[2:4],response_b=history[2:4],full_conversation_a=history,
        full_conversation_b=history,model_a='a',model_b='b',metadata={})
    out=p.convert('comparia',row,1,'rev')
    assert len(out)==2
    assert out[0]['messages']==history[:4]
    assert out[0]['target_message_index']==3
    assert out[0]['metadata']['source']=='ministere-culture/comparia-fr-arena'
    assert 'Etalab' in out[0]['metadata']['license']


def test_expert_history_reconstruction_and_ambiguous_hold():
    current=[turn('user','now'),turn('assistant','answer')]
    full=[dict(user=turn('user','before'),model_a=turn('assistant','context')),
          dict(user=current[0],model_a=current[1])]
    row=dict(id='x',winner='model_a',conversation_a=repr(current),full_conversation=repr(full),
        model_a='a',language='en',evaluation_order=2,occupational_tags={})
    out=p.convert('expert5k',row,1,'rev')[0]
    assert out['target_message_index']==3
    assert out['messages'][-2:]==current
    row['full_conversation']=repr(full+[full[-1]])
    with pytest.raises(ValueError,match='ambiguous'):
        p.convert('expert5k',row,1,'rev')


def prism():
    def response(t,i,text,score):
        return dict(turn=t,role='model',content=text,if_chosen=True,within_turn_id=i,
                    score=score,model_name='model',model_provider='provider')
    return dict(conversation_id='c',conversation_type='unguided',conversation_history=[
        dict(turn=0,role='user',content='first question'),response(0,0,'prior answer',40),
        response(0,1,'prior answer',50),dict(turn=1,role='user',content='second question'),
        response(1,0,'good target',90)])


def test_prism_identical_chosen_is_single_context_and_low_score_context_retained():
    out=p.convert('prism',prism(),1,'rev')
    assert len(out)==1
    assert [m['role'] for m in out[0]['messages']]==['user','assistant','user','assistant']
    assert out[0]['messages'][1]['content']=='prior answer'
    assert out[0]['metadata']['branch_lineage'][0]['chosen_within_turn_ids']==[0,1]
    assert out[0]['metadata']['license_policy']=='held_noncommercial'


def test_prism_distinct_chosen_branch_not_guessed():
    row=prism();row['conversation_history'][2]['content']='different answer'
    with pytest.raises(ValueError,match='ambiguous_prism_branch'):
        p.convert('prism',row,1,'rev')


def test_duplicate_key_includes_target_tools_and_template():
    row=p.convert('helpsteer3_edit',helpsteer(),1,'rev')[0]
    other=copy.deepcopy(row);other['metadata']['source']='other'
    assert p.fingerprint(row)==p.fingerprint(other)
    other['target_message_index']=0
    assert p.fingerprint(row)!=p.fingerprint(other)
    other=copy.deepcopy(row);other['tools']=[{'name':'lookup'}]
    assert p.fingerprint(row)!=p.fingerprint(other)
    other=copy.deepcopy(row);other['chat_template_kwargs']['enable_thinking']=True
    assert p.fingerprint(row)!=p.fingerprint(other)


@pytest.mark.parametrize('raw', [[dict(role='assistant',content='x',tool_calls=[{}])],
                                [dict(role='user',content=[dict(type='image',image='x')])]])
def test_no_silent_tool_or_media_flattening(raw):
    with pytest.raises(ValueError):p.text_messages(raw)


def test_numpy_repr_is_not_executed():
    with pytest.raises(ValueError):
        p.parse_numpy_repr("__import__('os').system('false')")


def test_source_pin_local_card_and_receipt(tmp_path):
    root=tmp_path/'downloads';directory=root/'HelpSteer3'
    data=directory/'edit/train.jsonl.gz';data.parent.mkdir(parents=True);data.write_bytes(b'fixture')
    revision='a'*40;receipt=directory/'.cache/huggingface/download/edit/train.jsonl.gz.metadata'
    receipt.parent.mkdir(parents=True);receipt.write_text(revision+'\n'+p.sha256(data)+'\n0\n')
    hub=tmp_path/'hub';card=hub/'datasets--nvidia--HelpSteer3'/'snapshots'/revision/'README.md'
    card.parent.mkdir(parents=True);card.write_text('license: cc-by-4.0')
    pin=p.source_pin(root,'helpsteer3_edit',hub)
    assert pin['revision']==revision and pin['sha256']==p.sha256(data)
    data.write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash_mismatch'):p.source_pin(root,'helpsteer3_edit',hub)


def test_fresh_root_required(tmp_path):
    with pytest.raises(ValueError,match='Fresh output'):
        p.prepare(tmp_path)
