from scripts import dfm13_repochat_candidate_recovery as c


def test_only_failed_stages_and_preserved_authority(tmp_path):
    plan = c.prepare(tmp_path)
    original = c.b.load(c.r.ROOT / 'plan.json')
    assert len(plan['jobs']) == 686
    assert {j['kind'] for j in plan['jobs']} == {'finalize', 'audit', 'audit_retry'}
    assert plan['preserved_holds'] == original['preserved_holds']
    assert not plan['admission']
    assert c.prepare(tmp_path) == plan


def test_no_native_tools_in_finalization():
    payload = c.r.final_payload([{'role':'user','content':'Question'}], 'model')
    assert 'tools' not in payload
    assert 'tool_choice' not in payload
