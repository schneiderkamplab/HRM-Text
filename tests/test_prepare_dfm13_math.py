import copy
from pathlib import Path

import pytest

from scripts import prepare_dfm13_math as m


def item(identity, problem, solution=r'Work. $\boxed{2}$', config='algebra'):
    return dict(id=identity,config=config,row_index=0,source_file=config+'/train.parquet',
        source_file_sha256='source-sha',row=dict(problem=problem,solution=solution,type='Algebra',level='Level 1'))


def test_cross_configuration_test_overlap_exact_and_whitespace():
    train=[item('a','x + y'),item('b','a\n  +\tb'),item('c','keep')]
    test=[item('test-a','x + y',config='geometry'),item('test-b','a + b')]
    kept,excluded=m.screen(train,test)
    assert [r['id'] for r in kept]==['c']
    assert [r['reason'] for r in excluded]==['train_test_exact','train_test_whitespace']
    assert excluded[0]['matched_test_ids']==['test-a']
    assert kept[0]['metadata']['split']=='train'


def test_train_problem_duplicates_record_conflicting_solution():
    kept,excluded=m.screen([item('a','same question'),item('b','same question'),
        item('c','same\nquestion',r'Different work. \boxed{3}')],[])
    assert len(kept)==1
    assert excluded[0]['reason']=='train_duplicate_exact'
    assert excluded[0]['same_solution'] is True
    assert excluded[1]['reason']=='train_duplicate_whitespace'
    assert excluded[1]['same_solution'] is False
    assert excluded[1]['winner_id']=='a'


def test_normalization_does_not_remove_word_separators_or_change_case():
    assert m.normalized_problem('  a\n b  ')=='a b'
    assert m.normalized_problem('a b')!=m.normalized_problem('ab')
    assert m.normalized_problem('A')!=m.normalized_problem('a')


@pytest.mark.parametrize('solution,answer',[
    (r'First \boxed{1}, then \boxed{\frac{2}{3}}.',r'\frac{2}{3}'),
    (r'Complete work \fbox{ 42 }','42'),
    (r'Proof \boxed{{a+b}^2} trailing explanation',r'{a+b}^2'),
    (r'Worked solution ends with $\boxed 2$.','2'),
    (r'Worked solution ends with $\boxed 9$.','9'),
])
def test_full_original_solution_preserved_with_terminal_box(solution,answer):
    result,actual,appended=m.worked_solution(solution)
    assert result.startswith(solution)
    assert actual==answer and appended
    assert result.endswith('\\boxed{'+answer+'}')


def test_already_terminal_box_unchanged():
    original='Detailed reasoning. \\boxed{2}\n'
    assert m.worked_solution(original)==(original,'2',False)


@pytest.mark.parametrize('solution',['No boxed answer',r'\boxed{unterminated','',r'\boxed{}',r'$\boxed 12$'])
def test_missing_box_not_invented(solution):
    with pytest.raises(ValueError):m.worked_solution(solution)


def test_invalid_first_solution_does_not_hide_valid_duplicate():
    kept,excluded=m.screen([item('a','question','No box'),item('b','question')],[])
    assert [r['id'] for r in kept]==['b']
    assert excluded[0]['reason']=='invalid_solution'


def test_source_not_mutated_and_only_single_target():
    source=item('a','question')
    original=copy.deepcopy(source)
    row=m.screen([source],[])[0][0]
    assert source==original
    assert row['target_message_index']==1
    assert row['messages'][0]['content']=='question'
    assert len(row['messages'])==2
    assert row['metadata']['revision']==m.REVISION


def test_real_native_template_tokenizes_full_worked_solution():
    import jinja2
    from tokenizers import Tokenizer
    from scripts import tokenize_chat_template as t
    tokenizer_path=m.ROOT/'data/dfm11_tokenizer/tokenizer.json'
    template_path=m.ROOT/'data/dfm11_tokenizer/chat_template.jinja'
    if not tokenizer_path.exists():pytest.skip('Local native tokenizer unavailable')
    response=m.worked_solution(r'We add one and one. \boxed{2}')[0]
    example=t.hrm_row_to_messages('direct','Compute 1 + 1.',response)
    encoded=t.tokenize_example(Tokenizer.from_file(str(tokenizer_path)),
        jinja2.Environment().from_string(template_path.read_text()),example,False)
    assert encoded is not None and all(encoded)
    decoded=Tokenizer.from_file(str(tokenizer_path)).decode(encoded[1],skip_special_tokens=True)
    assert response in decoded


def test_register_preserves_previous_eight_sources(tmp_path):
    output=tmp_path/'converted';output.mkdir()
    (output/'train.jsonl').write_text('data')
    manifest=dict(train_sha256=m.file_hash(output/'train.jsonl'),rows=1,pins={},corpus_overlap='RLVR expected')
    m.write_json(output/'metadata/manifest.json',manifest)
    m.write_json(output/'metadata/tokenization-receipt.json',dict(
        converted_manifest_sha256=m.file_hash(output/'metadata/manifest.json'),tokens=10,files={}))
    config=tmp_path/'config.json'
    additions=[dict(name=f'arena-{i}',repeat=1,output=f'accepted-{i}') for i in range(8)]
    m.write_json(config,dict(inherits='dfm12',additions=additions))
    m.register(config,output,tmp_path/'tokenized')
    actual=m.load(config)
    assert actual['additions'][:8]==additions
    assert actual['additions'][8]['repeat']==5
    with pytest.raises(ValueError,match='already registered'):m.register(config,output,tmp_path/'tokenized')
