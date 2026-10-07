"""Resume the reconciled three-epoch DFM14 transfer; publish only after validation."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = '/work/dfm/HRM-Text/data/dfm14/inheritance-reconciliation/sampled_dfm14/'
EXPECTED = [135548772522, 135547857271, 135548077354]
PINS = {
    'metadata.json': 'e4cf665ccb8a7b2d634b81733d3a10760a9da55522a90b75111f3382e078be93',
    'data_io/chat_templates/gemma4_native_chat.jinja': 'd8ae62ccf8e47299c8e912a86b16e93bf6b195d24e8b06fffb865e061e89f07e',
    '../brainsurgery/models/gemma4_31b/tokenizer.json': '12bac982b793c44b03d52a250a9f0d0b666813da566b910c24a6da0695fd11e6',
}


def main():
    os.chdir(ROOT)
    target = ROOT / 'data/sampled_dfm14'
    stage = ROOT / 'data/sampled_dfm14.transferring'
    with open(ROOT / 'data/.transfer-dfm14.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if target.exists():
            raise RuntimeError('Destination already exists; refusing overwrite')
        for name, digest in PINS.items():
            if name != 'metadata.json':
                assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
        stage.mkdir(exist_ok=True)
        subprocess.run([
            'rsync', '-aL', '--partial', '--info=progress2',
            '-e', 'ssh -p 6768 -o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=6',
            'ucloud@ssh.cloud.sdu.dk:' + SOURCE, str(stage) + '/',
        ], check=True)
        assert hashlib.sha256((stage/'metadata.json').read_bytes()).hexdigest() == PINS['metadata.json']
        tokens = np.load(stage/'tokens.npy', mmap_mode='r')
        totals = []
        for epoch, expected in enumerate(EXPECTED):
            arrays = {k: np.load(stage/f'epoch_{epoch}'/(k+'.npy'), mmap_mode='r')
                      for k in ('inst_start', 'inst_len', 'resp_start', 'resp_len')}
            lengths = {len(a) for a in arrays.values()}
            assert lengths == {406830651}, lengths
            total = 0
            for start in range(0, len(arrays['inst_len']), 1_000_000):
                chunk = {k: a[start:start+1_000_000] for k, a in arrays.items()}
                for prefix in ('inst', 'resp'):
                    offsets, sizes = chunk[prefix+'_start'], chunk[prefix+'_len']
                    assert np.all(offsets <= len(tokens))
                    assert np.all(sizes <= len(tokens)-offsets)
                    total += int(sizes.sum(dtype=np.uint64))
                assert np.all(chunk['resp_len'] > 0)
                assert np.all(chunk['inst_len']+chunk['resp_len'] <= 4097)
            assert total == expected, (epoch, total, expected)
            totals.append(total)
            print('Verified epoch', epoch, total, flush=True)
        (stage/'local-transfer-verified.json').write_text(json.dumps({
            'source': SOURCE, 'host': 'ssh.cloud.sdu.dk', 'port': 6768,
            'epoch_tokens': totals, 'pins': PINS,
            'transport': 'rsync transfer checksum; no independent full token-store hash',
        }, indent=2)+'\n')
        stage.rename(target)
        print('READY', target, flush=True)


if __name__ == '__main__':
    main()
