#!/usr/bin/env python3
"""Read-only DFM11 queue/score report. No W&B API or directory-wide scans."""
import argparse
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
 'transformer48': 'Transformer48 causal / AT',
 'bfull-dfm11': 'B causal / AT, full BP',
 'bauto-dfm11': 'B causal / AT, LR-auto',
 'bprefix-dfm11': 'B PrefixLM / TO',
 'btarget-dfm11': 'B causal / TO',
 'tprefix-dfm11': 'Transformer48 PrefixLM / TO',
 'ttarget-dfm11': 'Transformer48 causal / TO',
 'bmixed-dfm11': 'B MixedLM / TO',
 'tmixed-dfm11': 'Transformer48 MixedLM / TO',
 'sandwich-dfm11': 'Sandwich B PrefixLM / TO',
 'ouro-dfm11': 'Ouro B, four loops, PrefixLM / TO',
 'embla-causal-dfm11': 'Embla causal / AT',
 'embla-prefix-dfm11': 'Embla PrefixLM / TO',
 'embla-loop-dfm11': 'Embla, four decoder loops, PrefixLM / TO',
 'bcycles-dfm11': 'B sampled recursion BP16, PrefixLM / TO',
}
IDEAS = ['Append-only MixedLM / TO', 'MixedLM+ bucketed bidirectional / TO',
         'Mixed-objective batch training',
         'Minimir CPT: sampled recursion',
         'Minimir CPT: transition to CausalLM',
         'Minimir CPT: transition to MixedLM']


def prefix(job):
    return re.split(r'-(?:step_\d+|epoch_\d+)-', job)[0]


