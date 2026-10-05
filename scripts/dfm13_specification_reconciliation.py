"""Stage evidence-backed scope reconciliation; never update assembly pointers."""
import argparse
from collections import Counter
from pathlib import Path
import time

import numpy as np

from dfm12.io import file_hash, load, write_json, lock
from scripts.dfm13_finalization_inventory import build
from scripts.queue_dfm13_fo_instruct_successor import ROOT as FINAL_ASSEMBLY, require_included


def pin(path):
    return {'path': str(Path(path).resolve()), 'sha256': file_hash(path)}


def valid_pin(value):
    return bool(value and Path(value['path']).is_file()
                and file_hash(value['path']) == value['sha256'])


def disposition(names, components):
    if not names:
        return 'unresolved'
    states = [components[n]['stage'] for n in names]
    if all(s == 'held' for s in states):
        return 'held'
    if all(s in ('held', 'verified_integrated') for s in states):
        return 'integrated_with_holds' if 'held' in states else 'integrated'
    return 'pending_integration'


def scope_rows(inventory):
    components = {r['name']: r for r in inventory['components']}
    result = []
    for name, row in sorted(components.items()):
        result.append(dict(id='component:'+name, components=[name],
                           disposition=disposition([name], components),
                           evidence=row['registry_evidence'], hold=row.get('hold_evidence')))
    aliases = {
        'baltic_lt_qa': 'dfm13_wave3_baltic_lt_qa',
        'baltic_lv_qa': 'dfm13_wave3_baltic_lv_qa',
        'baltic_lt_aya': 'dfm13_wave3_baltic_lt_aya',
        'baltic_lt_summary': 'dfm13_wave3_baltic_lt_summary_',
        'baltic_lt_finepdfs': 'dfm13_wave3_finepdfs_lt_',
        'baltic_lv_finepdfs': 'dfm13_wave3_finepdfs_lv_',
        'baltic_lt_blkt': 'dfm13_wave3_transform_baltic_lt_blkt_',
        'latvian_p3': 'dfm13_wave3_latvian_p3_',
        'parlamint_lt': 'dfm13_wave3_transform_parlamint_lt_',
        'parlamint_lv': 'dfm13_wave3_transform_parlamint_lv_',
    }
    for path, spec in inventory['specifications'].items():
        if not path.startswith('config/'):
            continue
        for entry in spec.get('sources', []):
            name = entry['name']
            prefix = aliases.get(name)
            matches = sorted(n for n in components if n == name or (prefix and n.startswith(prefix)))
            result.append(dict(id=path+':'+name, components=matches,
                               disposition=disposition(matches, components), evidence=entry))
        for name, reason in spec.get('deferred', {}).items():
            result.append(dict(id=path+':deferred:'+name, disposition='deferred',
                               components=[], evidence=reason))
        for name, entry in spec.get('supplemental_cpu', {}).items():
            if name == 'opus':
                # OPUS is enumerated by exact component names in the live registry.
                matches = sorted(n for n, r in components.items()
                                 if any(e['entry'].get('publication_contract') ==
                                        'accepted-local-wave-translation-v1'
                                        for e in r['registry_evidence']))
            else:
                prefix = aliases.get(name)
                matches = sorted(n for n in components if prefix and n.startswith(prefix))
            result.append(dict(id=path+':supplemental:'+name, components=matches,
                               disposition=disposition(matches, components), evidence=entry))
    for language, task in inventory['completion_checks']['dala_missing']:
        result.append(dict(id=f'dala-required:{language}:{task}', disposition='pending_integration',
                           components=[], evidence='Explicit all-language DaLA manifest'))
    for family, count in [('baltic', 12), ('wave4', 66), ('tlpc', 2)]:
        actual = inventory['completion_checks'][family+'_integrated']
        result.append(dict(id='required-family:'+family,
                           disposition='integrated' if actual == count else 'pending_integration',
                           components=[], evidence=dict(required=count, integrated=actual)))
    for name in inventory['policy_exclusions']:
        result.append(dict(id='policy:'+name, disposition='excluded', components=[],
                           evidence='Explicit user exclusion, preserved in finalization inventory'))
    return result


