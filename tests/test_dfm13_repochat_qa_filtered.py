import pytest
from scripts import dfm13_repochat_qa_filtered as f


def test_actual_exact_eligible_set_and_pins():
    tasks, _ = f.selected_tasks()
    receipt = f.n.b.load(f.ASSESSMENT)
    assert len(tasks) == 74
    assert {t['id'] for t in tasks} == set(receipt['eligible_ids'])
    assert not {t['id'] for t in tasks}.intersection(receipt['held_ids'])


def test_missing_gate_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(f.n, 'ROOT', tmp_path)
    with pytest.raises(FileNotFoundError):
        f.verify_gate()


def test_gate_requires_independent_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(f.n, 'ROOT', tmp_path)
    f.n.b.save(tmp_path/'filtered-manual-gate.json', {'release_eligible_74':True,
        'admission':False, 'evidence_pins':{}})
    with pytest.raises(ValueError, match='missing independent'):
        f.verify_gate()
