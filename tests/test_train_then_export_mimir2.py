import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


def module():
    path = Path(__file__).resolve().parents[1] / 'scripts/train_then_export_mimir2.py'
    spec = importlib.util.spec_from_file_location('pilot_export', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_training_precedes_cpu_export(monkeypatch):
    mod = module()
    calls = []
    monkeypatch.setattr(sys, 'argv', ['pilot', '--checkpoint', '/cp', '--output', '/hf',
                                    '--tokenizer-reference', '/reference', '--',
                                    'torchrun', 'pretrain.py', 'gradient_accumulation_steps=4'])
    monkeypatch.setattr(mod.subprocess, 'run', lambda args, **kw: calls.append((args, kw)))
    mod.main()
    assert calls[0][0] == ['torchrun', 'pretrain.py', 'gradient_accumulation_steps=4']
    assert calls[1][1]['env']['CUDA_VISIBLE_DEVICES'] == ''
    assert calls[1][0][-2:] == ['--tokenizer-reference', '/reference']
    assert all(kw['check'] for _, kw in calls)


def test_failed_training_cannot_export(monkeypatch):
    mod = module()
    calls = []
    monkeypatch.setattr(sys, 'argv', ['pilot', '--checkpoint', '/cp', '--output', '/hf',
                                    '--tokenizer-reference', '/reference', '--', 'torchrun'])
    def fail(args, **kw):
        calls.append(args)
        raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(mod.subprocess, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        mod.main()
    assert len(calls) == 1
