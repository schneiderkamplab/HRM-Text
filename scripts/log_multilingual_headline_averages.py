#!/usr/bin/env python3
"""Log opt-in versioned populations, never overwrite legacy headline averages."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

try:
    from scripts.headline_population_registry import build_population_row, load_registry
except ModuleNotFoundError:
    from headline_population_registry import build_population_row, load_registry


@dataclass(frozen=True)
class PopulationItem:
    step: int
    epoch: float
    standard_root: list[Path]
    dfm_root: list[Path]
    euroeval_root: list[Path]


def log_atomic(wandb_module: Any, row: dict, *, project: str, run_id: str,
               run_name: str, entity: str | None = None) -> None:
    """One checkpoint row, explicit metric registration, one committed log call."""
    kwargs = dict(project=project, id=run_id, name=run_name, resume='must')
    if entity is not None:
        kwargs['entity'] = entity
    run = wandb_module.init(**kwargs)
    try:
        epoch_key = 'avg_population/epoch'
        wandb_module.define_metric(epoch_key)
        for key in sorted(row):
            if key != epoch_key:
                wandb_module.define_metric(key, step_metric=epoch_key, summary='last')
        wandb_module.log(row, commit=True)
    finally:
        run.finish()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    for suite in ('standard', 'dfm', 'euroeval'):
        parser.add_argument(f'--{suite}-root', f'--additional-{suite}-root', dest=f'{suite}_root',
                            type=Path, action='append', default=[])
    parser.add_argument('--epoch', type=float, required=True)
    parser.add_argument('--step', type=int, required=True)
    parser.add_argument('--project')
    parser.add_argument('--run-id')
    parser.add_argument('--run-name')
    parser.add_argument('--entity')
    parser.add_argument('--report', type=Path, help='Optional local JSON coverage/evidence report')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--include-raw-metrics', action='store_true', help='Also log unambiguous valid source metrics in their native units')
    parser.add_argument('--require-complete', action='store_true', help='Fail rather than log an incomplete population')
    args = parser.parse_args(argv)
    if not math.isfinite(args.epoch) or args.epoch < 0 or args.step < 0:
        parser.error('Nonnegative finite epoch and step required')
    if not args.dry_run and not all((args.project, args.run_id, args.run_name)):
        parser.error('Logging requires --project, --run-id, and --run-name; use --dry-run for local-only computation')
    return args


def main(argv=None):
    args = parse_args(argv)
    registry = load_registry(args.manifest)
    item = PopulationItem(args.step, args.epoch, args.standard_root, args.dfm_root, args.euroeval_root)
    row, report = build_population_row(item, registry)
    if args.include_raw_metrics:
        for population in report['populations'].values():
            for tasks in population['languages'].values():
                for detail in tasks.values():
                    if detail['status'] == 'valid':
                        key, raw = detail['key'], detail['raw_value']
                        if key in row and row[key] != raw:
                            raise ValueError('Conflicting raw metric bindings: ' + key)
                        row[key] = raw
    result = {'row': row, 'coverage': report}
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', dir=args.report.parent, delete=False) as handle:
            name = handle.name
            try:
                json.dump(result, handle, indent=2, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            except BaseException:
                os.unlink(name)
                raise
        try:
            os.replace(name, args.report)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    if args.dry_run:
        return result
    require_complete = args.require_complete or any(
        p['kind'] == 'cross_language' for p in registry['populations'])
    if require_complete and not all(p['complete'] for p in report['populations'].values()):
        raise ValueError('Required average population incomplete; see coverage report')
    import wandb
    log_atomic(wandb, row, project=args.project, run_id=args.run_id, run_name=args.run_name, entity=args.entity)
    return result


if __name__ == '__main__':
    main()
