"""Freeze all34 completed CPU exports, excluding additive NL/FA recovery."""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
from freeze_dala_v2_audit import pin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data/dfm13/dala-v2-audit34'))
    args = parser.parse_args()
    old = Path('data/dfm13/dala-v2-audit/manifest.json')
    previous = json.loads(old.read_text())
    assert pin(old)['sha256'] == json.loads(old.with_name('seal.json').read_text())['sha256']
    authority = Path('/work/mimir/DaLA/wiki/artifacts/v2-cpu-completion-20261003.json')
    evidence = json.loads(authority.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    entries = {e['language']: e for e in previous['languages']}
    for lang in ('da', 'nl', 'fa', 'bs', 'hu', 'lb', 'sq', 'sr'):
        info = evidence['languages'][lang]
        root = Path(info['output'])
        breadth = json.loads((root/'exported-breadth.json').read_text())
        assert breadth['counts']['pairs'] == info['exported_pairs']
        assert breadth['counts']['controls'] == info['exported_controls']
        assert breadth['pending_checker_rows'] == 0
        entries[lang] = dict(language=lang, requested_language=lang, source_root=str(root),
            counts=breadth['counts'], files={k: pin(root/f'{k}.for-audit.jsonl.gz') for k in ('pairs','controls')},
            breadth=pin(root/'exported-breadth.json'), identity=pin(root/'identity.json'),
            count_basis='producer full-stream census; not recounted here',
            completed_baseline_only=lang in ('nl','fa'), accepted=False, training_admitted=False)
        print(lang, breadth['counts']['pairs'], breadth['counts']['controls'], flush=True)
    assert len(entries) == 34
    # Existing26 pins remain byte-for-byte inherited; detect observable file drift.
    for entry in entries.values():
        for spec in entry['files'].values():
            st = Path(spec['path']).stat()
            assert (st.st_size, st.st_mtime_ns) == (spec['bytes'], spec['mtime_ns']), spec['path']
    result = dict(previous, schema='dala-v2-audit-frozen-inventory-v2',
        created_at=datetime.now(timezone.utc).isoformat(), languages=list(entries.values()),
        previous_manifest=pin(old), completion_authority=pin(authority),
        excluded_live_languages=[], excluded_streams=['nl additive recovery', 'fa additive recovery'],
        scope_authority='User requested all34; NL/FA completed baseline does not wait for additive recovery',
        candidate_pairs=sum(e['counts']['pairs'] for e in entries.values()),
        clean_controls=sum(e['counts']['controls'] for e in entries.values()),
        inventory_script=pin(Path(__file__)))
    (args.output/'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    (args.output/'seal.json').write_text(json.dumps(pin(args.output/'manifest.json'), indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('candidate_pairs','clean_controls')}))


if __name__ == '__main__':
    main()
