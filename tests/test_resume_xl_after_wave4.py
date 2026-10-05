from scripts import resume_xl_after_wave4 as watcher


def test_progress_ignores_commands_and_resume_metadata():
    text='command stop_after_step=3100000 resume_step=3081500\nResumed: step=3081500\n'
    assert watcher.actual_progress_steps(text)==[]
    text+='\r 93%|#########3| 3081500/3325079 [00:00<?, ?it/s]'
    assert watcher.actual_progress_steps(text)==[3081500]
    text+='\r 93%|#########3| 3081510/3325079 [01:10<20:00, 5.0s/it]\n'
    assert watcher.actual_progress_steps(text)==[3081500,3081510]


def test_blocked_targets_do_not_prevent_successful_runnable_pass():
    launch=dict(pid=1,children=[dict(pid=i) for i in range(2,10)])
    doc=dict(runnable_pass_success=True,active=0,exits=[0]*8,full_target_complete=False)
    assert watcher.pass_finished(doc,launch,lambda _:False)
    assert not watcher.pass_finished(doc,launch,lambda p:p['pid']==2)
    assert not watcher.pass_finished(dict(doc,active=1),launch,lambda _:False)
    assert not watcher.pass_finished(dict(doc,exits=[0]*7+[1]),launch,lambda _:False)


def test_explicit_release_required_after_recovery_disposition():
    good=dict(gpu_work_complete=True,all_shared_gpu_clients_finished=True,remaining_gpu_work=0,
        recovery_disposition_final=True,authorize_training_resume=True,
        campaign_root=str(watcher.CAMPAIGN),server_root=str(watcher.SERVERS),plan=str(watcher.PLAN))
    assert watcher.release_authorized(good)
    assert not watcher.release_authorized({})
    assert not watcher.release_authorized(dict(good,remaining_gpu_work=1))
    assert not watcher.release_authorized(dict(good,recovery_disposition_final=False))
    assert not watcher.release_authorized(dict(good,server_root='/foreign'))
    assert not watcher.release_authorized(dict(good,authorize_training_resume=False))