def dala_publications(inventory):
    """Bind grouped language publications to exact local integration receipts."""
    path = Path('exports_dfm13_dala_languages/inventory.json')
    if not path.exists():
        return {}
    destinations = {r['repo']: r for r in inventory['publication_destinations']}
    result = {}
    for package in load(path)['packages']:
        target = destinations.get(package['hf_repo_id'], {})
        receipt_path = target.get('publication_receipt')
        if not receipt_path or not Path(receipt_path).exists():
            continue
        receipt = load(receipt_path).get(package['hf_repo_id'], {})
        expected = package['files']
        if not (receipt.get('status') == 'verified' and receipt.get('revision')
                and receipt.get('remote_payloads_sha256_verified')
                and all(receipt.get('files', {}).get(k) == v for k, v in expected.items())):
            continue
        for pool, integration in package['integration_pins'].items():
            if not valid_pin(integration):
                continue
            for task in ('acceptability', 'correction'):
                language = package['language'].replace('-', '_')
                name = f"dfm13_dala_v2_compact_{language}_{pool}_{task}"
                result[name] = dict(ready=True, repo=package['hf_repo_id'],
                                    revision=receipt['revision'], integration=integration,
                                    receipt=pin(receipt_path), package_inventory=pin(path),
                                    basis='grouped_language_publication_bound_to_integration')
    return result


def gates(specifications, publication):
    return dict(
        all_specifications_disposed=bool(specifications) and all(
            r['disposition'] in ('integrated', 'integrated_with_holds', 'held', 'excluded', 'deferred')
            for r in specifications),
        all_integrated_packages_locally_upload_ready=bool(publication) and all(
            r.get('ready') is True for r in publication))


def setur_readiness(entry):
    if entry.get('publication_contract')!='setur-fo-instruct-native-v1':return None
    if entry.get('repo_id')!='Setur/fo-instruct' or entry.get('repeat')!=10:
        raise ValueError('Invalid Setur source identity/repeat')
    receipt=Path(entry['output']).parent.parent/'completion.json'
    proof=load(receipt)
    if proof['entry']!=entry or proof['verification']['revision']!=entry['revision']:
        raise ValueError('Setur completion binding mismatch')
    pins=[pin(receipt)]
    for path,sha in [(entry[k],entry[k+'_sha256']) for k in ('output','raw_source','source_card')]+list(entry['token_files'].items()):
        value=dict(path=path,sha256=sha)
        if not valid_pin(value):raise ValueError('Setur local conversion evidence drift')
        pins.append(value)
    return dict(ready=True,basis='pinned_upstream_source_with_verified_local_conversion',
                repo=entry['repo_id'],revision=entry['revision'],pins=pins,new_upload_required=False)


