import pytest
from scripts.assemble_dfm13_final_successor import merge


def test_merge_preserves_exact_entries_and_adds_once():
    c={'additions':[{'name':'a','repeat':5}]}
    merge(c,[{'name':'a','repeat':5},{'name':'b','repeat':1}])
    assert c['additions']==[{'name':'a','repeat':5},{'name':'b','repeat':1}]


def test_conflicting_replacement_fails_closed():
    c={'additions':[{'name':'identity','output_sha256':'new'}]}
    with pytest.raises(ValueError):merge(c,[{'name':'identity','output_sha256':'old'}])
