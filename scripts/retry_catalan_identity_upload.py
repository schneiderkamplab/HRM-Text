"""One-shot delayed CPU-only Catalan XXL-wide publication retry."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dfm12.io import lock, write_json
from dfm12.publish_identity_xxl_wide import publish


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--at', type=float, required=True, help='Absolute Unix timestamp')
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    args.state.mkdir(parents=True, exist_ok=True)
    with lock(args.state / '.timer.lock'):
        receipt = dict(due_at=args.at, due_utc=datetime.fromtimestamp(args.at, timezone.utc).isoformat(),
                       status='waiting')
        write_json(args.state / 'status.json', receipt)
        print(json.dumps(receipt), flush=True)
        while time.time() < args.at:
            time.sleep(min(60, args.at-time.time()))
        receipt.update(status='running', started=time.time())
        write_json(args.state / 'status.json', receipt)
        try:
            publish(Path('exports_dfm12/identity-xxl-wide-21'),
                    only='dfm12-identity-xxl-wide-full-bp-ca')
        except Exception as exc:
            receipt.update(status='failed', error=f'{type(exc).__name__}: {exc}', finished=time.time())
            write_json(args.state / 'status.json', receipt)
            raise
        receipt.update(status='verified', finished=time.time())
        write_json(args.state / 'status.json', receipt)
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
