"""Read-only inventory of explicitly enabled, prepared native-thinking targets."""
import json
from collections import defaultdict
from pathlib import Path
import numpy as np


def main():
    root = Path('data/dfm15/native-reasoning-v2')
    groups = defaultdict(lambda: dict(rows=0, tokens=0))
    for part in json.loads((root/'repairs.json').read_text())['parts']:
        path = root/'tokenized'/part['name']
        thinking = np.load(path/'valid.npy', mmap_mode='r') == 2
        lengths = np.load(path/'inst_len.npy', mmap_mode='r') + np.load(path/'resp_len.npy', mmap_mode='r')
        count = int(thinking.sum())
        assert count == part['counts'].get('thinking', 0)
        group = groups[part['name'].split('__')[0]]
        group['rows'] += count
        group['tokens'] += int(lengths[thinking].sum())
    groups['danish-foundation-models/multilingual-gsm-symbolic (EN synthetic train)'] = dict(rows=3799, tokens=682844)
    summary = json.loads(Path('data/dfm16/decisions-v1/preparation_summary.json').read_text())
    for source in summary['sources']:
        receipt = json.loads(Path(source['conversion_receipt']).read_text())
        if not receipt.get('counts', {}).get('thinking'):
            continue
        group = dict(rows=0, tokens=0, rows_le4096=0, tokens_le4096=0)
        for path in Path(source['tokenized_path']).glob('thinking/**/inst_len.npy'):
            lengths = np.load(path, mmap_mode='r') + np.load(path.with_name('resp_len.npy'), mmap_mode='r')
            group['rows'] += len(lengths)
            group['tokens'] += int(lengths.sum())
            fit = lengths <= 4096
            group['rows_le4096'] += int(fit.sum())
            group['tokens_le4096'] += int(lengths[fit].sum())
        assert group['rows'] == receipt['counts']['thinking'], source['name']
        groups[source['repo_id']] = group
    print(json.dumps(dict(groups), indent=2))


if __name__ == '__main__':
    main()
