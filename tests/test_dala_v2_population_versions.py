import copy
import json
from pathlib import Path
from scripts.prepare_dala_v2_population_versions import prepare, raw_mapping
from scripts.headline_population_registry import validate_registry


def test_new_versions_only_change_exact_dala_bindings():
    base=json.loads(Path('config/multilingual_headline_populations_dfm13_20261006.json').read_text())
    original=copy.deepcopy(base);new=prepare(base);validate_registry(new)
    assert base==original
    assert [p['id'] for p in new['populations']]==['dfm13_multilingual_v2','dfm13_all_languages_v2']
    for p,expected in zip(new['populations'],[38,42]):
        before=next(x for x in base['populations'] if x['id']==p['id'].replace('_v2','_v1'))
        assert p['languages']==before['languages'] and p['required_tasks']==before['required_tasks']
        changes=sum(p['metrics'][lang][task]!=v for lang,tasks in before['metrics'].items() for task,v in tasks.items())
        assert changes==expected
    assert len(raw_mapping()['append_panels'])==42 and raw_mapping()['replacements']==[]
