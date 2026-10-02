import asyncio
from types import SimpleNamespace

import pytest

from dfm12 import european_synthetic_campaign, multilingual_pilot_v6
from dfm12.io import digest, load
from dfm12.joint_async_process import AsyncRemoteSeen, process


@pytest.mark.parametrize('private', [False, True])
@pytest.mark.parametrize('case', ['accept', 'reject', 'duplicate', 'generation_invalid',
                                  'review_invalid', 'exception', 'cancel_generate', 'cancel_review'])
def test_retained_processor_parity(tmp_path, monkeypatch, private, case):
    pilot = european_synthetic_campaign.isolated_controller().pilot if private else multilingual_pilot_v6
    candidate = dict(messages=[dict(role='user', content='Question'),
                               dict(role='assistant', content='Answer')], tools=[])
    spec = dict(language_code='de' if private else 'nb', family='tool-dialogue', slot=1,
                subtype='single', contract_version=4, cohort='async-parity')
    fingerprint = digest(candidate)
    v6 = pilot.v6
    monkeypatch.setattr(v6, 'generation_request', lambda *a, **kw: {'kind': 'generation'})
    monkeypatch.setattr(v6, 'compact_request', lambda p: (p, {'schema': True}))
    monkeypatch.setattr(v6, 'endpoint_limit', lambda h: 16384)
    monkeypatch.setattr(v6, 'generation_assemble', lambda *a: candidate)
    monkeypatch.setattr(v6, 'audit_record', lambda c: {'candidate': c})
    monkeypatch.setattr(v6, 'review_request', lambda *a: {'kind': 'review'})
    monkeypatch.setattr(v6, 'review_result', lambda *a: dict(status='valid', effective_keep=case != 'reject'))

    class Stages:
        def __init__(self):
            self.calls = []

        async def call(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            stage = args[1]
            if case == 'cancel_' + stage:
                raise asyncio.CancelledError()
            if case == 'exception':
                raise ValueError('fixture failure')
            status = 'invalid_output' if case == ('generation_invalid' if stage == 'generate' else 'review_invalid') else 'complete'
            return dict(status=status, output={}, json_valid=True, structure_valid=True,
                        content_constraints_valid=True, error='fixture' if status != 'complete' else None)

    class Claims:
        def __init__(self):
            self.values = {fingerprint} if case == 'duplicate' else set()
            self.calls = 0

        async def claim(self, value):
            self.calls += 1
            if value in self.values:
                return False
            self.values.add(value)
            return True

    async def run():
        old_seen = {fingerprint} if case == 'duplicate' else set()
        new_seen = Claims()
        old_stages, new_stages = Stages(), Stages()
        args = (spec, 'endpoint')
        for root, stages, seen, new in [(tmp_path/'old', old_stages, old_seen, False),
                                         (tmp_path/'new', new_stages, new_seen, True)]:
            call = process(*args, root, stages, {'endpoint': {}}, None, None, seen, pilot=pilot) if new else pilot.process(*args, root, stages, {'endpoint': {}}, None, None, seen)
            if case.startswith('cancel_'):
                with pytest.raises(asyncio.CancelledError):
                    await call
            else:
                await call
        key = pilot.slot_key(spec)
        old = load(tmp_path/'old'/'outcomes'/f'{key}.json')
        new = load(tmp_path/'new'/'outcomes'/f'{key}.json')
        old.pop('completed'); new.pop('completed')
        assert old == new
        assert old_stages.calls == new_stages.calls
        assert old_seen == new_seen.values
        old_candidate = tmp_path/'old'/'candidates'/f'{key}.json'
        new_candidate = tmp_path/'new'/'candidates'/f'{key}.json'
        assert old_candidate.exists() == new_candidate.exists()
        if old_candidate.exists():
            assert load(old_candidate) == load(new_candidate)
    asyncio.run(run())


@pytest.mark.parametrize('result', [True, False])
def test_remote_claim_is_one_rpc_without_confirm(result):
    calls = []
    async def call(op, **fields):
        calls.append((op, fields))
        return result
    seen = AsyncRemoteSeen(SimpleNamespace(call=call), 'original', 'slot')
    assert asyncio.run(seen.claim('a'*64)) is result
    assert calls == [('claim', dict(role='original', key='slot', fingerprint='a'*64))]
    assert not seen.broken


@pytest.mark.parametrize('failure', [RuntimeError('disconnected'), asyncio.CancelledError(), None])
def test_remote_claim_marks_broken_on_transport_or_protocol_failure(failure):
    async def call(*a, **kw):
        if failure is not None:
            raise failure
        return 'not a boolean'
    seen = AsyncRemoteSeen(SimpleNamespace(call=call), 'original', 'slot')
    with pytest.raises(type(failure) if failure is not None else ValueError):
        asyncio.run(seen.claim('a'*64))
    assert seen.broken
