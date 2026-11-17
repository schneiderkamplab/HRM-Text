import json
import shlex
import pytest
from scripts.b_dfm15_epoch2_switch import command,patch_definition,END,BOUNDARIES
from models.module_learning_rates import windowed_cosine_lr


def test_decay_then_flat_tail():
    for step,expected in [(450000,3e-4),(899999,3e-4),(900000,3e-4),(950000,1.55e-4),(1000000,1e-5),(END,1e-5)]:
        assert windowed_cosine_lr(3e-4,1/30,step,900000,1000000)==pytest.approx(expected)


def test_both_command_formats_have_one_full_horizon():
    before='python pretrain.py epochs=1 lr_decay_start_step=962923 lr_decay_end_step=1025846 stop_after_step=512923 training_total_steps=512923 suspend_after_steps=[500000]'
    for value in (before,shlex.split(before)):
        result=command(value);tokens=shlex.split(result) if isinstance(result,str) else result
        for key,want in [('lr_decay_start_step','900000'),('lr_decay_end_step','1000000'),('epochs','2'),('stop_after_step',str(END))]:
            assert [s for s in tokens if s.startswith(key+'=')]==[key+'='+want]
        assert '512923' in next(t for t in tokens if t.startswith('suspend_after_steps='))


def test_first_epoch_is_not_final_and_next_leg_resumes_it():
    def row(step):
        return dict(job_id=f'b-dfm15-train-{step}',action='train_until_step',deps='b-dfm15-train-500000,b-dfm15-500000-report',metadata_json=json.dumps(dict(stop_after_step=step,command='python pretrain.py epochs=1',completion_checkpoint_tag='epoch_2',cooperative_training=dict(command=['python','pretrain.py','epochs=1'],final_boundary=True))))
    mid=json.loads(patch_definition(row(512923))['metadata_json'])
    assert not mid['cooperative_training']['final_boundary']
    assert 'completion_checkpoint_tag' not in mid
    nxt=patch_definition(row(550000));md=json.loads(nxt['metadata_json'])
    assert md['resume_from_tag']=='step_512923'
    assert nxt['deps']=='b-dfm15-train-512923,b-dfm15-512923-report'
    assert 'lr_decay_start_step=900000' in md['cooperative_training']['command']
    final=json.loads(patch_definition(row(END))['metadata_json'])
    assert final['cooperative_training']['final_boundary']
    assert final['completion_checkpoint_tag']=='epoch_2'


def test_staging_preserves_shared_inference_publication_layout(tmp_path, monkeypatch):
    import sqlite3
    from scripts import b_dfm15_epoch2_switch as switch
    path = tmp_path/'staged.sqlite'
    monkeypatch.setattr(switch, 'STAGED', path)
    monkeypatch.setattr(switch, 'OUT', tmp_path/'receipts')
    monkeypatch.setattr(switch, 'PLAN', tmp_path/'plan')
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE jobs(job_id TEXT PRIMARY KEY, definition TEXT, status TEXT, log_dir TEXT)')
        db.execute('CREATE TABLE dependencies(job_id TEXT, dependency TEXT)')
        for step in [500000,550000]:
            for suffix, action in [('eval-inference','eval_dfm'),('eval','export_dfm_results')]:
                jid=f'b-dfm15-{step}-{suffix}'
                d=dict(job_id=jid,action=action,deps='',metadata_json='{}')
                log=f'/logs/dfm/step_{step}/gec_dala/shard_0_of_2/step_{step}'
                db.execute('INSERT INTO jobs VALUES (?,?,?,?)',(jid,json.dumps(d),'pending',log))
    switch.stage()
    with sqlite3.connect(path) as db:
        logs=[r[0] for r in db.execute("SELECT log_dir FROM jobs WHERE job_id LIKE 'b-dfm15-550000-%'")]
    assert logs == ['/logs/dfm/step_550000/gec_dala/shard_0_of_2/step_550000']*2
