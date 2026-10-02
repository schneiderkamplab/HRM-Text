import pytest

from dfm12.dala_integrate import conversations
from dfm12.dala_european import snapshot


@pytest.mark.parametrize('language,name',[('fi','Finnish'),('ca','Catalan'),('cs','Czech'),('es','Spanish')])
def test_explicit_language_and_four_balanced_views(language,name):
    pair=dict(language=language,split='train',pair_id='p',source_name='fixture',original='Original.',corrupted='Corrupt.',edits=[])
    prompts=dict(acceptability=f'Is this {name} correct? Reply only yes or no.',
                 correction=f'Correct this {name} sentence. Return only the sentence.')
    rows=list(conversations(pair,prompts,'pin'))
    assert len(rows)==4
    assert [r['messages'][-1]['content'] for r in rows]==['yes','no','Original.','Original.']
    assert all(name in r['messages'][0]['content'] for r in rows)
    with pytest.raises(ValueError):
        list(conversations(dict(pair,split='validation'),prompts,'pin'))
    with pytest.raises(ValueError):
        list(conversations(pair,dict(acceptability='Correct?',correction='Fix.'),'pin'))


def test_snapshot_rejects_changed_selection(tmp_path):
    from dfm12.io import write_json
    write_json(tmp_path/'inputs.json',dict(european_selections={'fi':{'run':'old'}}))
    with pytest.raises(ValueError,match='selections changed'):
        snapshot(tmp_path,tmp_path,{'fi':{'run':'new'}})
