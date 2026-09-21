"""Policy regressions: accepting a known fallback must never hide another finding."""
import importlib.util
from pathlib import Path
import unittest
import json
import subprocess
import sys
import tempfile

__all__ = []

_SPEC = importlib.util.spec_from_file_location('cuda_memcheck', Path(__file__).with_name('cuda_memcheck.py'))
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def _log(*diagnostics, summary=None):
    blocks = ['COMPUTE-SANITIZER', *diagnostics,
              f'ERROR SUMMARY: {len(diagnostics) if summary is None else summary} errors']
    return '\n=========\n'.join('========= ' + x for x in blocks) + '\n'


def _api(call, code='cudaErrorGraphExecUpdateFailure (error 910)'):
    return f'Program hit {code} on CUDA API call to {call}.'


class MemcheckPolicyTests(unittest.TestCase):
    def test_clean(self):
        self.assertTrue(_MODULE._classify(_log(), 0, False)['pass'])

    def test_known_pair(self):
        log = _log(_api('cudaGraphExecUpdate'), _api('cudaGetLastError'))
        self.assertTrue(_MODULE._classify(log, 0, True)['pass'])
        self.assertFalse(_MODULE._classify(log, 0, False)['pass'])

    def test_stack_and_description(self):
        update = _api('cudaGraphExecUpdate').replace(' on CUDA', ' due to "update constraints" on CUDA')
        update += '\n========= Saved host backtrace up to driver entry point\n========= Host Frame: ggml_cuda_graph_update_executable'
        self.assertTrue(_MODULE._classify(_log(update, _api('cudaGetLastError')), 0, True)['pass'])

    def test_runner_preserves_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool = root / 'compute-sanitizer'
            tool.write_text('#!' + sys.executable + '\n' +
                'import sys, subprocess\nfrom pathlib import Path\n' +
                "i = sys.argv.index('--log-file')\n" +
                "Path(sys.argv[i+1]).write_text('========= COMPUTE-SANITIZER\\n=========\\n========= ERROR SUMMARY: 0 errors\\n')\n" +
                'sys.exit(subprocess.run(sys.argv[i+2:]).returncode)\n')
            tool.chmod(0o755)
            for name, program, expected in [
                ('success', "print('test passed')", 0),
                ('failure', "print('test passed'); raise SystemExit(3)", 1),
                ('incomplete', "print('not finished')", 1),
            ]:
                out = root / name
                run = subprocess.run([sys.executable, str(Path(_MODULE.__file__)),
                    '--sanitizer', str(tool), '--output', str(out), '--expect', 'test passed',
                    '--', sys.executable, '-c', program], capture_output=True, text=True)
                self.assertEqual(run.returncode, expected, run.stdout + run.stderr)
                result = json.loads((out / 'result.json').read_text())
                self.assertEqual(result['pass'], expected == 0)
                self.assertTrue((out / 'work').is_dir())

    def test_fail_closed(self):
        pair = [_api('cudaGraphExecUpdate'), _api('cudaGetLastError')]
        cases = [
            ('missing', '', 0),
            ('truncated', '========= COMPUTE-SANITIZER\n', 0),
            ('application failure', _log(*pair), 1),
            ('signal', _log(), -11),
            ('memory error', _log(*pair, 'Invalid __global__ read of size 4 bytes'), 0),
            ('hidden memory error', _log(pair[0] + '\n========= Invalid __global__ read'), 0),
            ('different API', _log(_api('cudaMalloc')), 0),
            ('different error', _log(_api('cudaGraphExecUpdate', 'cudaErrorIllegalAddress (error 700)')), 0),
            ('unpaired clear', _log(pair[1]), 0),
            ('unpaired update', _log(pair[0]), 0),
            ('wrong order', _log(*pair[::-1]), 0),
            ('missing diagnostics', _log(*pair, summary=4), 0),
            ('leak', _log('Leaked 64 bytes at 0x1234'), 0),
            ('unknown format', 'new format\n' + _log(), 0),
            ('duplicate summary', _log() + '=========\n========= ERROR SUMMARY: 0 errors\n', 0),
        ]
        for name, log, status in cases:
            with self.subTest(name=name):
                self.assertFalse(_MODULE._classify(log, status, True)['pass'])


if __name__ == '__main__':
    unittest.main()
