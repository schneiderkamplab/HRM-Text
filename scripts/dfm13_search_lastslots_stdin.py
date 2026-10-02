"""Read one credential from stdin and hand it to a detached client via a pipe."""
import argparse
import asyncio
import os
from pathlib import Path
import subprocess
import sys


def read_credential(stream):
    value = stream.readline(4097).strip()
    if not value or len(value) > 4096 or any(c.isspace() for c in value):
        raise ValueError('expected one nonempty credential line on stdin')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    credential = read_credential(sys.stdin)
    if args.child:
        import fcntl
        from scripts import dfm13_search_lastslots2 as client
        # The secret enters the child only through stdin, never argv or its
        # initial environment, and is cleared after the scoped retrieval run.
        os.environ['JINA_API_KEY'] = credential
        del credential
        try:
            with (client.ROOT / 'run.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                asyncio.run(client.run(argparse.Namespace(credential_file=Path('/nonexistent/unused'))))
        finally:
            os.environ.pop('JINA_API_KEY', None)
        return
    log = Path('logs/arena_review/20261001/search-lastslots2-stdin.log')
    with log.open('ab') as output:
        env = dict(os.environ)
        env.pop('JINA_API_KEY', None)
        child = subprocess.Popen([sys.executable, '-u', '-m', __spec__.name, '--child'],
            stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True, env=env)
        try:
            child.stdin.write((credential + '\n').encode())
            child.stdin.close()
        except BrokenPipeError:
            raise RuntimeError('credential handoff child exited') from None
    del credential
    print(f'PID {child.pid}; log {log}')


if __name__ == '__main__':
    main()
