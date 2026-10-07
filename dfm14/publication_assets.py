"""Carry local upstream attribution attachments into public DFM14 packages."""
import gzip
import json
from pathlib import Path

from dfm12.io import atomic, file_hash, load, rows, write_json


def attribution_paths(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'attribution' and isinstance(item, str) and item.startswith('data/dfm14/'):
                path = Path(item).resolve(strict=True)
                if not path.is_relative_to(Path('data/dfm14').resolve()):
                    raise ValueError('Attribution path escapes DFM14 source directory')
                yield item, path
            else:
                yield from attribution_paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from attribution_paths(item)


def attach(folder, training):
    receipt = folder/'metadata/attribution-receipt.json'
    if receipt.exists():
        return load(receipt)
    paths = {}
    for path in sorted(training.glob('*.jsonl')):
        for row in rows(path):
            for original, source in attribution_paths(row.get('provenance')):
                paths[original] = source
    output = folder/'metadata/upstream-attribution.jsonl.gz'
    temporary = output.with_suffix('.tmp')
    output.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(temporary,'wt',encoding='utf-8') as handle:
        for original,source in sorted(paths.items()):
            handle.write(json.dumps(dict(original_path=original,sha256=file_hash(source),
                document=load(source)),ensure_ascii=False)+'\n')
    temporary.replace(output)
    result=dict(file=str(output.relative_to(folder)),sha256=file_hash(output),documents=len(paths))
    card=folder/'README.md'
    note=('\n## Upstream attribution attachments\n\n'
          '`metadata/upstream-attribution.jsonl.gz` preserves the original local '
          'attribution documents referenced by row provenance, including available '
          'OPUS README and license texts. Entries map the original path to its '
          'content and SHA-256.\n')
    text=card.read_text()
    if '## Upstream attribution attachments' not in text:
        with atomic(card) as handle:
            handle.write(text+note)
    write_json(receipt,result)
    return result
