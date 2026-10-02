from scripts import dfm13_arena_recovery_candidate_diagnostic as m
import pytest


def fixture():
    manifest = dict(diagnostic_only=True, controls_pass=False, export_prohibited=True,
        no_admission=True, user_authorized_failed_control_diagnostic=True, total=100)
    jobs = [dict(id=str(i), kind='recovery') for i in range(100)]
    controls = [dict(id=f'c{i}', status='complete', result={'verdict': 'keep'}) for i in range(6)]
    return manifest, jobs, {r['id']: r for r in controls}, controls


def test_explicit_exception_retains_failed_flag():
    args = fixture()
    assert m.authorized(*args)
    assert args[0]['controls_pass'] is False


@pytest.mark.parametrize('key', ['diagnostic_only', 'export_prohibited', 'no_admission',
                                'user_authorized_failed_control_diagnostic', 'total'])
def test_missing_restriction_fails_closed(key):
    manifest, *rest = fixture()
    manifest.pop(key)
    assert not m.authorized(manifest, *rest)


def test_control_drift_and_expansion_fail():
    manifest, jobs, outcomes, controls = fixture()
    assert not m.authorized(manifest, jobs + jobs[:1], outcomes, controls)
    outcomes = dict(outcomes, c0={'result': {'verdict': 'reject'}})
    assert not m.authorized(manifest, jobs, outcomes, controls)
