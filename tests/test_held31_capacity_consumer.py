import ast
import inspect
from pathlib import Path

import pytest

from dfm12 import held31_capacity_consumer as c


@pytest.mark.parametrize('n', [0, -1, True, 9, 64])
def test_unmeasured_rejected(n):
    with pytest.raises(ValueError):
        c.capacity_limit({}, {}, n)


def test_default_ceiling():
    assert c.capacity_limit({}, {}, 8)['measured'] is False


def test_measured_reservation(tmp_path, monkeypatch):
    p = tmp_path/'profile.json'
    c.write_json(p, dict(model='test-only', revision='test-only',
                        client_allocations=dict(wave4=24,baltic=8)))
    monkeypatch.setattr(c.capacity, 'validate', lambda _: (32,64))
    m=dict(model='test-only', revision='test-only',capacity_wave='wave4')
    a=dict(capacity_reservation=dict(profile_sha256=c.file_hash(p),wave='wave4',
        exclusive_wave_allocation=True, other_clients_within_remaining_allocations=True,
        scheduler_owner='synthetic-test'))
    assert c.capacity_limit(m,a,24,p)['aggregate']==32
    with pytest.raises(ValueError): c.capacity_limit(m,a,25,p)
    with pytest.raises(ValueError): c.capacity_limit(m,{},24,p)
    a['capacity_reservation']['profile_sha256']='drift'
    with pytest.raises(ValueError): c.capacity_limit(m,a,24,p)


def test_stage_lifecycle_parity():
    old=ast.parse(inspect.getsource(c.fars.run)).body[0]
    new=ast.parse(inspect.getsource(c.execute)).body[0]
    # Full lifecycle after the old cap guard is byte-for-byte AST equivalent.
    assert [ast.dump(x) for x in old.body[2:]] == [ast.dump(x) for x in new.body[6:]]


def test_prepare_preserves_predecessor(tmp_path):
    old=tmp_path/'old';old.mkdir()
    (old/'catalog.sqlite').write_bytes(b'test-only immutable catalog')
    c.write_json(old/'manifest.json',dict(count=20,pins={},model='test-only',revision='test-only'))
    c.write_json(old/'seal.json',dict(manifest_sha256=c.file_hash(old/'manifest.json')))
    before=c.file_hash(old/'manifest.json')
    new=tmp_path/'new'
    c.prepare(new,old,'baltic')
    assert c.fars.verify(new)['capacity_wave']=='baltic'
    assert c.file_hash(old/'manifest.json')==before
    assert not c.load(new/'launch-handoff.template.json')['run_authorized']
    with pytest.raises(ValueError): c.prepare(new,old,'baltic')
    (old/'runtime.sqlite').touch()
    with pytest.raises(ValueError): c.prepare(tmp_path/'blocked',old,'baltic')
