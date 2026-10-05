"""Strict borrowed31B endpoint gate; never starts or stops servers."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import urllib.request

from .io import load, file_hash, write_json

MODEL = 'google/gemma-4-31B-it'


def validate(document, snapshot, context=32768):
    models = document.get('data') if isinstance(document, dict) else None
    if not isinstance(models, list) or len(models) != 1 or not isinstance(models[0], dict):
        raise ValueError('Require exactly one advertised31B model')
    model = models[0]
    root = model.get('root')
    if (model.get('id') != MODEL or not isinstance(root, str) or not root
            or not Path(root).is_absolute() or Path(root).resolve() != Path(snapshot).resolve()
            or type(model.get('max_model_len')) is not int or model['max_model_len'] < context):
        raise ValueError('31B endpoint model/context/snapshot mismatch')
    return document


def check(endpoint, snapshot, context=32768):
    with urllib.request.urlopen(endpoint.rstrip('/') + '/models', timeout=10) as response:
        document = json.load(response)
    return validate(document, snapshot, context)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', action='append', required=True)
    parser.add_argument('--ready', type=Path, default=Path('data/dfm13/wave4/gemma31-download/ready.json'))
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER,
                        help='Optional exact consumer command after --; executed only after all gates pass')
    args = parser.parse_args()
    ready = load(args.ready)
    if ready.get('model') != MODEL or ready.get('all_files_verified') is not True:
        raise ValueError('Verified31B download receipt required')
    documents = {e: check(e, ready['snapshot']) for e in args.endpoint}
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    write_json(args.receipt, dict(time=time.time(), model=MODEL, snapshot=ready['snapshot'],
        ready_sha256=file_hash(args.ready), endpoints=documents, command=command,
        server_actions=False, admission_authorized=False))
    if command:
        subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