def schedule_order(trains):
    """Collapse eval-block references onto their training boundary, then sort DAG."""
    pending = {k: v for k, v in trains.items() if v['status'] in ('pending', 'running')}
    deps = {}
    for k, v in pending.items():
        parents = set()
        for dep in v['definition'].get('deps', '').split(','):
            parent = dep.split('-eval-', 1)[0] + '-train' if '-eval-' in dep else dep
            if parent in pending and parent != k:
                parents.add(parent)
        deps[k] = parents
    ordered = []
    while deps:
        ready = [k for k, parents in deps.items() if not parents]
        if not ready:
            raise ValueError('Cycle in pending training boundary dependencies')
        ready.sort(key=lambda k: (pending[k]['status'] != 'running', pending[k]['position']))
        for k in ready:
            ordered.append(k)
            del deps[k]
        for parents in deps.values():
            parents.difference_update(ready)
    return list(dict.fromkeys(prefix(k) for k in ordered))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=Path('/var/tmp/dfm11-architecture-comparison/jobs.sqlite'))
    parser.add_argument('--cache', type=Path, default=ROOT/'logs/diagnostics/dfm11-table-cache.json')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--refresh', action='store_true', help='Re-read known average logs; still no W&B directory scan')
    args = parser.parse_args()
    cache = json.loads(args.cache.read_text()) if args.cache.exists() else {'scores': {}, 'logs': {}}
    scores = cache['scores']
    # Bootstrap from preserved reports once; subsequent calls inspect only known completed average jobs.
    if not cache.get('seeded'):
        old = ROOT/'logs/diagnostics/dfm11-all-checkpoints-20261115.json'
        if old.exists():
            for v in json.loads(old.read_text()).values():
                for r in v['rows']:
                    scores.setdefault(v['run'], {})[str(int(r['headline_avg_v3/train_step']))] = {'value': r['headline_avg_v3/overall'], 'source': str(old)}
        latest = ROOT/'logs/diagnostics/dfm11-headline-latest-20261117.json'
        if latest.exists():
            for r in json.loads(latest.read_text()):
                scores.setdefault(r['run'], {})[str(int(r['step']))] = {'value': r['overall'], 'source': r['source']}
        cache['seeded'] = True
    conn = sqlite3.connect(f'file:{args.db}?mode=ro', uri=True)
    trains, groups = {}, {}
    for k, pos, status, raw in conn.execute("SELECT job_id,position,status,definition FROM jobs WHERE job_id LIKE '%-train'"):
        d = json.loads(raw)
        m = json.loads(d.get('metadata_json', '{}'))
        trains[k] = dict(position=pos, status=status, definition=d)
        g = groups.setdefault(prefix(k), {'run': m.get('wandb_run_id'), 'states': [], 'epoch_done': False})
        g['states'].append(status)
        g['epoch_done'] |= '-epoch_1-train' in k and status == 'done'
    warnings = []
    for k, status, raw, logdir in conn.execute("SELECT job_id,status,definition,log_dir FROM jobs WHERE job_id LIKE '%average%' AND status='done'"):
        if prefix(k) not in groups:
            continue
        d = json.loads(raw); m = json.loads(d.get('metadata_json', '{}'))
        if not m.get('atomic_v3_averages') or m.get('average_scope') != 'all':
            continue
        path = Path(logdir)/(d['name']+'.log')
        try:
            stat = path.stat(); signature = [stat.st_mtime_ns, stat.st_size]
            if not args.refresh and cache['logs'].get(str(path)) == signature:
                continue
            text = path.read_text(errors='replace')
            matches = re.findall(r'(?:/work/dfm/HRM-Text/|\./)?wandb/(run-[^/\s]+)', text)
            found = False
            for name in reversed(list(dict.fromkeys(matches))):
                summary = ROOT/'wandb'/name/'files/wandb-summary.json'
                if not summary.exists():
                    continue
                r = json.loads(summary.read_text()); step = r.get('headline_avg_v3/train_step')
                if step != m.get('eval_step') or 'headline_avg_v3/overall' not in r:
                    continue
                scores.setdefault(m['wandb_run_id'], {})[str(int(step))] = {'value': r['headline_avg_v3/overall'], 'source': str(summary)}
                found = True; break
            if found:
                cache['logs'][str(path)] = signature
            else:
                warnings.append('No matching published summary: '+k)
        except (OSError, ValueError) as e:
            warnings.append(f'{k}: {e}')
    order = schedule_order(trains)
    order += [p for p in LABELS if p in groups and p not in order]
    rows = []
    for p in order:
        g = groups[p]; states = g['states']
        status = 'Current' if 'running' in states else 'Continue' if 'pending' in states and 'done' in states else 'Queued' if 'pending' in states else 'Complete' if g['epoch_done'] else 'Stopped'
        values = scores.get(g['run'], {})
        cells = [f"{values[str(s)]['value']*100:.2f}" if str(s) in values else '·' for s in range(50000,350001,50000)]
        end = [int(s) for s in values if int(s)>350000]
        cells.append(f"{values[str(max(end))]['value']*100:.2f}" if g['epoch_done'] and end else '·')
        rows.append([LABELS.get(p,p),status,*cells])
    rows += [[idea,'Idea only',*(['·']*8)] for idea in IDEAS]
    args.cache.parent.mkdir(parents=True,exist_ok=True)
    temp = args.cache.with_suffix('.tmp'); temp.write_text(json.dumps(cache,indent=2)+'\n');temp.replace(args.cache)
    result = dict(metric='headline_avg_v3/overall (%)', rows=rows, warnings=warnings, source=str(args.db))
    if args.json:
        print(json.dumps(result,indent=2));return
    headers = ['Experiment','Status','50K','100K','150K','200K','250K','300K','350K','Epoch 1']
    widths = [max(len(row[i]) for row in [headers,*rows]) for i in range(len(headers))]
    for row in [headers,*rows]:
        print('  '.join(cell.ljust(w) for cell,w in zip(row,widths)).rstrip())
    if warnings:
        print(f'\n{len(warnings)} aggregate receipts lack matching summaries; retained cached scores. Use --json for details.')

if __name__ == '__main__':
    main()
