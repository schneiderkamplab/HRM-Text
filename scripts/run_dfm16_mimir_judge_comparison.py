"""Run two diagnostic Mimir passes in spare VRAM; never touch other GPU owners."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

import httpx

from dfm12.io import file_hash, load, lock, rows, write_json
from scripts.dfm16_mimir_judge import MODEL_PATH, MODEL_ID
from scripts.queue_dfm16_stories_qwen import DEFAULT, prepare_stage, audited_records

ROOT = DEFAULT/'mimir-comparison'
PYTHON = '/home/ucloud/miniforge3/envs/hrm/bin/python'


def prepare(root, probe=False, text_units=False):
    if probe:
        from scripts.dfm16_mimir_probe_cases import cases
        prepare_stage(root/'probe', cases(), 'mimir_short_prompt_controls')
        return
    records = []
    for entry in rows(DEFAULT.parent/'quality-v2/pilot/manual-review-100.jsonl'):
        records.append(dict(entry['candidate'], comparison_cohort='v2', audit_id=entry['candidate']['id']))
    for row in rows(DEFAULT/'manual-review.jsonl'):
        records.append(dict(row, comparison_cohort='v3', audit_id=row['id']))
    if len(records) != 200 or len({r['id'] for r in records}) != 200:
        raise ValueError('Expected 200 unique unchanged conversations')
    if text_units:
        from scripts.dfm16_mimir_text_units import text_units as extract
        prepare_stage(root/'probe', list(extract(records)), 'mimir_prose_units_v1')
        return
    for stage in ('language', 'content'):
        prepare_stage(root/stage, records, f'mimir_{stage}_diagnostic')


def summarize(root, stages=('language', 'content')):
    grouped, decisions = {}, {}
    for stage in stages:
        counts = Counter()
        for source, result in audited_records(root/stage):
            outcome = result.get('review', {}).get('decision', result['status'])
            key = f'{source["comparison_cohort"]}/{source["language"]}/{outcome}'
            counts[key] += 1
            decisions.setdefault(source['id'], dict(cohort=source['comparison_cohort'],
                language=source['language'], task=source['task'], expected=source.get('expected')))[stage] = outcome
        grouped[stage] = dict(counts)
    write_json(root/'summary.json', dict(counts=grouped, decisions=decisions,
        production_authorized=False, note='Diagnostic judgments, not new training acceptance decisions'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--prepared-probe', action='store_true', help='Run existing probe manifest without replacing it')
    parser.add_argument('--text-units', action='store_true', help='Judge each assistant text independently')
    args = parser.parse_args()
    if args.probe and args.text_units:
        parser.error('Choose controls or text units, not both')
    if args.text_units and args.root == ROOT:
        args.root = DEFAULT/'mimir-text-units'
    root = args.root.resolve()
    with lock(root/'.lock'):
        if not args.prepared_probe:
            prepare(root, args.probe, args.text_units)
        stages = ('probe',) if args.probe or args.text_units or args.prepared_probe else ('language', 'content')
        lines = subprocess.check_output(['nvidia-smi', '--query-gpu=index,memory.free',
            '--format=csv,noheader,nounits'], text=True).splitlines()
        free, gpu = max((int(line.split(',')[1]), int(line.split(',')[0])) for line in lines)
        if free < 13500:
            raise RuntimeError(f'Need >=13500 MiB spare VRAM; maximum available {free}; no owners stopped')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        command = [PYTHON, '-m', 'vllm.entrypoints.openai.api_server',
            '--model', str(MODEL_PATH), '--served-model-name', MODEL_ID,
            '--host', '127.0.0.1', '--port', str(port), '--dtype', 'bfloat16',
            '--attention-backend', 'FLASH_ATTN', '--enforce-eager',
            '--no-enable-prefix-caching', '--no-enable-chunked-prefill',
            '--max-model-len', '4096', '--max-num-batched-tokens', '4096',
            '--max-num-seqs', '1', '--gpu-memory-utilization', '0.05',
            '--kv-cache-memory-bytes', str(3584*1024**2), '--seed', '0']
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), OMP_NUM_THREADS='1',
            MKL_NUM_THREADS='1', TOKENIZERS_PARALLELISM='false', WANDB_MODE='disabled',
            VLLM_USE_FLASHINFER_SAMPLER='0', CUDA_HOME='/home/ucloud/miniforge3/envs/hrm',
            PATH='/home/ucloud/miniforge3/envs/hrm/bin:'+os.environ['PATH'])
        write_json(root/'launch.json', dict(command=command, gpu=gpu, free_mib=free,
            model=str(MODEL_PATH), config_sha256=file_hash(MODEL_PATH/'config.json'),
            concurrency_per_server=128, max_active_sequences=1))
        with (root/'server.log').open('a') as log:
            server = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            write_json(root/'status.json', dict(phase='starting_server', pid=server.pid, gpu=gpu, port=port))
            deadline = time.monotonic()+1200
            while True:
                if server.poll() is not None:
                    raise RuntimeError('Owned Mimir server exited; inspect server.log')
                if time.monotonic() > deadline:
                    raise TimeoutError('Mimir server startup timeout')
                try:
                    response = httpx.get(f'http://127.0.0.1:{port}/v1/models', timeout=2, trust_env=False)
                    if response.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(5)
            for stage in stages:
                state = root/stage/'audit/pipeline/state.json'
                if state.exists() and load(state)['phase'] == 'complete':
                    continue
                write_json(root/'status.json', dict(phase=stage, gpu=gpu, server_pid=server.pid, port=port))
                subprocess.run([PYTHON, '-m', 'audit_pipeline', f'story-mimir-{stage}',
                    '--root', str(root/stage), '--output', str(root/stage/'audit'),
                    '--model', MODEL_ID, '--ports', str(port), '--concurrency', '128'], check=True)
                if load(state)['phase'] != 'complete':
                    raise RuntimeError(f'Incomplete {stage}')
            summarize(root, stages)
            write_json(root/'status.json', dict(phase='complete', production_authorized=False))
        except BaseException as exc:
            write_json(root/'status.json', dict(phase='failed', error=repr(exc)))
            raise
        finally:
            if server.poll() is None:
                os.killpg(server.pid, signal.SIGTERM)
                try:
                    server.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(server.pid, signal.SIGKILL)
                    server.wait()


if __name__ == '__main__':
    main()
