import pytest
from scripts.dfm13_search_closeout_export import verify_observations, select_version
import json
from pathlib import Path


def test_exact_cache_binding():
    row={'messages':[{'content':json.dumps({'results':[{'url':'https://x','body':'first\n\nlast'}]})}]}
    calls={0:{'name':'search','arguments':{'query':'q'}}}
    cache=[{'query':'q','sha256':'hash','payload':{'data':[{'url':'https://x','content':'first\n\nomitted\n\nlast'}]}}]
    assert verify_observations(row,calls,cache)[0]['matches'][0]['raw_sha256']=='hash'
    cache[0]['query']='different'
    with pytest.raises(ValueError):verify_observations(row,calls,cache)


def test_invented_observation_rejected():
    row={'messages':[{'content':json.dumps({'results':[{'url':'https://x','body':'invented'}]})}]}
    with pytest.raises(ValueError):verify_observations(row,{0:{'name':'search','arguments':{'query':'q'}}},[])


def test_one_exact_manual_version():
    assert select_version({'existing_manual_versions':[{'candidate':'a','candidate_sha256':'sha'},{'candidate':'b','candidate_sha256':'sha'}]})==(Path('a'),'sha')
