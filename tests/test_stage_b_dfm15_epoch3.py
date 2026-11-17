import json
import shlex
import pytest
from models.module_learning_rates import windowed_cosine_lr
from scripts.stage_b_dfm15_epoch3 import (DECAY_START, END, schedule_command,
                                        replace_steps, configure_train, real_gates)


def test_full_third_epoch_cosine_without_second_epoch_decay():
    for step, expected in [(900000, 3e-4), (1000000, 3e-4),
                           (DECAY_START, 3e-4), ((DECAY_START+END)/2, 1.55e-4),
                           (END, 1e-5)]:
        assert windowed_cosine_lr(3e-4, 1/30, step, DECAY_START, END) == pytest.approx(expected)


def test_commands_replace_old_horizon_in_both_formats():
    old='python pretrain.py epochs=2 +lr_decay_start_step=900000 lr_decay_end_step=1000000 stop_after_step=1025846 training_total_steps=1025846 suspend_after_steps=[650000]'
    for value in (old, shlex.split(old)):
        result=schedule_command(value,[700000,1025846,1500000])
        tokens=shlex.split(result) if isinstance(result,str) else result
        for key,want in [('epochs','3'),('stop_after_step',str(END)),
                         ('training_total_steps',str(END)),('lr_decay_start_step',str(DECAY_START)),
                         ('lr_decay_end_step',str(END))]:
            assert [t for t in tokens if t.lstrip('+').startswith(key+'=')] == [key+'='+want]
        assert 'suspend_after_steps=[700000,1025846,1500000]' in tokens


def test_clone_rewrites_paths_once_without_historical_id_changes():
    old={'job_id':'b-dfm15-1000000-eval-dfm13-step_3250000-merge-600575',
         'deps':'b-dfm15-train-950000', 'path':'/logs/step_1000000/task/step_1000000',
         'boundary':1000000, 'truth':True}
    new=replace_steps(old,{1000000:1050000,950000:1025846})
    assert new['job_id']=='b-dfm15-1050000-eval-dfm13-step_3250000-merge-600575'
    assert new['deps']=='b-dfm15-train-1025846'
    assert new['path']=='/logs/step_1050000/task/step_1050000'
    assert new['boundary']==1050000 and new['truth'] is True
    assert old['boundary']==1000000


def test_epoch_two_is_suspend_and_epoch_three_is_final():
    def row(step):
        return {'metadata_json':json.dumps({'stop_after_step':step,'command':'python pretrain.py epochs=2',
                'completion_checkpoint_tag':'epoch_2','cooperative_training':{'command':['python','pretrain.py','epochs=2'],'final_boundary':True}})}
    middle=json.loads(configure_train(row(DECAY_START),[DECAY_START],'fresh')['metadata_json'])
    assert not middle['cooperative_training']['final_boundary']
    assert 'completion_checkpoint_tag' not in middle
    last=json.loads(configure_train(row(END),[DECAY_START],'fresh')['metadata_json'])
    assert last['completion_checkpoint_tag']=='epoch_3'
    assert last['cooperative_training']['final_boundary']


def test_gates_expand_administrative_rows_to_actual_work():
    defs={'train':{'action':'train_until_step','deps':''},
          'avg':{'action':'average','deps':''},
          'barrier':{'action':'terminal_barrier','deps':'train,avg'},
          'teardown':{'action':'teardown_eval','deps':'barrier'}}
    assert real_gates(['train','teardown'],defs)==['avg','train']
    defs['barrier']['deps']='teardown'
    with pytest.raises(ValueError,match='cycle'):real_gates(['teardown'],defs)
