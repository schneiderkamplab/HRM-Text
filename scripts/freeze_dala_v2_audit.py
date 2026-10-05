"""Read-only DaLA export inventory; writes a fresh HRM manifest, not audit results."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

LANGUAGES = 'en de fr es it pt-PT cs sk pl uk be bg ro el ca fi et lv lt sv nb nn is fo hr sl'.split()


def pin(path):
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise RuntimeError(f'Source changed during hashing: {path}')
    return dict(path=str(path.resolve()), sha256=h.hexdigest(), bytes=after.st_size,
                mtime_ns=after.st_mtime_ns)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('/work/mimir/DaLA'))
    parser.add_argument('--output', type=Path, default=Path('data/dfm13/dala-v2-audit'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    readiness_path = args.source/'wiki/artifacts/v2-audit-readiness-20261003.json'
    readiness_pin = pin(readiness_path)
    readiness = json.loads(readiness_path.read_text())
    entries = []
    for lang in LANGUAGES:
        info = readiness['ready'][lang]
        root = Path(info['output'])
        breadth_path = root/'exported-breadth.json'
        breadth_pin = pin(breadth_path)
        breadth = json.loads(breadth_path.read_text())
        assert breadth['language'] == lang
        assert breadth['counts']['pairs'] == info['candidate_pairs']
        assert breadth['counts']['controls'] == info['clean_controls']
        assert breadth['pending_checker_rows'] == 0
        files, examples = {}, {}
        for kind in ('pairs', 'controls'):
            path = root/f'{kind}.for-audit.jsonl.gz'
            files[kind] = pin(path)
            with gzip.open(path, 'rt') as f:
                examples[kind] = json.loads(next(f))
            assert examples[kind]['language'] == lang
        entry = dict(language=lang, requested_language='pt_pt' if lang == 'pt-PT' else lang,
                     source_root=str(root), counts=breadth['counts'], files=files,
                     breadth=breadth_pin, identity=pin(root/'identity.json'),
                     count_basis='producer full-stream census, pinned exported-breadth; not recounted here',
                     samples=examples, accepted=False, training_admitted=False)
        entries.append(entry)
        print(lang, info['candidate_pairs'], info['clean_controls'], flush=True)
    if pin(readiness_path) != readiness_pin:
        raise RuntimeError('Readiness changed')
    result = dict(schema='dala-v2-audit-frozen-inventory-v1',
                  created_at=datetime.now(timezone.utc).isoformat(), readiness=readiness_pin,
                  languages=entries, excluded_live_languages=['nl', 'fa'],
                  language_aliases={'pt_pt': 'pt-PT'},
                  candidate_pairs=sum(e['counts']['pairs'] for e in entries),
                  clean_controls=sum(e['counts']['controls'] for e in entries),
                  snapshot_type='content-pinned external files; runner must verify before consumption',
                  accepted=False, training_admitted=False,
                  split_policy='Preserve train/validation/test and representative/challenge; never train on validation/test',
                  review_contract_pins=[pin(args.source/p) for p in (
                      'dala/audit_v2.py', 'dala/clean_audit_v2.py',
                      'dala/composition_v2.py', 'dala/additional_release_v2.py')],
                  inventory_script=pin(Path(__file__)))
    with (args.output/'manifest.json').open('x') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    with (args.output/'seal.json').open('x') as f:
        json.dump(pin(args.output/'manifest.json'), f, indent=2)
    print(json.dumps({k: result[k] for k in ('candidate_pairs', 'clean_controls')}))


if __name__ == '__main__':
    main()
