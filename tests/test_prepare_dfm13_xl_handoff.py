import json

import pytest

from scripts.prepare_dfm13_xl_handoff import proposal, sample_contract


def test_missing_receipt_is_not_ready(tmp_path):
    assert sample_contract(tmp_path / 'missing.json', tmp_path) is None


def test_partial_verification_rejected(tmp_path):
    receipt = tmp_path / 'completion.json'
    receipt.write_text(json.dumps(dict(complete=True, epochs=1, output=str(tmp_path),
                                      validation=dict(full_index_bounds_scan=True))))
    with pytest.raises(ValueError, match='full verified'):
        sample_contract(receipt, tmp_path)


def test_proposal_preserves_run_and_clean_boundaries():
    value = proposal({}, dict(optimizer_steps=487123))
    assert value['start_step'] == 3150000
    assert value['end_step'] == 3637123
    assert value['eval_steps'] == list(range(3200000, 3637123, 50000)) + [3637123]
    assert value['proposed_lr']['decay_start_step'] == 3587123
    assert value['proposed_lr']['rewarm_steps'] == 0
    assert value['wandb_run_id'] == 'dfm8-xl-from-dfm6-dfm7-epoch5-clean-full'
    assert value['resume_policy']['preserve_optimizer']
    assert value['resume_policy']['preserve_ema']
    assert not value['training_launched']
    assert not value['active_plan_changed']


def test_too_short_budget_rejected():
    with pytest.raises(ValueError, match='short'):
        proposal({}, dict(optimizer_steps=10000))
