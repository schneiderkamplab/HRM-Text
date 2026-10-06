import pytest
from scripts import calibrate_xl_eval_capacity as c


def test_non_eager_native_configuration():
    argv=c.server_command(0,59100,.95,512)
    assert '--enforce-eager' not in argv
    assert argv[argv.index('--model')+1]==str(c.MODEL)
    assert argv[argv.index('--chat-template')+1]==str(c.TEMPLATE)
    assert argv[argv.index('--max-model-len')+1]=='4096'
    assert argv[argv.index('--max-num-seqs')+1]=='512'
    assert c.server_command(4,59104,.85,512)[-5:] == argv[-5:]


def test_prometheus_labels_and_counters():
    text='''# TYPE vllm:num_preemptions counter
vllm:num_preemptions_total{model_name="xl-capacity"} 2
vllm:kv_cache_usage_perc{model_name="xl-capacity"} 0.51
vllm:num_requests_running{model_name="xl-capacity"} 32
vllm:num_requests_waiting{model_name="xl-capacity"} 0
'''
    assert c.metrics(text)==dict(preemptions=2,kv=.51,running=32,waiting=0)


@pytest.mark.parametrize('field,value',[('errors',1),('preemptions',1),('kv_peak',.9)])
def test_escalation_stops_on_pressure(field,value):
    r=dict(errors=0,preemptions=0,kv_peak=.51)
    assert c.safe_next(r)
    r[field]=value
    assert not c.safe_next(r)


def test_literal_attachment_resolution():
    assert c.resolve([{'content':'attachment://a'}],{'a':'Exact source'})==[{'content':'Exact source'}]
    with pytest.raises(KeyError):c.resolve('attachment://missing',{})


def test_busy_gpu_failclosed(monkeypatch):
    monkeypatch.setattr(c.subprocess,'check_output',lambda *a,**k:'\n'.join(f'{i}, 180000, 1000' for i in range(8)))
    with pytest.raises(RuntimeError,match='occupied'):c.free_gpus()


def test_other_compute_process_blocks_launch(monkeypatch):
    replies=iter(['\n'.join(f'{i}, 180000, 179999' for i in range(8)),'12345'])
    monkeypatch.setattr(c.subprocess,'check_output',lambda *a,**k:next(replies))
    with pytest.raises(RuntimeError,match='Compute processes'):c.free_gpus()
