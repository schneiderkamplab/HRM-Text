import json
from types import SimpleNamespace

import pytest
import yaml

from conversion.convert_to_hf import _build_rope_parameters
from eval_scheduler.runtime import validate_export_rope_config


def test_yarn_parameters_use_transformers_field_names():
    assert _build_rope_parameters(
        {
            "max_seq_len": 8192,
            "H_rope_scaling_type": "yarn",
            "H_rope_scaling_factor": 2.0,
        },
        10000.0,
    ) == {
        "rope_type": "yarn",
        "factor": 2.0,
        "original_max_position_embeddings": 4096,
        "rope_theta": 10000.0,
    }


def test_export_validation_rejects_default_rope_for_yarn_checkpoint(tmp_path):
    checkpoint = tmp_path / "checkpoint"
    export = tmp_path / "export"
    checkpoint.mkdir()
    export.mkdir()
    (checkpoint / "all_config.yaml").write_text(
        yaml.safe_dump(
            {
                "arch": {
                    "H_rope_scaling_type": "yarn",
                    "H_rope_scaling_factor": 2.0,
                }
            }
        )
    )
    (export / "config.json").write_text(
        json.dumps({"rope_parameters": {"rope_type": "default", "rope_theta": 10000.0}})
    )
    job = SimpleNamespace(metadata={"ckpt_path": str(checkpoint)})

    with pytest.raises(ValueError, match="RoPE type mismatch"):
        validate_export_rope_config(job, export)


@pytest.mark.parametrize("attention,prefix", [("prefixlm", False), ("causal", True)])
def test_export_rejects_other_attention_objective(tmp_path, attention, prefix):
    checkpoint = tmp_path / "checkpoint"
    export = tmp_path / "export"
    checkpoint.mkdir()
    export.mkdir()
    (checkpoint / "all_config.yaml").write_text(yaml.safe_dump({"arch": {"attn_type": attention}}))
    (export / "config.json").write_text(json.dumps({
        "prefix_lm": prefix, "rope_parameters": {"rope_type": "default"}
    }))
    job = SimpleNamespace(metadata={"ckpt_path": str(checkpoint)})
    with pytest.raises(ValueError, match="attention objective mismatch"):
        validate_export_rope_config(job, export)


@pytest.mark.parametrize('field,value', [('checkpoint_path','/other'), ('checkpoint_tag','step_100000'), ('use_ema',False)])
def test_export_receipt_rejects_wrong_source(tmp_path,field,value):
    from eval_scheduler.runtime import export_source_identity
    job=SimpleNamespace(metadata={'ckpt_path':str(tmp_path/'checkpoint'),'ckpt_tag':'step_50000'})
    receipt=export_source_identity(job);receipt[field]=value
    (tmp_path/'scheduler_export_source.json').write_text(json.dumps(receipt))
    with pytest.raises(ValueError,match='export source checkpoint mismatch'):
        validate_export_rope_config(job,tmp_path)


def test_required_export_receipt_cannot_be_missing(tmp_path):
    job=SimpleNamespace(metadata={'ckpt_path':str(tmp_path/'checkpoint'),'ckpt_tag':'step_50000','require_export_source':True})
    with pytest.raises(ValueError,match='missing export source receipt'):
        validate_export_rope_config(job,tmp_path)
