import importlib.util
from pathlib import Path

P=Path(__file__).resolve().parents[1]/'scripts/dfm13_arena_original_keep_sample.py'
spec=importlib.util.spec_from_file_location('original_keep_sample_test',P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_stratum_quotas_sum_ten():
    assert m.quotas({0:100,1:500,2:200,3:300})=={0:2,1:3,2:2,3:3}


def test_reproducible_hash_rank():
    assert m.rank('seed',9,'id')==m.rank('seed',9,'id')
    assert m.rank('seed',9,'id')!=m.rank('other seed',9,'id')
