"""Resume a staged DFM11 transfer and publish it only after structural checks."""
import json
import os
from pathlib import Path
import subprocess

import numpy as np


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / 'data/sampled_dfm11'
    staging = root / 'data/sampled_dfm11.incoming'
    assets = root / 'data/dfm11_tokenizer'
    receipt_dir = root / 'logs/dfm11_transfer'
    if target.exists():
        raise RuntimeError(f'Refusing to overwrite {target}')
    for path in (staging, assets, receipt_dir):
        path.mkdir(parents=True, exist_ok=True)
    source = 'ucloud@ssh.cloud.sdu.dk:'
    common = ['rsync', '-a', '--partial', '--info=progress2', '--bwlimit=204800',
              '-e', 'ssh -p 6977 -o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=6']

    def transfer(remote, local):
        print(f'Transferring {remote} to {local}', flush=True)
        subprocess.run(common + [source + remote, str(local)], check=True)

    transfer('/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json', assets / 'tokenizer.json')
    transfer('/work/dfm/HRM-Text/data_io/chat_templates/gemma4_native_chat.jinja', assets / 'chat_template.jinja')
    transfer('/work/dfm/HRM-Text/data/sampled_dfm11/', str(staging) + '/')
    metadata_text = (staging / 'metadata.json').read_text()
    metadata = json.loads(metadata_text)
    assert metadata['total_length'] == 103214604702, metadata
    epochs = sorted(staging.glob('epoch_*'))
    assert {p.name for p in epochs} == {f'epoch_{i}' for i in range(10)}

    def inspect(path):
        array = np.load(path, mmap_mode='r', allow_pickle=False)
        assert array.ndim == 1 and array.dtype.kind in 'iu', path
        assert path.stat().st_size == array.offset + array.nbytes, path
        return len(array)

    token_count = inspect(staging / 'tokens.npy')
    counts = {}
    for epoch in epochs:
        lengths = [inspect(epoch / f'{name}.npy')
                   for name in ('inst_start', 'inst_len', 'resp_start', 'resp_len')]
        assert lengths == [235520711] * 4, (epoch, lengths)
        counts[epoch.name] = lengths[0]
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(assets / 'tokenizer.json'))
    assert tokenizer.get_vocab_size() == metadata['tokenizer_info']['vocab_size']
    (receipt_dir / 'source_metadata.json').write_text(metadata_text)
    metadata['tokenizer_info']['tokenizer_path'] = str(assets / 'tokenizer.json')
    metadata['tokenizer_info']['chat_template_path'] = str(assets / 'chat_template.jinja')
    (staging / 'metadata.json').write_text(json.dumps(metadata) + '\n')
    os.rename(staging, target)
    receipt = dict(target=str(target), total_length=metadata['total_length'],
                   stored_tokens=token_count, epoch_rows=counts,
                   validation='rsync success; NPY headers/shapes/file sizes; tokenizer vocab')
    (receipt_dir / 'complete.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('COMPLETE ' + json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
