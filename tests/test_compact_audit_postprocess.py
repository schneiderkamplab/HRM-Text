from scripts.compact_audit_postprocess import classify


def row(value,finish='stop'):
    return dict(raw=dict(finish_reason=finish),raw_decision=value)


def test_empty_reason_keep_is_provisional_not_discarded():
    value=classify(row(dict(verdict='keep',issues=[],reason='')))
    assert value['status']=='usable_model_verdict'
    assert value['warnings']==['missing_rationale']
    assert not value['admission_authorized'] and value['source_holds_preserved']


def test_missing_reason_nonkeep_and_duplicates_retained():
    value=classify(row(dict(verdict='repair',issues=['incorrect','incorrect'])))
    assert value['status']=='usable_model_verdict'
    assert 'duplicate_issue_labels' in value['warnings']


def test_contradiction_and_incomplete_do_not_become_keeps():
    assert classify(row(dict(verdict='keep',issues=['incorrect'])))['status']=='contradictory_keep'
    assert classify(row(dict(verdict='keep',issues=[]),'length'))['status']=='incomplete_or_unknown'


def test_named_uncertainty_without_label_is_retained():
    value=classify(row(dict(verdict='needs_verification',issues=[],reason='Source date absent.')))
    assert value['status']=='usable_model_verdict'
    assert value['warnings']==['missing_issue_label']
