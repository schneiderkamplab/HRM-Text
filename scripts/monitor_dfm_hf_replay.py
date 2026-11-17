"""Read-only, low-frequency monitoring of an HF acquisition job."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--input-lock', type=Path, required=True)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--interval', type=float, default=300)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error('--interval must be positive')
    sources = json.loads(args.input_lock.read_text())['hf_sources']
    manifest = args.root / 'dfm1-hf-inputs.json'
    log = args.root / 'monitor.jsonl'
    while True:
        started = time.monotonic()
        state = json.loads(manifest.read_text()) if manifest.exists() else {}
        rows = state.get('hf_sources', [])
        counts = Counter(row['status'] for row in rows)
        try:
            command = Path(f'/proc/{args.pid}/cmdline').read_bytes().replace(b'\0', b' ')
            alive = b'scripts.prepare_dfm_hf_replay' in command
        except FileNotFoundError:
            alive = False
        terminal = state.get('status') in ('inputs_downloaded', 'blocked')
        report = dict(
            time=datetime.now(timezone.utc).isoformat(), pid=args.pid, alive=alive,
            stage='hf_acquisition', status=state.get('status', 'starting'),
            total_sources=len(sources), counts=dict(counts),
            next_unrecorded_source=sources[len(rows)]['name'] if len(rows) < len(sources) else None,
            completed_source_bytes=sum(sum(f.get('size') or 0 for f in row.get('files', []))
                                       for row in rows if row['status'] == 'downloaded'),
            free_bytes=shutil.disk_usage(args.root).free,
            errors=[dict(name=row['name'], error=row.get('error'))
                    for row in rows if row['status'] == 'blocked'],
            unexpected_exit=not alive and not terminal,
        )
        with log.open('a') as stream:
            stream.write(json.dumps(report) + '\n')
            stream.flush()
        print(json.dumps(report), flush=True)
        if terminal or not alive:
            break
        time.sleep(max(0, args.interval - (time.monotonic() - started)))


if __name__ == '__main__':
    main()
