"""Read-only dashboard for a standalone EuroEval scheduler's JSON telemetry."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table


def read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def render(root):
    state = read(root / 'scheduler-state.json')
    telemetry = read(root / 'telemetry/latest.json')
    counts = Counter(j['state'] for j in state.get('jobs', []))
    age = time.time() - telemetry.get('timestamp', 0)
    header = Panel(f'{root.name}\n{dict(counts)} | telemetry age {age:.0f}s', title='Active EuroEval — read only')
    gpu = Table('GPU', 'Clients', 'Running', 'Waiting', 'Gen tok/s', 'GPU util', 'Free GiB')
    for row in telemetry.get('servers', []):
        metrics = row.get('gpu_metrics', {})
        gpu.add_row(str(row['gpu']), row.get('language', ''), str(int(row.get('num_requests_running', 0))),
                    str(int(row.get('num_requests_waiting', 0))), f"{row.get('generation_tokens_per_second', 0):.0f}",
                    f"{metrics.get('util_pct', 0):.0f}%", f"{metrics.get('free_mib', 0)/1024:.1f}")
    jobs = Table('Language', 'Mode', 'State', 'Phase / error')
    for job in state.get('jobs', []):
        if job['state'] not in ('running', 'failed'):
            continue
        phase = read(root / job['mode'] / job['language'] / 'phase.json').get('phase', '')
        error = job.get('error', '').replace('\n', ' ')
        jobs.add_row(job['language'], job['mode'], job['state'], (error if job['state'] == 'failed' else phase)[:130])
    return Group(header, gpu, jobs)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('root', type=Path); args = p.parse_args()
    with Live(render(args.root), refresh_per_second=1, screen=True) as live:
        while True:
            time.sleep(5)
            live.update(render(args.root))