def reconcile(inventory):
    reference = inventory['authoritative']
    assembly_path = Path(reference['root'])/'assembly.json'
    if file_hash(assembly_path) != reference['assembly_sha256']:
        raise ValueError('Assembly pointer hash mismatch')
    specs = scope_rows(inventory)
    grouped = dala_publications(inventory)
    readiness = {r['name']: r for r in inventory['publication_readiness']}
    publication = []
    for row in inventory['components']:
        if row['stage'] != 'verified_integrated':
            continue
        item = dict(readiness[row['name']])
        if row['name'] in grouped:
            item.update(grouped[row['name']])
        source_ready=setur_readiness(row['registry_evidence'][-1]['entry'])
        if source_ready:item.update(source_ready)
        publication.append(item)
    inherited_path = Path('data/dfm13/dfm12-full-inheritance-20261004-v2/inheritance.json')
    inherited = load(inherited_path)
    reuse_path = Path('docs/reports/dfm13_inherited_dala_reuse_handoff_20261004.json')
    # Existing producer publication equivalence is separately checked by inventory.build.
    targets = {r['repo']: r for r in inventory['publication_destinations']}
    for source in inherited['sources']:
        target = targets.get(source.get('hf_repo_id'), {})
        original = source['publication']['status'] == 'verified_published'
        reused = (target.get('publication_basis') == 'existing_producer_exact_manifest_and_audited_pairs'
                  and target.get('published') is True and bool(target.get('remote_revision')))
        publication.append(dict(name=source['name'], inherited=True, ready=original or reused,
                                recorded_publication=source['publication'],
                                reuse=target if reused else None))
    base_path = Path('data/provenance/dfm11_remote_20261002/source-map.json')
    base_dala = [r for r in load(base_path)['tasks'] if 'dala' in r['task'].lower()]
    prior_coverage = []
    for row in inventory['components']:
        entry = row['registry_evidence'][-1]['entry']
        export_pin = entry.get('export_receipt')
        if not export_pin or not row['name'].startswith('dfm13_dala_v2_compact_'):
            continue
        if not valid_pin(export_pin):
            raise ValueError('DaLA export receipt drift: '+row['name'])
        export = load(export_pin['path'])
        prior = export.get('prior_index', {})
        prior_coverage.append(dict(name=row['name'], export=export_pin,
            prior_index={k: prior.get(k) for k in ('path', 'sha256', 'counts', 'normalization')},
            prior_repos=sorted({v['repo_id'] for v in prior.get('files', {}).values() if v.get('repo_id')}),
            prior_revisions=sorted({v['revision'] for v in prior.get('files', {}).values() if v.get('revision')}),
            historical_files=prior.get('files', {}),
            duplicate_exclusions={k: v for k, v in export.get('counts', {}).items()
                                  if 'duplicate' in k or 'conflict' in k},
            disposition='incremental_exact_pair_and_clean_control_exclusion_not_blanket_replacement'))
    checks = gates(specs, publication)
    result = dict(schema='dfm13-specification-reconciliation-v1', staged_only=True,
                  **checks, inherited_dfm12_coverage_verified=inventory['completion_checks'].get(
                      'inherited_dfm12_coverage_verified') is True,
                  assembly=pin(assembly_path), authoritative=reference,
                  input_pins=[pin(p) for p in inventory['specifications']]+
                             [pin(inherited_path), pin(base_path), pin(reuse_path)],
                  registry_inputs=inventory['registry_inputs'], specifications=specs,
                  disposition_counts=dict(Counter(r['disposition'] for r in specs)),
                  publication=publication, publication_unready=[r['name'] for r in publication if not r['ready']],
                  dala_prior_coverage=prior_coverage, historical_dala_tasks=base_dala,
                  replacement_policy=dict(base='DFM11 plus latest381 once; never sampled_DFM12 plus381',
                      xl_identity='nine obsolete packages replaced; latest21 repeat10',
                      xxl_identity='21 distinct persona packages remain excluded repeat0',
                      dala='v2 incremental; prior clean controls and exact noisy pairs excluded'),
                  sampling=dict(epochs=1, seed=0, no_sampling_performed=True,
                                repeat_policy='preserve sealed mapping: XL identity10, Setur FO10, MATH5, other1'),
                  unresolved_risks=['Prior pair exclusion is not semantic deduplication; inherited historical all-split TV2R remains train-contaminated for evaluation'],
                  sampling_authorized_by_this_report=False)
    if load('data/dfm13/authoritative-additions.json') != reference:
        raise ValueError('Authority changed during reconciliation; rerun on stable snapshot')
    for value in result['input_pins']:
        if not valid_pin(value):
            raise ValueError('Input drift during reconciliation')
    return result


