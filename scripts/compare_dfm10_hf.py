"""Verify every sampled DFM10 value; write a separate HF-only completion receipt."""
import json
from pathlib import Path
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.acquire_dfm10_hf import save, sha
from scripts.replay_dfm_serial import equal_arrays, FIELDS


def compare():
    work=ROOT/'data/rebuild_hf_dfm/serial-queue/dfm10-hf-v2'
    cfg=json.loads((work/'hf_recipe.json').read_text())
    if cfg['recipe'] != 'dfm10-hf-v2' or json.loads((work/'all-token-comparison.json').read_text())['status'] != 'matched':
        raise ValueError('HF source/token verification missing')
    actual=work/'sampled'; expected=ROOT/'data/sampled_dfm10'
    epochs=[f'epoch_{i}' for i in range(10)]
    for root in (actual,expected):
        if sorted(p.name for p in root.glob('epoch_*') if p.is_dir()) != epochs:
            raise ValueError('Epoch inventory differs')
    files=[Path('tokens.npy')]+[Path(e)/(f+'.npy') for e in epochs for f in FIELDS]
    for rel in files:
        print('Comparing',rel,flush=True)
        equal_arrays(np.load(actual/rel,mmap_mode='r'),np.load(expected/rel,mmap_mode='r'),str(rel))
    if json.loads((actual/'metadata.json').read_text()) != json.loads((expected/'metadata.json').read_text()):
        raise ValueError('Sample metadata differs')
    save(work/'verified.json',{'version':10,'status':'matched','input_policy':'HF-only plus lexdk/DBC','config_sha256':sha(work/'hf_recipe.json'),'verified_files':len(files),'scope':'all token and epoch-index values; metadata'})


if __name__ == '__main__':
    compare()
