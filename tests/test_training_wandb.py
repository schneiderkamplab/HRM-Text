import copy
import ast
from pathlib import Path

import pytest

from utils.training_wandb import TrainingWandbLogger


class FakeWandb:
    def __init__(self):
        self.step = 3155000
        self.run = self
        self.definitions = []
        self.rows = []

    def define_metric(self, key, **kwargs):
        self.definitions.append((key, kwargs))

    def log(self, row, **kwargs):
        assert kwargs['commit'] is True
        assert set(kwargs) == {'step', 'commit'}
        assert kwargs['step'] >= self.step
        self.rows.append((kwargs['step'], row))
        self.step = kwargs['step'] + 1


def test_resume_below_history_highwater_drops_no_rows_or_changes_training_state():
    wandb = FakeWandb()
    logger = TrainingWandbLogger(wandb)
    state = dict(step=3154500, cursor=12345, lr=.0003, optimizer={'momentum': 4})
    before = copy.deepcopy(state)
    metrics = {'train/loss': 1.2, 'train/lr': state['lr'], 'bp_steps': 8}
    logger.log(metrics, state['step'])
    logger.log({'val/loss': .9}, state['step'])
    logger.log({'diagnostics/grad_norm': 1.}, state['step'])
    assert state == before
    assert 'train/step' not in metrics
    assert [s for s,r in wandb.rows] == [3155000,3155001,3155002]
    assert all(r['train/step']==3154500 for s,r in wandb.rows)
    assert all(kwargs == {'step_metric':'train/step'} for key,kwargs in wandb.definitions if key!='train/step')


def test_registration_once_and_no_eval_axes_rebinding():
    w=FakeWandb();l=TrainingWandbLogger(w)
    l.log({'train/loss':1.},1);l.log({'train/loss':.8},2)
    assert len(w.definitions)==2
    assert not any('eval' in k or k=='*' for k,kw in w.definitions)


@pytest.mark.parametrize('step',[True,-1,1.5])
def test_invalid_step(step):
    with pytest.raises(ValueError):TrainingWandbLogger(FakeWandb()).log({},step)


def test_conflicting_step():
    with pytest.raises(ValueError):TrainingWandbLogger(FakeWandb()).log({'train/step':4},3)


def test_uneven_optimizer_intervals_preserve_step_panel_spacing():
    w=FakeWandb();l=TrainingWandbLogger(w)
    steps=[3154505,3154510,3154527,3154600]
    for step in steps:l.log({'train/loss':1.},step)
    assert l.logging_offset==495
    assert [s for s,r in w.rows]==[step+495 for step in steps]
    assert [r['train/step'] for s,r in w.rows]==steps


def test_same_step_extra_rows_do_not_compress_next_training_interval():
    w=FakeWandb();l=TrainingWandbLogger(w)
    for step in [3154505,3154505,3154505,3154510,3154520]:l.log({'train/loss':1.},step)
    assert [s for s,r in w.rows]==[3155000,3155001,3155002,3155005,3155015]
    assert l.logging_offset==495


def test_no_highwater_preserves_original_absolute_optimizer_steps():
    w=FakeWandb();w.step=0;l=TrainingWandbLogger(w)
    for step in [0,5,10,100]:l.log({'train/loss':1.},step)
    assert [s for s,r in w.rows]==[0,5,10,100]
    assert l.logging_offset==0


def test_cursor_jump_is_never_rewound_and_initial_offset_stays_stable():
    w=FakeWandb();l=TrainingWandbLogger(w)
    l.log({'train/loss':1.},3154505)
    w.step+=134
    l.log({'train/loss':1.},3154510)
    assert w.rows[-1][0]==3155135
    assert w.rows[-1][1]['train/step']==3154510
    assert l.logging_offset==495


def test_uninitialized_run_fails_without_logging():
    w=FakeWandb();w.run=None
    with pytest.raises(RuntimeError):TrainingWandbLogger(w).log({},0)
    assert not w.rows


def test_pretrain_all_four_logging_sites_use_independent_cursor():
    tree=ast.parse(Path('pretrain.py').read_text())
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
           and isinstance(n.func.value,ast.Name) and n.func.attr=='log']
    assert not [n for n in calls if n.func.value.id=='wandb']
    logging=[n for n in calls if n.func.value.id=='training_wandb']
    assert len(logging)==4
    assert all(not any(k.arg=='step' for k in n.keywords) for n in logging)