def scan_inherited_lengths(output):
    """Full length/bounds scan of small indices, not the massive token backing."""
    path = Path('data/dfm13/dfm12-full-inheritance-20261004-v2/inheritance.json')
    inherited = load(path)
    rows = []
    for source in inherited['sources']:
        for part in source['parts']:
            arrays = {}
            for field in ('inst_len', 'resp_len', 'inst_start', 'resp_start'):
                evidence = part['arrays'][field]
                p = Path(evidence['path']); st = p.stat()
                if st.st_size != evidence['bytes'] or st.st_mtime_ns != evidence['mtime_ns']:
                    raise ValueError('Inherited index drift: '+str(p))
                arrays[field] = np.load(p, mmap_mode='r', allow_pickle=False)
            counts = Counter(); max_length = 0
            for start in range(0, part['rows'], 1_000_000):
                a = {k: np.asarray(v[start:start+1_000_000], dtype=np.int64) for k, v in arrays.items()}
                lengths = a['inst_len']+a['resp_len']
                if len(lengths):
                    max_length = max(max_length, int(lengths.max()))
                counts['over_context'] += int(np.count_nonzero(lengths > 4097))
                counts['short_response'] += int(np.count_nonzero(a['resp_len'] < 2))
                for prefix in ('inst', 'resp'):
                    position = a[prefix+'_start']; length = a[prefix+'_len']
                    counts['bad_bounds'] += int(np.count_nonzero(
                        (position < 0) | (length < 0) | (position > part['tokens']) |
                        (length > part['tokens']-position)))
            rows.append(dict(source=source['name'], task=part['task'], rows=part['rows'],
                             max_length=max_length, violations=dict(counts)))
    result = dict(inheritance=pin(path), sources=len(inherited['sources']), parts=len(rows),
                  rows=sum(r['rows'] for r in rows), full_length_index_scan=True,
                  token_payload_not_scanned=True, context_size=4097, min_resp_length=2,
                  valid=all(not any(r['violations'].values()) for r in rows), checks=rows)
    write_json(output, result)
    return result


def watch(output):
    """Release Tesla's existing sampler once final scope and receipts agree."""
    expected = FINAL_ASSEMBLY.resolve()
    canonical = Path('data/dfm13/all-source-finalization-20261004-v1')
    with lock(output.parent/'watcher.lock'):
        lengths = scan_inherited_lengths(output.parent/'inherited-length-validation.json')
        if not lengths['valid']:
            raise ValueError('Inherited indices would drop rows; sampling remains blocked')
        while True:
            ref = load('data/dfm13/authoritative-additions.json')
            comp = load('data/dfm13/authoritative-composition.json')
            if (Path(ref['root']).resolve() == expected and
                    comp.get('additions_sha256') == ref['assembly_sha256']):
                require_included(expected)
                result = reconcile(build())
                result['inherited_length_validation'] = pin(output.parent/'inherited-length-validation.json')
                write_json(output, result)
                ready = (result['all_specifications_disposed'] and
                         result['all_integrated_packages_locally_upload_ready'] and
                         result['inherited_dfm12_coverage_verified'])
                write_json(output.parent/'progress.json', dict(phase='checked_final', ready=ready,
                    counts=result['disposition_counts'], unready=result['publication_unready'], time=time.time()))
                if ready:
                    with lock(Path('data/dfm13/authoritative-additions.lock')):
                        if load('data/dfm13/authoritative-additions.json') != ref:
                            continue
                        result.update(assembly_sha256=ref['assembly_sha256'], sampling_authorized=True,
                            authorization='User explicitly authorized final integrate/verify/sample one epoch; Tesla owns execution',
                            staged_only=False)
                        write_json(canonical/'reconciliation.json', result)
                        write_json(canonical/'sampling-reconciliation.json', result)
                        write_json(output.parent/'completion.json', dict(complete=True,
                            reconciliation=pin(canonical/'reconciliation.json'),
                            sampling_reconciliation=pin(canonical/'sampling-reconciliation.json'),
                            time=time.time()))
                    return
            else:
                write_json(output.parent/'progress.json', dict(phase='waiting_final_assembly_and_composition',
                    expected_root=str(expected), current_root=ref['root'], time=time.time()))
            time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    if args.watch:
        return watch(args.output)
    result = reconcile(build())
    write_json(args.output, result)
    print({k: result[k] for k in ('all_specifications_disposed',
          'all_integrated_packages_locally_upload_ready', 'disposition_counts', 'publication_unready')})


if __name__ == '__main__':
    main()
