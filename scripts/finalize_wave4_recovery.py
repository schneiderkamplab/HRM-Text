"""Wait for CPU preparation and terminal owners, then export isolated recovery."""
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dfm12 import wave4_recovery_supplement as recovery
from dfm12.io import file_hash,load,write_json,lock


def run(bundle,output,release,expected_hash):
    with lock(output.parent/(output.name+'.finalizer.lock')):
        while True:
            if file_hash(recovery.__file__)!=expected_hash:
                raise ValueError('Prepared recovery code changed')
            ready=(output/'prepared.json').exists() and (bundle/'terminal.json').exists()
            write_json(output.with_suffix('.finalizer-progress.json'),dict(
                time=time.time(),prepared=(output/'prepared.json').exists(),
                campaign_terminal=(bundle/'terminal.json').exists(),release=str(release),
                source_ledgers_unchanged=True))
            if ready:
                try:
                    recovery.finalize(bundle,output,release)
                except BlockingIOError:
                    time.sleep(15)
                    continue
                write_json(output.with_suffix('.finalizer-complete.json'),dict(
                    release=str(release),manifest_sha256=file_hash(release/'manifest.json'),time=time.time()))
                return
            time.sleep(30)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--release',type=Path,required=True)
    parser.add_argument('--runtime-sha256',required=True)
    args=parser.parse_args()
    run(args.bundle.resolve(),args.output.resolve(),args.release.resolve(),args.runtime_sha256)
