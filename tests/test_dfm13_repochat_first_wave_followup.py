from scripts import dfm13_repochat_first_wave_followup as r


def test_originals_and_single_retry_are_separate():
    source = r.f.n.ROOT/'first'
    assert r.ROOT != source
    tasks = r.b.load(source/'selection.json')['tasks']
    assert {r.WACOM, r.SCRCPY}.issubset({t['id'] for t in tasks})
    failure = r.b.load(source/'trajectories'/r.WACOM/'outcome.json')
    assert failure['status'] == 'failed'
    assert 'final_empty' in failure['error']
