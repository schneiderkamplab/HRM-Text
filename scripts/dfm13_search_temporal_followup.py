"""One cached-only pass for date framing and contradictory review outcomes."""
import argparse
import asyncio
import fcntl
import json
from pathlib import Path

from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_followup_v2 as replay

PREFIXES = ('454d90e0', '51c2360a', '0cfb74ac', '42c1b060', 'a1f76a3a',
            '25bdd9ac', '74f0b1aa', 'e19e0b36')

POLICY = (
    'The source prompt was collected historically, but these cached observations were retrieved on 2026-10-01. '
    'A document dated after original_timestamp is not inherently fabricated or simulated. '
    'For relative-date questions explicitly state the historical date interpretation and separately label any '
    'retrieval-time update as of 2026-10-01. Never silently substitute present-day facts for a historical answer. '
    'For explicit historical dates preserve the requested period; if the cache cannot establish it, say so. '
    'Do not declare sourced events hallucinated merely because they postdate the original prompt. '
    'Review verdict must agree with the rationale: rejection needs a concrete factual, grounding, safety or task '
    'failure, not an approving explanation ending in rejection. A district landmark/address can be given as a '
    'representative destination if explicitly labeled, not as the unique address of an entire district. '
    'Unknown source URLs and genuinely unsupported claims remain disallowed. '
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run'])
    parser.add_argument('--source', type=Path, default=Path('data/dfm13/search-calibration-100-20261001-followup2'))
    parser.add_argument('--root', type=Path, default=Path('data/dfm13/search-temporal-followup-20261001'))
    parser.add_argument('--concurrency-per-server', type=int, default=8)
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    if args.command == 'prepare':
        if args.root.exists():
            raise ValueError('new root required')
        jobs = [j for j in json.loads((args.source/'jobs.json').read_text()) if j['id'][:8] in PREFIXES]
        if len(jobs) != len(PREFIXES):
            raise ValueError('target coverage mismatch')
        manifest = json.loads((args.source/'manifest.json').read_text())
        base.atomic(args.root/'jobs.json', jobs)
        for p in (Path(__file__), args.root/'jobs.json', args.source/'manifest.json'):
            manifest['pins'][str(p.resolve())] = base.file_hash(p)
        manifest.update(total=len(jobs), wait_for=str((args.source/'finished.json').resolve()),
                        source=str(args.source.resolve()), created_at=base.now(), policy=POLICY)
        base.atomic(args.root/'manifest.json', manifest)
        print(json.dumps(dict(queued=len(jobs), paid_calls=0)))
    else:
        replay.RUBRIC = replay.RUBRIC.replace(
            'Historical relative dates refer to original_timestamp, not retrieval time. ', '') + POLICY
        with (args.root/'run.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            asyncio.run(replay.run(args))


if __name__ == '__main__':
    main()
