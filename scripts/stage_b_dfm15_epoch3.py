"""Prepare (never activate) a B third-epoch database from an online SQLite backup."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shlex
import sqlite3
import time

EPOCH_STEPS = 512923
DECAY_START = 2 * EPOCH_STEPS
END = 3 * EPOCH_STEPS
NEW_BOUNDARIES = [*range(1050000, 1500001, 50000), END]
LIVE = Path('/tmp/dfm15-B-production/jobs.sqlite')
ROOT = Path('/work/dfm/HRM-Text')
OUT = ROOT / 'logs/scheduler/B_dfm15_gemma4_epoch1_20261103/epoch3-stage-20261105'
CONTROL = ROOT / 'logs/training/B-dfm15-gemma4-epoch1/cooperative_epoch3_staged_20261105'


def schedule_command(value, boundaries):
    tokens = shlex.split(value) if isinstance(value, str) else list(value)
    overrides = dict(epochs='3', training_total_steps=str(END), stop_after_step=str(END),
                     lr='3e-4', lr_decay_start_step=str(DECAY_START),
                     lr_decay_end_step=str(END), lr_min_ratio=str(1 / 30),
                     suspend_after_steps='[' + ','.join(map(str, boundaries)) + ']')
    tokens = [t for t in tokens if t.lstrip('+').split('=', 1)[0] not in overrides]
    tokens += [f'{k}={v}' for k, v in overrides.items()]
    return shlex.join(tokens) if isinstance(value, str) else tokens


def replace_steps(value, mapping):
    """Replace complete numeric tokens once, including paths and embedded command strings."""
    if isinstance(value, str):
        return re.sub(r'(?<!\d)(' + '|'.join(map(str, mapping)) + r')(?!\d)',
                      lambda m: str(mapping[int(m[0])]), value)
    if isinstance(value, dict):
        return {k: replace_steps(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_steps(v, mapping) for v in value]
    if isinstance(value, int) and not isinstance(value, bool):
        return mapping.get(value, value)
    return value


def configure_train(d, boundaries, control):
    d = copy.deepcopy(d)
    m = json.loads(d['metadata_json']); step = int(m['stop_after_step'])
    m['command'] = schedule_command(m['command'], boundaries)
    co = m['cooperative_training']
    co['command'] = schedule_command(co['command'], boundaries)
    co['control_root'] = str(control)
    co['final_boundary'] = step == END
    if step == END:
        m['completion_checkpoint_tag'] = 'epoch_3'
    else:
        m.pop('completion_checkpoint_tag', None)
    m['eval_epoch'] = step / EPOCH_STEPS
    d['metadata_json'] = json.dumps(m, sort_keys=True)
    return d


def real_gates(ids, definitions):
    """Administrative teardown/barriers cannot serve as work-completion gates."""
    result = set(); visiting = set()
    def visit(jid):
        if jid in visiting:
            raise ValueError('Dependency cycle: ' + jid)
        d = definitions[jid]
        if d['action'] in ('terminal_barrier', 'teardown_eval'):
            visiting.add(jid)
            for dep in filter(None, d.get('deps', '').split(',')): visit(dep)
            visiting.remove(jid)
        else:
            result.add(jid)
    for jid in ids: visit(jid)
    return sorted(result)


def definition_hash(db):
    digest = hashlib.sha256()
    for jid, definition in db.execute('SELECT job_id,definition FROM jobs ORDER BY job_id'):
        digest.update((jid + '\n' + definition + '\n').encode())
    return digest.hexdigest()


def stage(source=LIVE, output=OUT):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    destination = output / 'jobs.sqlite'
    local_destination = Path(source).parent / 'jobs_epoch3_stage.sqlite'
    if local_destination.exists(): raise FileExistsError(local_destination)
    if destination.exists(): raise FileExistsError(destination)
    with sqlite3.connect(f'file:{source}?mode=ro', uri=True) as src, sqlite3.connect(destination) as db:
        src.backup(db)
    with sqlite3.connect(destination) as db:
        db.row_factory = sqlite3.Row
        original = [dict(r) for r in db.execute('SELECT * FROM jobs ORDER BY position')]
        before_hash = definition_hash(db)
        definitions = {r['job_id']: json.loads(r['definition']) for r in original}
        train_template = next(r for r in original if r['job_id'] == 'b-dfm15-train-1000000')
        eval_templates = [r for r in original if r['job_id'].startswith('b-dfm15-1000000-')]
        assert len(eval_templates) == 2203
        future = [r for r in original if definitions[r['job_id']]['action'] == 'train_until_step'
                  and r['status'] in ('pending', 'running')]
        boundaries = sorted({int(json.loads(definitions[r['job_id']]['metadata_json'])['stop_after_step'])
                             for r in future} | set(NEW_BOUNDARIES))
        suspensions = [s for s in boundaries if s < END]
        additions = []; previous = DECAY_START; position = max(r['position'] for r in original)
        for step in NEW_BOUNDARIES:
            mapping = {1000000: step, 950000: previous}
            for template in [train_template, *eval_templates]:
                r = copy.deepcopy(template)
                d = replace_steps(json.loads(r['definition']), mapping)
                m = json.loads(d['metadata_json'])
                m['eval_step'] = step; m['eval_epoch'] = step / EPOCH_STEPS
                if 'xl_boundary' in m: m['xl_boundary'] = step
                d['metadata_json'] = json.dumps(m, sort_keys=True)
                if d['action'] == 'train_until_step': d = configure_train(d, suspensions, CONTROL)
                r.update(job_id=d['job_id'], definition=json.dumps(d, sort_keys=True),
                         status='pending', attempt=0, token=None,
                         log_dir=replace_steps(r['log_dir'], mapping))
                position += 1; r['position'] = position
                definitions[r['job_id']] = d; additions.append(r)
            previous = step
        changed = []; copied_claims = []
        for r in original:
            if r in future:
                d = configure_train(definitions[r['job_id']], suspensions, CONTROL)
                definitions[r['job_id']] = d; r['definition'] = json.dumps(d, sort_keys=True)
                changed.append(r['job_id'])
            if r['status'] == 'running':
                copied_claims.append({'job_id': r['job_id'], 'attempt': r['attempt'], 'token': r['token']})
                # Claims belong only to the live coordinator, never to the staged copy.
                r.update(status='pending', attempt=0, token=None)
        for r in [*original, *additions]:
            d = definitions[r['job_id']]
            if r['status'] != 'pending' or d['action'] not in ('train_until_step', 'wait_checkpoint'): continue
            deps = real_gates(filter(None, d.get('deps', '').split(',')), definitions)
            assert r['job_id'] not in deps
            d['deps'] = ','.join(deps)
            d['deps_mode'] = 'terminal' if d['action'] == 'train_until_step' else 'success'
            r['deps_mode'] = d['deps_mode']; r['definition'] = json.dumps(d, sort_keys=True)
        columns = list(original[0])
        db.execute('BEGIN IMMEDIATE')
        for r in original:
            db.execute('UPDATE jobs SET definition=?,deps_mode=?,status=?,attempt=?,token=? WHERE job_id=?',
                       (r['definition'],r['deps_mode'],r['status'],r['attempt'],r['token'],r['job_id']))
        db.executemany(f"INSERT INTO jobs ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                       [[r[k] for k in columns] for r in additions])
        db.execute('DELETE FROM dependencies')
        for r in [*original, *additions]:
            d = json.loads(r['definition'])
            db.executemany('INSERT INTO dependencies(job_id,dependency) VALUES (?,?)',
                           [(r['job_id'], dep) for dep in filter(None, d.get('deps', '').split(','))])
        # Explicitly non-dispatchable review copy; this lock does not affect live training.
        db.execute('UPDATE administration SET locked=1')
        db.commit()
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('SELECT 1 FROM dependencies d LEFT JOIN jobs j ON d.dependency=j.job_id WHERE j.job_id IS NULL LIMIT 1').fetchone()
        assert not db.execute("SELECT 1 FROM jobs WHERE status='running' OR token IS NOT NULL LIMIT 1").fetchone()
        staged_hash = definition_hash(db)
    with sqlite3.connect(f'file:{source}?mode=ro', uri=True) as src:
        assert definition_hash(src) == before_hash, 'Live definitions changed concurrently; review snapshot'
    with sqlite3.connect(destination) as snapshot, sqlite3.connect(local_destination) as local:
        snapshot.backup(local)
    receipt = dict(created_at=time.time(), source=str(source), database=str(local_destination),
                   persistent_snapshot=str(destination),
                   activation='not activated; staged administrative lock deliberately set',
                   source_definition_sha256=before_hash, staged_definition_sha256=staged_hash,
                   epoch_steps=EPOCH_STEPS, end_step=END, decay_start=DECAY_START, decay_end=END,
                   peak_lr=3e-4, floor_lr=1e-5, suspension_steps=suspensions,
                   added_boundaries=NEW_BOUNDARIES, added_rows=len(additions), rows=len(original)+len(additions),
                   modified_training_rows=changed, copied_claims=copied_claims,
                   control_root=str(CONTROL),
                   activation_requirements=['Reconcile live statuses at the selected checkpoint pause; do not replace live DB with this stale snapshot.',
                     'The active trainer already loaded its old schedule. Activate with a controlled checkpoint restart and exactly one recovery supervisor.',
                     'Keep optimizer/EMA and exact data cursor, and run continuation preflight before resuming.'])
    (output/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ('database','rows','added_rows','decay_start','decay_end','activation')},indent=2))
    return receipt


if __name__ == '__main__':
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--source',type=Path,default=LIVE)
    parser.add_argument('--output',type=Path,default=OUT)
    args=parser.parse_args();stage(args.source,args.output)
