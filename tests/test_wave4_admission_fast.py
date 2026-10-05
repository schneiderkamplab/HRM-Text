import pytest
from dfm12.wave4_admission_fast import admission_metrics,controller
from dfm12.multilingual_quarter import admission_metrics as original,AdmissionGate
from dfm12.wave4_batched_runtime import Owner


@pytest.mark.parametrize('text',[
    'vllm:kv_cache_usage_perc 0.2\nvllm:num_requests_waiting 12\n',
    '# TYPE vllm:kv_cache_usage_perc gauge\nvllm:kv_cache_usage_perc{model="x",a="a\\\"b"} 0.2\nvllm:kv_cache_usage_perc{model="y"} 0.4\nvllm:num_requests_waiting 0\n',
    'vllm:gpu_cache_usage_perc 0.9\nvllm:num_requests_waiting 128\nother_histogram_bucket{a="x"} 2\n',
    '  vllm:kv_cache_usage_perc\t0.1 123\nvllm:num_requests_waiting 3\n',
])
def test_exact_values(text):assert admission_metrics(text)==original(text)


@pytest.mark.parametrize('text',[
    'vllm:kv_cache_usage_perc_extra 0.2\nvllm:num_requests_waiting 0',
    'vllm:kv_cache_usage_perc NaN\nvllm:num_requests_waiting 0',
    'vllm:kv_cache_usage_perc 1.1\nvllm:num_requests_waiting 0',
    'vllm:kv_cache_usage_perc .2\nvllm:num_requests_waiting -1',
    'vllm:kv_cache_usage_perc .2\nvllm:num_requests_waiting +Inf',
    'vllm:kv_cache_usage_perc{broken 0.2\nvllm:num_requests_waiting 0',
])
def test_invalid_signals_fail_closed(text):
    with pytest.raises(ValueError):admission_metrics(text)


def test_private_binding():
    owner=Owner()
    try:
        c=controller(owner)
        assert c.AdmissionGate.admit.__globals__['admission_metrics'] is admission_metrics
        assert AdmissionGate.admit.__globals__['admission_metrics'] is original
    finally:owner.close()
