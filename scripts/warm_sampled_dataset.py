"""Read immutable sampled data sequentially to warm the filesystem page cache."""
import argparse
import json
import threading
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--epoch', type=int, default=0)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    paths = [args.dataset / f'epoch_{args.epoch}' / f'{key}.npy'
             for key in ('inst_len', 'resp_len', 'inst_start', 'resp_start')]
    paths.append(args.dataset / 'tokens.npy')
    sizes = {str(p): p.stat().st_size for p in paths}
    state = {'started': time.time(), 'total_bytes': sum(sizes.values()),
             'read_bytes': 0, 'completed_files': [], 'status': 'reading'}
    lock = threading.Lock()

    def read():
        try:
            buffer = bytearray(16 * 1024 * 1024)
            for path in paths:
                with lock:
                    state['current_file'] = str(path)
                    state['current_file_read_bytes'] = 0
                with path.open('rb', buffering=0) as src:
                    while True:
                        if (args.output / 'stop.request').exists():
                            with lock:
                                state['status'] = 'stopped'
                            return
                        n = src.readinto(buffer)
                        if not n:
                            break
                        with lock:
                            state['read_bytes'] += n
                            state['current_file_read_bytes'] += n
                with lock:
                    if state['current_file_read_bytes'] != sizes[str(path)]:
                        raise RuntimeError(f'File size changed: {path}')
                    state['completed_files'].append(str(path))
            with lock:
                state['status'] = 'complete'
        except Exception as exc:
            with lock:
                state.update(status='failed', error=repr(exc))

    worker = threading.Thread(target=read)
    worker.start()
    while True:
        with lock:
            snapshot = dict(state)
            snapshot['completed_files'] = list(state['completed_files'])
        snapshot['time'] = time.time()
        elapsed = snapshot['time'] - snapshot['started']
        snapshot['average_mib_s'] = snapshot['read_bytes'] / max(elapsed, .001) / 2**20
        temp = args.output / 'status.tmp'
        temp.write_text(json.dumps(snapshot, indent=2) + '\n')
        temp.replace(args.output / 'status.json')
        print(json.dumps(snapshot), flush=True)
        if snapshot['status'] != 'reading':
            break
        time.sleep(5)
    worker.join()
    if state['status'] == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
