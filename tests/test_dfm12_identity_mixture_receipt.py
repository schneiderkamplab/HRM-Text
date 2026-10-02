import numpy as np
import pytest

from dfm12.identity_mixture_receipt import response_summary, verify_and_write
from dfm12.build_identity_adaptation import continuation_contract


def test_response_fractions_and_stop():
    result = response_summary(np.array([90, 4, 6, 100]), np.array([0, 1, 2, 0]), 3)
    assert result["at_stop"]["identity_response_fraction"] == .1
    assert result["prepared"]["identity_response_fraction"] == .05
    assert result["at_stop"]["rows"] == 3


@pytest.mark.parametrize("stop", [0, 5])
def test_invalid_boundary(stop):
    with pytest.raises(ValueError, match="boundary"):
        response_summary(np.ones(3), np.arange(3), stop)


def test_unknown_source_label():
    with pytest.raises(ValueError, match="labels"):
        response_summary(np.ones(4), np.arange(4), 3)


def test_no_existing_receipt_overwrite(tmp_path):
    (tmp_path / "identity-lineage.json").touch()
    with pytest.raises(FileExistsError):
        verify_and_write(tmp_path)


def test_six_thousand_continuation():
    result = continuation_contract(2881261, 6000, "step_2881261", 14)
    assert result["stop_after_step"] == 2887261
    assert result["trainer_epoch"] == 15 and result["data_epoch_index"] == 14
    assert result["required_batch_in_epoch"] == result["required_global_row_cursor_in_epoch"] == 0
    assert result["requires_isolated_zero_cursor_resume_metadata"]
