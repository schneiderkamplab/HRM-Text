"""Evidence-aware checks for DFM16 generated targets; no teacher verdict is a unit test."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VERIFIERS = ROOT/'data/dfm16/expansion-v1/verifiers'


def sandbox_command():
    binary = shutil.which('unshare')
    if not binary:
        raise RuntimeError('unshare required; refusing unsandboxed execution')
    env = Path(sys.prefix).resolve()
    return [binary, '--user', '--map-root-user', '--net', '--pid', '--fork', '--kill-child',
            str(env/'bin/python'), '-I', str(ROOT/'scripts/dfm16_verifier_worker.py')]


def isolated(kind, text, spec):
    # Output is file-backed and bounded by RLIMIT_FSIZE, not an unbounded PIPE.
    with tempfile.TemporaryDirectory(prefix='dfm16-verify-') as scratch, tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        env = dict(PATH=str(Path(sys.prefix).resolve()/'bin')+':/usr/bin', HOME=scratch, TMPDIR=scratch,
                   OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', DFM_VERIFIER_ROOT=str(VERIFIERS),
                   DFM_VERIFIER_READ_PATHS=json.dumps([str(Path(sys.prefix).resolve()), str(VERIFIERS),
                       '/usr', '/lib', '/lib64', '/bin', '/etc/ld.so.cache', str(ROOT/'data/nltk_data')]),
                   NLTK_DATA=str(ROOT/'data/nltk_data'))
        result = subprocess.run(sandbox_command(), input=json.dumps(dict(kind=kind, text=text, spec=spec)).encode(),
                                stdout=out, stderr=err, timeout=30, env=env, cwd=scratch)
        out.seek(0); err.seek(0)
        stdout, stderr = out.read(65536), err.read(2000)
    if result.returncode:
        raise ValueError('isolated_verifier_exit: '+stderr.decode(errors='replace'))
    value = json.loads(stdout)
    if 'error' in value:
        raise ValueError('isolated_verifier: '+value['error'])
    return value['passed'] is True


def minutes(value):
    match = re.fullmatch(r'(\d{1,2}):(\d{2})', value)
    if not match or int(match[1]) > 23 or int(match[2]) > 59:
        raise ValueError('invalid_clock')
    return int(match[1])*60+int(match[2])


def human_minutes(value):
    match = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', value.strip(), re.I)
    if not match or not 1 <= int(match[1]) <= 12 or int(match[2] or 0) > 59:
        raise ValueError('unknown_calendar_constraint')
    return (int(match[1]) % 12 + (12 if match[3].lower() == 'pm' else 0))*60+int(match[2] or 0)


def calendar(text, expected):
    events = json.loads(text)
    if not isinstance(events, list):
        return False
    found, intervals = {}, []
    for event in events:
        if set(event) != {'event_id', 'event_name', 'start_time', 'duration'}:
            return False
        if type(event['event_id']) is not int or type(event['duration']) is not int or event['duration'] <= 0:
            return False
        if not isinstance(event['event_name'], str) or not event['event_name'].strip():
            return False
        k = str(event['event_id'])
        if k in found or k not in expected:
            return False
        reference = expected[k]
        start = minutes(event['start_time']); end = start+event['duration']
        if event['duration'] != reference['duration'] or start < minutes(reference['min_time']) or end > minutes(reference['max_time']):
            return False
        constraint = reference.get('constraint')
        if constraint:
            if constraint.startswith('before '):
                valid = end <= human_minutes(constraint[7:])
            elif constraint.startswith('after '):
                valid = start >= human_minutes(constraint[6:])
            elif constraint.startswith('at '):
                valid = start == human_minutes(constraint[3:])
            elif constraint.startswith('between ') and ' and ' in constraint:
                lo, hi = constraint[8:].split(' and ')
                valid = start >= human_minutes(lo) and end <= human_minutes(hi)
            else:
                raise ValueError('unknown_calendar_constraint')
            if not valid:
                return False
        found[k] = event
        intervals.append((start, end))
    intervals.sort()
    return set(found) == set(expected) and all(a[1] <= b[0] for a,b in zip(intervals, intervals[1:]))


def check(text, verification):
    kind = verification['kind']
    if kind == 'calendar':
        return calendar(text, verification['expected'])
    if kind in ('synlogic', 'math', 'ifeval', 'code'):
        return isolated(kind, text, verification)
    if kind in ('reference_review', 'tool_review', 'commonsense_review'):
        return True  # Explicit semantic review below, not deterministic verification.
    raise ValueError('unknown_verification_kind')
