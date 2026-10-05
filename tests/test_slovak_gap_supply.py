import json

import pytest

from dfm12.io import file_hash, load, write_json
from scripts.research_slovak_gap_supply import crosscheck


def record(language, english, target):
    return dict(language=language,reverse_language='en',
                messages=[dict(role='assistant',content=target)],
                reverse_messages=[dict(role='assistant',content=english)])


def fixture(tmp_path):
    pins = {}
    for language, records in {
        'ca':[record('ca','same','ca')],
        'fo':[record('fo','Same','fo')],
        'nn':[record('nn','unique','nn')],
        'sk':[record('sk','same','sk1'),record('sk','same','sk2'),record('sk','unique','sk3')],
    }.items():
        folder = tmp_path/('opus-en-'+language)
        folder.mkdir()
        path=folder/'candidates.jsonl'
        path.write_text(''.join(json.dumps(r)+'\n' for r in records))
        pins[str(path)]=file_hash(path)
    write_json(tmp_path/'receipt.json',dict(local_leg_pins=pins))


def test_exact_join_and_ambiguity(tmp_path):
    fixture(tmp_path)
    crosscheck(tmp_path)
    result=load(tmp_path/'independent-stream-crosscheck.json')
    assert result['sk_rows_scanned']==3
    assert result['pairs']['ca-sk']==dict(raw_exact_anchor_intersections=1,unambiguous_intersections=0)
    assert result['pairs']['fo-sk']==dict(raw_exact_anchor_intersections=0,unambiguous_intersections=0)
    assert result['pairs']['nn-sk']==dict(raw_exact_anchor_intersections=1,unambiguous_intersections=1)


def test_drift_fails_closed(tmp_path):
    fixture(tmp_path)
    (tmp_path/'opus-en-sk/candidates.jsonl').write_text('')
    with pytest.raises(ValueError,match='Pinned input drift'):
        crosscheck(tmp_path)
