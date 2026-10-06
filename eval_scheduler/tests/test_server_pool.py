from __future__ import annotations

import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

from eval_scheduler.model import Action, Job
from eval_scheduler.runtime import (
    VLLMServerKey,
    VLLMServerLease,
    VLLMServerPool,
    local_service_port,
    managed_judge_port,
    run_standard_openai,
    run_euroeval_openai,
    run_with_vllm_server,
)


def make_job(*, utilization: float = 0.9, checkpoint: str = "step_100000") -> Job:
    return Job(
        job_id="eval-1",
        action=Action.EVAL_STANDARD,
        family="standard",
        name="BoolQ",
        metadata={
            "ckpt_tag": checkpoint,
            "host": "127.0.0.1",
            "hrm_hf_export_dir": "/tmp/model",
            "no_ema": False,
            "port_base": 18000,
            "python_bin": "python",
            "vllm_dtype": "bfloat16",
            "vllm_max_model_len": 4096,
            "vllm_gpu_memory_utilization": utilization,
            "vllm_extra_args": "--enforce-eager",
        },
    )


class VLLMServerPoolTest(unittest.TestCase):
    def test_euroeval_persistent_client_receives_retry_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            job = make_job().with_updates(
                log_dir=directory,
                metadata={**make_job().metadata, "model_prefix": "test", "euroeval_bin": "python guard.py",
                          "euroeval_max_concurrent_calls": 128},
            )
            def invoke(*args, **kwargs):
                return kwargs["callback"]("http://localhost:8000/v1", Path(directory) / "server.log",
                                          MagicMock(), "test-model")
            with patch("eval_scheduler.runtime.run_with_vllm_server", side_effect=invoke), \
                 patch("eval_scheduler.runtime.run_client_with_server_monitor", return_value=1) as client:
                for batch, expected in [(64, "64"), (256, "128")]:
                    self.assertEqual(run_euroeval_openai(job, 0, batch, None), 1)
                    self.assertEqual(client.call_args.kwargs["env"]["EUROEVAL_MAX_CONCURRENT_CALLS"], expected)

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.events: list[str] = []
        self.pool = VLLMServerPool(Path(self.temp_dir.name), self.events.append)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @patch("eval_scheduler.runtime.os.getpid", return_value=999_999)
    def test_local_service_port_stays_in_valid_range(self, _getpid: MagicMock) -> None:
        port = local_service_port(make_job(), 99_999)
        self.assertGreaterEqual(port, 30_000)
        self.assertLess(port, 60_000)

    def test_managed_judge_ports_stay_valid_and_unique(self) -> None:
        job = make_job().with_updates(metadata={**make_job().metadata, "port_base": 59_000})
        ports = {managed_judge_port(job, gpu, shard) for gpu in range(8) for shard in range(8)}

        self.assertEqual(len(ports), 64)
        self.assertGreaterEqual(min(ports), 20_000)
        self.assertLess(max(ports), 60_000)

    @patch("eval_scheduler.runtime.terminate")
    @patch("eval_scheduler.runtime.wait_for_vllm_server", return_value=0)
    @patch("eval_scheduler.runtime.start_vllm_server")
    @patch.object(VLLMServerPool, "_healthy", return_value=True)
    def test_reuses_exact_key(
        self,
        _healthy: MagicMock,
        start: MagicMock,
        _wait: MagicMock,
        _terminate: MagicMock,
    ) -> None:
        process = MagicMock(pid=123)
        process.poll.return_value = None
        start.return_value = process

        first = self.pool.acquire(make_job(), 0)
        second = self.pool.acquire(make_job(), 0)

        self.assertIs(first, second)
        self.assertEqual(first.reuse_count, 1)
        start.assert_called_once()
        self.assertTrue(any(event.startswith("VLLM_REUSE") for event in self.events))

    @patch("eval_scheduler.runtime.start_vllm_server")
    def test_starts_different_gpus_concurrently(self, start: MagicMock) -> None:
        barrier = threading.Barrier(2, timeout=2)

        def wait_for_server(*_args: object, **_kwargs: object) -> int:
            barrier.wait()
            return 0

        start.side_effect = [
            MagicMock(pid=123, poll=MagicMock(return_value=None)),
            MagicMock(pid=456, poll=MagicMock(return_value=None)),
        ]
        with patch(
            "eval_scheduler.runtime.wait_for_vllm_server",
            side_effect=wait_for_server,
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                leases = list(executor.map(lambda gpu: self.pool.acquire(make_job(), gpu), (0, 1)))

        self.assertEqual({lease.key.gpu for lease in leases}, {0, 1})

    @patch("eval_scheduler.runtime.terminate")
    @patch("eval_scheduler.runtime.wait_for_vllm_server", return_value=0)
    @patch("eval_scheduler.runtime.start_vllm_server")
    @patch.object(VLLMServerPool, "_healthy", return_value=True)
    def test_replaces_on_server_configuration_change(
        self,
        _healthy: MagicMock,
        start: MagicMock,
        _wait: MagicMock,
        terminate: MagicMock,
    ) -> None:
        first_process = MagicMock(pid=123)
        second_process = MagicMock(pid=456)
        first_process.poll.return_value = None
        second_process.poll.return_value = None
        start.side_effect = [first_process, second_process]

        first = self.pool.acquire(make_job(utilization=0.9), 0)
        second = self.pool.acquire(make_job(utilization=0.65), 0)

        self.assertIsNot(first, second)
        terminate.assert_called_once_with(first_process)
        self.assertEqual(start.call_count, 2)
        self.assertTrue(
            any("reason_key_mismatch" in event for event in self.events)
        )

    @patch("eval_scheduler.runtime.terminate")
    @patch("eval_scheduler.runtime.wait_for_vllm_server", return_value=0)
    @patch("eval_scheduler.runtime.start_vllm_server")
    @patch.object(VLLMServerPool, "_healthy", side_effect=[False])
    def test_replaces_unhealthy_matching_server(
        self,
        _healthy: MagicMock,
        start: MagicMock,
        _wait: MagicMock,
        terminate: MagicMock,
    ) -> None:
        first_process = MagicMock(pid=123)
        second_process = MagicMock(pid=456)
        start.side_effect = [first_process, second_process]

        self.pool.acquire(make_job(), 0)
        self.pool.acquire(make_job(), 0)

        terminate.assert_called_once_with(first_process)
        self.assertTrue(any("reason_unhealthy" in event for event in self.events))

    def test_failed_callback_invalidates_pooled_server(self) -> None:
        process = MagicMock(pid=123)
        process.poll.return_value = None
        key = VLLMServerKey(
            gpu=0,
            model_path="/tmp/model",
            checkpoint_tag="step_100000",
            use_ema=True,
            python="python",
            host="127.0.0.1",
            dtype="bfloat16",
            max_model_len=4096,
            gpu_memory_utilization=0.9,
            attention_backend="FLASH_ATTN",
            trust_remote_code=False,
            extra_args="--enforce-eager",
            cuda_home="",
        )
        lease = VLLMServerLease(
            key=key,
            process=process,
            base_url="http://127.0.0.1:1/v1",
            health_url="http://127.0.0.1:1/health",
            model_name="pooled-model",
            log_path=Path(self.temp_dir.name) / "server.log",
            started_at=0.0,
        )
        pool = MagicMock()
        pool.acquire.return_value = lease

        status = run_with_vllm_server(
            make_job(),
            0,
            model_name="requested-model",
            port_offset=0,
            log=Path(self.temp_dir.name) / "unused.log",
            callback=lambda *_: 73,
            server_pool=pool,
        )

        self.assertEqual(status, 73)
        pool.invalidate.assert_called_once_with(0, lease, "job_status_73")

    @patch("eval_scheduler.runtime.run_with_vllm_server")
    def test_standard_eval_uses_active_pooled_model_name(
        self,
        run_with_server: MagicMock,
    ) -> None:
        job = make_job()
        job = job.with_updates(
            log_dir=self.temp_dir.name,
            shards=1,
            shard=0,
            metadata={
                **job.metadata,
                "model_prefix": "hrm-test",
                "standard_config": "evaluation/config/dfm6_vllm_benchmarking.yaml",
                "standard_hf_export_dir": "/tmp/model",
            },
        )

        def invoke_callback(*_args: object, **kwargs: object) -> int:
            callback = kwargs["callback"]
            with patch(
                "eval_scheduler.runtime.run_client_with_server_monitor",
                return_value=0,
            ) as run_client:
                with patch("eval_scheduler.runtime.tail", return_value="--- BoolQ ---"):
                    status = callback(
                        "http://127.0.0.1:1/v1",
                        Path(self.temp_dir.name) / "server.log",
                        MagicMock(),
                        "pooled-model",
                    )
                argv = run_client.call_args.args[0]
            self.assertIn("engine=OpenAIEngine", argv)
            self.assertIn("model=pooled-model", argv)
            return status

        run_with_server.side_effect = invoke_callback
        status = run_standard_openai(job, 0, 16, MagicMock())
        self.assertEqual(status, 0)


if __name__ == "__main__":
    unittest.main()
