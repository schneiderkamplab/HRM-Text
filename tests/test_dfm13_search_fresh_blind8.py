import pytest
from scripts.dfm13_search_fresh_blind8 import select, references
from scripts.dfm13_search_postbatch_accounting import receipt_rows, SUPPORTED_ASSESSMENTS


def test_new_receipt_schema_covers_blind_and_repairs():
    rows = receipt_rows(dict(blind_packet=[dict(id='one')],repairs=[dict(id='two')]))
    assert [r['id'] for r in rows] == ['one','two']
    assert 'useful_honest_evidence_limitation' in SUPPORTED_ASSESSMENTS
    assert 'prior_date_leakage_issue_resolved_useful_answer' in SUPPORTED_ASSESSMENTS
    assert 'hard_hold_future_evidence_used_as_historical_analysis' not in SUPPORTED_ASSESSMENTS


def test_never_seen_prioritized_and_all_holds_and_seen_hashes_excluded():
    pool = [dict(id=f'{i:02}',sha256='hash'+str(i),training_sha256='text'+str(i),held=False) for i in range(12)]
    pool[0]['held'] = True
    result = select(pool,{'01','02'},{'hash3'},size=8)
    assert len(result) == 8
    assert all(r['id'] not in {'00','01','02','03'} for r in result)
    assert all(r['never_manually_seen_id'] for r in result)
    assert result == select(list(reversed(pool)),{'01','02'},{'hash3'},size=8)


def test_insufficient_fresh_does_not_reuse_old_hash():
    with pytest.raises(ValueError):
        select([dict(id='a',sha256='seen',training_sha256='t',held=False)],set(),{'seen'},size=1)


def test_reference_hashes_ignore_request_and_packet_pins():
    assert references(dict(pins=[dict(path='a/candidate.json',sha256='c'),
        dict(path='a/packet.json',sha256='p'),dict(path='a/actual-request.json',sha256='r')])) == {'c'}
