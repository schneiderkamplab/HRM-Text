"""Launch the isolated rebuild and stop it on sustained filesystem latency."""
import argparse
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import time


def probe(path):
    start = time.monotonic()
    with path.open("wb") as f:
        f.write(b"x" * 4096)
        f.flush()
        os.fsync(f.fileno())
    assert path.read_bytes() == b"x" * 4096
    path.unlink()
    print(time.monotonic() - start, flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--probe", type=Path)
    p.add_argument("--queue", type=Path)
    p.add_argument("--log-dir", type=Path)
    args = p.parse_args()
    if args.probe:
        probe(args.probe)
        return
    if not args.queue or not args.log_dir:
        p.error("--queue and --log-dir required")
    args.log_dir.mkdir(parents=True, exist_ok=True)
    path = args.log_dir / f".latency-{os.getpid()}"

    def measure():
        try:
            result = subprocess.run([sys.executable, __file__, "--probe", str(path)],
                                    timeout=5, check=True, capture_output=True, text=True)
            return float(result.stdout)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
            return 5.0

    baseline = statistics.median(measure() for _ in range(5))
    if baseline >= .5:
        raise RuntimeError(f"Filesystem already slow ({baseline:.3f}s); not launching")
    threshold = max(.5, 10 * baseline)
    with (args.log_dir / "runner.log").open("a") as output:
        child = subprocess.Popen(
            [sys.executable, "-m", "scripts.queue_dfm_hf_rebuild", "run",
             "--queue", str(args.queue)],
            stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        print(json.dumps(dict(pid=child.pid, baseline=baseline, threshold=threshold)), flush=True)
        consecutive = 0
        while child.poll() is None:
            time.sleep(30)
            latency = measure()
            consecutive = consecutive + 1 if latency > threshold else 0
            print(json.dumps(dict(time=time.time(), latency=latency,
                                  slow_checks=consecutive, pid=child.pid)), flush=True)
            if consecutive >= 3 and child.poll() is None:
                print("Stopping rebuild process group: sustained slow filesystem", flush=True)
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                break
        print(f"Rebuild exited: {child.wait()}", flush=True)


if __name__ == "__main__":
    main()
