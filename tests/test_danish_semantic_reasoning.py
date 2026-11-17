import pytest
from scripts.prepare_danish_semantic_reasoning import choice,convert
from evaluation.danish_semantic_reasoning_eval import parse_answer,danish_semantic_reasoning


def test_no_answer_leak_and_neutral_preserved():
    prompt,gold,labels,_,_=convert('entailment','test.txt',['Pia talte.','Per sov.','neutral','frame'],None)
    assert gold=='ukendt' and 'ukendt' in labels and 'neutral' not in prompt


def test_missing_gold_is_not_invented():
    with pytest.raises(AssertionError):convert('entailment','test.txt',['Pia talte.','Per sov.','frame'],None)


def test_known_combined_label_field_is_parsed():
    assert convert('inference','inference_constitutive_wholePart.txt',['Eksempler','Udsagn','true holo_member'],None)[1]=='sandt'


@pytest.mark.parametrize('text,expected',[('JA.','ja'),('ja eller nej',None),('nej, men ja',None),('Svaret er ja',None),('ja\nnej',None)])
def test_strict_label_parser(text,expected):
    assert parse_answer(text,['ja','nej'])==expected


def test_ambiguous_choices_rejected():
    with pytest.raises(AssertionError):choice(['x','x'],'x')


@pytest.mark.parametrize('family',['inference','entailment','danwic','synonymy','similarity','sentiment','dameta'])
def test_prepared_task_loads_and_shards(family):
    full=danish_semantic_reasoning(family=family)
    a=danish_semantic_reasoning(family=family,num_shards=2,shard_index=0)
    b=danish_semantic_reasoning(family=family,num_shards=2,shard_index=1)
    assert len(full.dataset)==len(a.dataset)+len(b.dataset)
    assert not {s.id for s in a.dataset}&{s.id for s in b.dataset}


def test_danwic_primary_excludes_all_positive_control():
    task=danish_semantic_reasoning(family='danwic')
    assert len(task.dataset)==1098
    assert {s.metadata['subset'] for s in task.dataset}=={'danwic_poly_selection'}
    assert {s.target for s in task.dataset}=={'ja','nej'}


def test_invalid_answer_is_wrong_and_reported():
    import asyncio
    from types import SimpleNamespace
    from inspect_ai.scorer import Target
    from evaluation.danish_semantic_reasoning_eval import semantic_score
    state=SimpleNamespace(output=SimpleNamespace(completion='ja eller nej'),metadata={'labels':['ja','nej']})
    score=asyncio.run(semantic_score()(state,Target('ja')))
    assert score.value=={'accuracy':0,'valid_format':0}
