import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from recover_pilot_evaluations_20261022 import preserve_outputs, terminal
from eval_scheduler.model import Action, Job


def test_recovery_preserves_outputs_and_refuses_conflicts(tmp_path):
    source, target = tmp_path / 'old', tmp_path / 'canonical'
    source.mkdir()
    (source / 'result.log').write_text('original')
    preserve_outputs(source, target)
    assert (target / 'result.log').is_symlink()
    assert (target / 'result.log').read_text() == 'original'
    preserve_outputs(source, target)
    (target / 'result.log').unlink()
    (target / 'result.log').write_text('different')
    with pytest.raises(RuntimeError, match='Conflicting output'):
        preserve_outputs(source, target)


def test_training_barrier_ignores_publication():
    rows = [Job('infer', Action.EVAL_STANDARD, 'standard', 'MATH'),
            Job('merge', Action.MERGE_STANDARD, 'standard', 'MATH')]
    barrier = terminal('pilot-', rows)
    assert barrier.deps == ('infer',)
    assert barrier.deps_mode == 'terminal'
