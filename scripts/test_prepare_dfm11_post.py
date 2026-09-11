"""Small regression tests for post-mix inventory parsing and token budgets."""
import tempfile
import unittest
from pathlib import Path
import sys
import json
import subprocess

import numpy as np

from prepare_dfm11_post import allocate, task_report, TWICE, FOCUS, EXCLUDE_PREFIXES
from dfm11_post_quality import conversation_selection


class PostPolicyTests(unittest.TestCase):
    def test_sampler_selection_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            task = source / 'task'
            task.mkdir(parents=True)
            (source / 'tokenizer_info.json').write_text(json.dumps({'vocab_size': 65536}))
            np.save(task / 'tokens.npy', np.arange(20, dtype=np.uint32))
            for name, values in dict(inst_start=[0,5,10,15], inst_len=[2]*4,
                                     resp_start=[2,7,12,17], resp_len=[3]*4).items():
                np.save(task / f'{name}.npy', np.asarray(values, dtype=np.uint64))
            mask = root / 'mask.npy'
            np.save(mask, np.asarray([1,3], dtype=np.int64))
            policy = root / 'policy.yaml'
            policy.write_text(f'- prefix: task\n  selection_indices_path: {mask}\n')
            output = root / 'output'
            subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'data_io/sample_tokenized.py'),
                            f'tokenized_path={source}', f'output_path={output}',
                            f'prefix_config_path={policy}', 'epochs=2', 'concat_workers=1'],
                           check=True, capture_output=True, text=True)
            for epoch in range(2):
                actual = np.load(output / f'epoch_{epoch}/inst_start.npy')
                self.assertEqual(sorted(actual.tolist()), [5,15])
            self.assertEqual(len(np.load(output / 'tokens.npy')), 20)
            self.assertEqual(json.loads((output / 'metadata.json').read_text())['total_length'], 10)

    def test_quality_weights_reduce_large_anchor_share(self):
        capacities = {'good': 10000., 'noisy': 10000.}
        result = allocate(capacities, 3000., {'noisy': .25})
        self.assertAlmostEqual(sum(result.values()), 3000.)
        self.assertAlmostEqual(result['noisy'] / result['good'], .25)

    def test_whole_conversation_selection(self):
        rows = [dict(id=str(i), actual_exchanges=3,
                     messages=[{'role': 'assistant'}] * 3,
                     diversity={'topic_id': 'topic', 'interaction_mode': 'mode'},
                     complexity='medium', length_band='short') for i in range(8)]
        indices, original, chosen = conversation_selection(rows, 'seed')
        self.assertEqual((original, chosen, len(indices)), (24, 4, 12))
        self.assertTrue(np.array_equal(indices, conversation_selection(rows, 'seed')[0]))
        for start in range(0, original, 3):
            self.assertIn(sum(i in indices for i in range(start, start + 3)), (0, 3))

    def test_selection_keeps_original_token_offsets(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data_io'))
        from sample_tokenized import Task, TaskIndices, PrefixConfig, apply_selection
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'selected.npy'
            np.save(path, np.array([1, 3]))
            arrays = TaskIndices(*(np.arange(5) * 100 + n for n in range(4)))
            task = Task('test', arrays, PrefixConfig(selection_indices_path=str(path)), mmap_base_offset=123)
            apply_selection(task)
            self.assertEqual(task.indices.inst_start.tolist(), [100, 300])
            self.assertEqual(task.mmap_base_offset, 123)
            np.save(path, np.array([3, 1]))
            with self.assertRaises(ValueError):
                apply_selection(task)

    def test_budget_saturates_small_sources(self):
        capacities = {'small': 100., 'large': 10000.}
        result = allocate(capacities, 3000.)
        self.assertAlmostEqual(sum(result.values()), 3000.)
        self.assertEqual(result['small'], 100.)
        self.assertLessEqual(result['large'], capacities['large'])

    def test_insufficient_capacity_fails(self):
        with self.assertRaises(ValueError):
            allocate({'small': 10}, 11)

    def test_final_fraction_not_additive_fraction(self):
        behavior = 1000.
        anchors = behavior * .33 / .67
        self.assertAlmostEqual(anchors / (behavior + anchors), .33)

    def test_repeated_sources_are_behavior_not_excluded(self):
        self.assertLessEqual(TWICE, FOCUS)
        self.assertFalse(any(n.startswith(EXCLUDE_PREFIXES) for n in TWICE))

    def test_only_task_section_is_parsed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.log'
            path.write_text('### Category Coverage Stats\n'
                            '| **same** | 99 | 99 | 99 | 99 | 99 | 99 |\n'
                            '### Task Coverage Stats\n'
                            '| **same** | 10 (1%) | 1,000 (2%) | 20 | 2,000 | 500 | 1,500 |\n'
                            '### Global Summary\n')
            self.assertEqual(task_report(path), {
                'same': {'rows': 10, 'tokens': 1000, 'sampled_tokens': 2000}})


if __name__ == '__main__':
    unittest.main()
