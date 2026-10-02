from scripts import dfm13_repochat_qualifier_controls as q


def test_generic_rules():
    assert 'counterexample' in q.RULES
    assert 'As soon as possible' in q.RULES
    assert 'Neuro' not in q.RULES
    assert 'fcc0' not in q.RULES


def test_preserves_controls_and_pairs():
    targeted, full = q.records()
    original = q.base.b.load(q.base.ROOT / 'plan.json')['controls']
    assert full == original
    assert len(full) == 32
    assert len(targeted) == 4
    assert [c['expected_pass'] for c in targeted] == [False, True, False, True]
    assert targeted[2]['package']['retrieved_source'] == targeted[3]['package']['retrieved_source']


def test_prepare_pins_and_no_pilot(tmp_path):
    targeted, _ = q.records()
    plan = q.prepare(tmp_path, targeted, 'targeted')
    assert not plan['automatic_pilot']
    assert not plan['admission']
    assert q.prepare(tmp_path, targeted, 'targeted') == plan
