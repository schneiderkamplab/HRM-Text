from unittest.mock import patch
from pathlib import Path
from eval_scheduler.model import Job,Action
from eval_scheduler.runtime import vllm_server_key,start_vllm_server


def job(backend):
    return Job(job_id='embla-test',action=Action.EVAL_STANDARD,family='standard',name='BoolQ',metadata={
        'persistent_server_backend':backend,'ckpt_path':'/tmp/embla-checkpoint','ckpt_tag':'step_50000',
        'hrm_hf_export_dir':'/tmp/embla-export','host':'127.0.0.1','native_server_batch_size':4})


def test_backend_is_part_of_pool_identity():
    native=vllm_server_key(job('embla_native'),0)
    vllm=vllm_server_key(job('vllm'),0)
    assert native.digest != vllm.digest
    assert native.model_path == '/tmp/embla-checkpoint'
    assert native.native_batch_size == 4


def test_native_dispatch_uses_existing_hrm_server():
    with patch('eval_scheduler.runtime.start_hrm_server') as launch:
        j=job('embla_native')
        start_vllm_server(j,0,port=8099,model_name='embla',log=Path('/tmp/test.log'))
        launch.assert_called_once_with(j,0,port=8099,model_name='embla',batch=4,log=Path('/tmp/test.log'))
