"""Append completed NL/FA recovery inputs without rewriting baseline manifests."""
import json
from pathlib import Path
from freeze_dala_v2_audit import pin


def source(entry, kind, recovery=False):
    spec = entry['files'][kind]
    return dict(component=entry['language']+(':recovery-v3:' if recovery else ':')+kind,
        language=entry['language'], kind='pair' if kind == 'pairs' else 'clean_control',
        path=spec['path'], sha256=spec['sha256'], rows=entry['counts'][kind],
        split='from_record', receipt=entry['breadth']['path'],
        receipt_sha256=entry['breadth']['sha256'])


def main():
    old = Path('data/dfm13/dala-v2-audit34/manifest.json')
    predecessor = pin(old)
    assert predecessor['sha256'] == json.loads(old.with_name('seal.json').read_text())['sha256']
    baseline = json.loads(old.read_text())
    recovery = []
    for lang, expected in [('nl', (137888, 114360)), ('fa', (58971, 48258))]:
        root = Path('/work/mimir/DaLA/la_output/v2/grammar-recovery-production-v3')/lang/'output'
        status_pin, breadth_pin = pin(root/'status.json'), pin(root/'exported-breadth.json')
        status = json.loads((root/'status.json').read_text())
        breadth = json.loads((root/'exported-breadth.json').read_text())
        assert status['complete'] is True and status['stage'] == 'ready_for_gpu_audit'
        assert breadth['pending_checker_rows'] == 0
        assert (breadth['counts']['pairs'], breadth['counts']['controls']) == expected
        entry = dict(language=lang, source_root=str(root), counts=breadth['counts'],
            status=status_pin, breadth=breadth_pin, identity=pin(root/'identity.json'),
            files={k: pin(root/f'{k}.for-audit.jsonl.gz') for k in ('pairs', 'controls')},
            complete=True, stage=status['stage'], pending_checker_rows=0,
            coverage_requirements_met=status['coverage_requirements_met'],
            observed_family_floors_met=status['observed_family_floors_met'],
            accepted=False, training_admitted=False)
        assert status_pin == pin(root/'status.json') and breadth_pin == pin(root/'exported-breadth.json')
        recovery.append(entry)
    sources = [source(e,k) for e in baseline['languages'] for k in ('controls','pairs')]
    sources += [source(e,k,True) for e in recovery for k in ('controls','pairs')]
    assert len(sources) == len({s['component'] for s in sources}) == 72
    result = dict(schema='dala-v2-audit-baseline-plus-recovery-v3', previous_manifest=predecessor,
        languages=baseline['languages'], recovery=recovery, sources=sources,
        candidate_pairs=baseline['candidate_pairs']+sum(e['counts']['pairs'] for e in recovery),
        clean_controls=baseline['clean_controls']+sum(e['counts']['controls'] for e in recovery),
        count_basis='Producer export census; sum of input rows, not cross-pool unique count',
        preparation_complete=True, audit_complete=False, admission_authorized=False,
        split_policy=baseline['split_policy'], inventory_script=pin(Path(__file__)))
    root = Path('data/dfm13/dala-v2-audit34-with-recovery-v1')
    root.mkdir(exist_ok=False)
    (root/'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    (root/'seal.json').write_text(json.dumps(pin(root/'manifest.json'), indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('candidate_pairs','clean_controls','preparation_complete','audit_complete')}))


if __name__ == '__main__':
    main()
