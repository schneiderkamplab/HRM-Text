import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from training_suspend.controller import Controller
from training_suspend.protocol import atomic_write, claim, matches, read_json, steps, submit
from training_suspend.smoke import wait_offloaded, make_data


class FakeCuda:
    def __init__(self, pids):
        self.states = dict.fromkeys(pids, 'running')
        self.actions = []
        self.fail = None
        self.headroom = 100000

    def state(self, pid):
        return self.states[pid]

    def action(self, pid, action):
        self.actions.append((pid, action))
        if self.fail == (pid, action):
            raise RuntimeError('injected failure')
        self.states[pid] = {'lock': 'locked', 'checkpoint': 'checkpointed',
                            'restore': 'locked', 'unlock': 'running'}[action]

    def memory(self):
        return {(pid, 'gpu0'): 32 for pid, state in self.states.items()
                if state != 'checkpointed'}

    def free(self):
        return {'gpu0': self.headroom}


class ProtocolTests(unittest.TestCase):
    def test_full_size_synthetic_data_dimensions(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'data'
            make_data(root, full_size=True)
            metadata = read_json(root / 'metadata.json')
            self.assertEqual(metadata['max_seq_len'], 4097)
            self.assertEqual(metadata['tokenizer_info']['vocab_size'], 262144)
            lengths = np.load(root / 'epoch_0/resp_len.npy')
            self.assertEqual(len(lengths), 1024)
            self.assertTrue(np.all(lengths == 3073))

    def test_queue_validation(self):
        self.assertEqual(steps('8 3 8'), [3, 8])
        for values in ['-1', '0', '1.5', 'foo', [True]]:
            with self.assertRaises(ValueError):
                steps(values)

    def test_claim_does_not_delete_new_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            atomic_write(root / 'launch.json', {})
            submit(root, [5, 2])
            submit(root, [3])
            old, values = claim(root)
            self.assertEqual(values, [2, 3, 5])
            submit(root, [10])
            old.unlink()
            self.assertEqual(claim(root)[1], [10])

    def test_invalid_file_is_quarantined(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            atomic_write(root / 'suspend_after_steps', 'oops')
            self.assertEqual(claim(root), (None, []))
            self.assertEqual(len(list(root.glob('*.rejected.json'))), 1)

    def test_generation_must_match(self):
        self.assertFalse(matches({'job_id': 'a', 'step': 4, 'generation': 1},
                                 {'job_id': 'a', 'step': 4, 'generation': 2}))


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ranks = [{'rank': i, 'pid': 100 + i, 'start_ticks': str(i)} for i in range(2)]
        self.ready = {'job_id': 'job', 'generation': 1, 'step': 7, 'ranks': self.ranks}
        self.generation = self.root / 'generation_000001'
        atomic_write(self.root / 'launch.json', {'job_id': 'job', 'ranks': self.ranks})
        atomic_write(self.root / 'suspend_ready.json', self.ready)
        for rank in self.ranks:
            atomic_write(self.generation / f"ready.{rank['pid']}.json", self.ready | rank)
        self.backend = FakeCuda([100, 101])
        self.controller = Controller(self.root, self.backend)
        p = patch('training_suspend.controller.validate_process')
        p.start()
        self.addCleanup(p.stop)

    def test_success_order_and_idempotent_restore(self):
        self.controller.offload()
        self.assertEqual(self.backend.actions, [(100, 'lock'), (101, 'lock'),
                                               (100, 'checkpoint'), (101, 'checkpoint')])
        self.controller.restore()
        n = len(self.backend.actions)
        self.controller.restore()
        self.assertEqual(len(self.backend.actions), n)
        self.assertTrue((self.generation / 'resume.100').exists())
        self.assertTrue((self.generation / 'resume.101').exists())
        atomic_write(self.root / 'resumed.json', self.ready)
        with self.assertRaisesRegex(RuntimeError, 'already resumed'):
            self.controller.restore()

    def test_partial_offload_recovers_without_false_admission(self):
        self.backend.fail = (101, 'checkpoint')
        with self.assertRaises(RuntimeError):
            self.controller.offload()
        self.assertFalse((self.generation / 'offloaded.json').exists())
        self.backend.fail = None
        Controller(self.root, self.backend).restore()
        self.assertEqual(set(self.backend.states.values()), {'running'})

    def test_partial_restore_does_not_release_any_rank(self):
        self.controller.offload()
        self.backend.fail = (101, 'restore')
        with self.assertRaises(RuntimeError):
            self.controller.restore()
        self.assertFalse(list(self.generation.glob('resume.*')))
        self.backend.fail = None
        self.backend.headroom = 560  # Enough for the remaining 32 MiB + margin, not both.
        self.controller.restore()
        self.assertEqual(len(list(self.generation.glob('resume.*'))), 2)

    def test_memory_and_user_hold(self):
        self.controller.offload()
        self.backend.headroom = 0
        with self.assertRaisesRegex(RuntimeError, 'headroom'):
            self.controller.restore()
        self.backend.headroom = 100000
        (self.root / 'hold').touch()
        with self.assertRaisesRegex(RuntimeError, 'hold'):
            self.controller.restore()

    def test_missing_ready_rejects_before_gpu_operation(self):
        (self.generation / 'ready.101.json').unlink()
        with self.assertRaises(FileNotFoundError):
            self.controller.offload()
        self.assertEqual(self.backend.actions, [])

    def test_restore_before_offload_releases_without_cuda_operations(self):
        self.controller.restore()
        self.assertTrue((self.generation / 'cancelled.json').exists())
        self.assertTrue((self.generation / 'resume.100').exists())
        self.assertEqual(self.backend.actions, [])

    def test_cancel_before_offload(self):
        self.controller.cancel_unoffloaded()
        self.assertTrue((self.generation / 'resume.100').exists())
        with self.assertRaisesRegex(RuntimeError, 'released'):
            self.controller.offload()

    def test_new_gpu_occupant_blocks_restore(self):
        self.controller.offload()
        with patch.object(self.backend, 'memory', return_value={(999, 'gpu0'): 1}):
            with self.assertRaisesRegex(RuntimeError, 'New GPU workload'):
                self.controller.restore()
        self.assertFalse(list(self.generation.glob('resume.*')))

    def test_stale_process_rejects_before_gpu_operation(self):
        with patch('training_suspend.controller.validate_process', side_effect=RuntimeError('stale')):
            with self.assertRaisesRegex(RuntimeError, 'stale'):
                self.controller.offload()
        self.assertEqual(self.backend.actions, [])

    def test_cuda_error_output_is_preserved(self):
        error = subprocess.TimeoutExpired('checkpoint', 60, output=b'partial output', stderr=b'diagnostic')
        with patch.object(self.backend, 'action', side_effect=error):
            with self.assertRaises(subprocess.TimeoutExpired):
                self.controller.transition(self.generation, self.ranks[0], 'checkpoint', 'checkpointed')
        last = json.loads((self.generation / 'operations.jsonl').read_text().splitlines()[-1])
        self.assertEqual(last['stderr'], 'diagnostic')
        self.assertEqual(last['stdout'], 'partial output')

    def test_pause_health_checks_offloaded_state(self):
        self.controller.offload()
        wait_offloaded(Mock(poll=lambda: None), self.backend, self.controller, 0, float('inf'))
        last = json.loads((self.generation / 'operations.jsonl').read_text().splitlines()[-1])
        self.assertEqual(last['owned_gpu_mib'], 0)
        self.backend.states[100] = 'running'
        with self.assertRaisesRegex(RuntimeError, 'Offloaded state changed'):
            wait_offloaded(Mock(poll=lambda: None), self.backend, self.controller, 0, float('inf'))

    def test_pause_checks_launcher_liveness(self):
        self.controller.offload()
        with self.assertRaisesRegex(RuntimeError, 'launcher exited'):
            wait_offloaded(Mock(poll=lambda: 1), self.backend, self.controller, 0, float('inf'))

    def test_requested_early_resume_leaves_restore_to_controller(self):
        self.controller.offload()
        request = self.generation / 'finish_early.request'
        request.touch()
        wait_offloaded(Mock(poll=lambda: None), self.backend, self.controller,
                       7200, float('inf'), request)
        self.assertEqual(set(self.backend.states.values()), {'checkpointed'})
        self.controller.restore()
        self.assertEqual(set(self.backend.states.values()), {'running'})


if __name__ == '__main__':
    unittest.main()
