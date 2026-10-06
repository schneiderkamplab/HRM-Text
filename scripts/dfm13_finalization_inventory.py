"""Read-only union of live registries and verified assembly membership."""
import argparse
from collections import Counter
from pathlib import Path
import time
import os
import sys
from dfm12.io import load, write_json, file_hash
from scripts.assemble_dfm13_additions import signature


REGISTRIES = [
    'config/dfm13_sources.json',
    'data/dfm13/dala-v2-compact-finalized-20261004-v1/registry.json',
    'data/dfm13/dala-remaining21-finalized-20261004-v1/registry.json',
    'data/dfm13/baltic-finished-release-20261004-v1/registry.json',
    'data/dfm13/wave4-finished-release-20261004-v1/registry.json',
    'data/dfm13/dala-baseline-delta-finalized-20261004-v1/registry.json',
]


def resolve_grouped_publications(inventory):
    # Reuse the reconciliation proof, not a repository-name inference. Import
    # here because reconciliation also uses this module's inventory builder.
    from scripts.dfm13_specification_reconciliation import dala_publications
    grouped = dala_publications(inventory)
    readiness = {r['name']: r for r in inventory['publication_readiness']}
    destinations = {r['repo']: r for r in inventory['publication_destinations']}
    for row in inventory['components']:
        proof = grouped.get(row['name'])
        if not proof or not row.get('integrated'):
            continue
        if row.get('hf_repo_id') not in (None, proof['repo']):
            raise ValueError('Grouped publication conflicts with recorded repository')
        if row.get('hf_revision') not in (None, proof['revision']):
            raise ValueError('Grouped publication conflicts with recorded revision')
        overlay = dict(hf_repo_id=proof['repo'], hf_revision=proof['revision'],
                       status='verified_published', basis=proof['basis'],
                       receipt=proof['receipt'], integration=proof['integration'],
                       package_inventory=proof['package_inventory'],
                       local_view_is_derived=True, byte_identity_claimed=False)
        row.update(hf_repo_id=proof['repo'], hf_revision=proof['revision'],
                   publication_overlay=overlay, publication_pending=False)
        readiness[row['name']].update(ready=True, uploaded=True, requires_upload=False,
            reason='verified_grouped_language_publication', publication_overlay=overlay)
        components = destinations[proof['repo']]['components']
        if row['name'] not in components:
            components.append(row['name'])
    return inventory


def build():
    reference = load('data/dfm13/authoritative-additions.json')
    assembly = load(Path(reference['root'])/'assembly.json')
    paths = [assembly['registry_path'], *REGISTRIES]
    rows, inputs = {}, []
    for filename in paths:
        path = Path(filename)
        if not path.exists():
            inputs.append(dict(path=str(path), exists=False))
            continue
        data = load(path)
        inputs.append(dict(path=str(path), exists=True, sha256=file_hash(path)))
        for entry in data.get('additions', []):
            name = entry['name']
            row = rows.setdefault(name, dict(name=name, registry_evidence=[]))
            row['registry_evidence'].append(dict(path=str(path), entry=entry))
            for field in ('language', 'rows', 'tokens', 'repeat', 'status', 'hf_repo_id', 'hf_revision',
                          'tokenized_path', 'uploaded', 'publication_contract', 'audit_contract'):
                if field in entry:
                    row[field] = entry[field]
    ready = {e['name']: e for e in assembly['ready_additions']}
    held = {e['name']: e for e in assembly['unready_additions']}
    for name, row in rows.items():
        row['integrated'] = name in ready
        row['integration_evidence'] = ready.get(name)
        row['hold_evidence'] = held.get(name)
        row['stage'] = 'verified_integrated' if name in ready else 'not_in_current_verified_assembly'
        if name in held:
            row['stage'] = 'held'
        # A revision is recorded evidence, not a fresh remote verification.
        source = ready.get(name, row)
        row['recorded_hf_repo'] = source.get('hf_repo_id', row.get('hf_repo_id'))
        row['recorded_hf_revision'] = source.get('hf_revision', row.get('hf_revision'))
    specs = {}
    for filename in ('config/dfm13_sources.json', 'config/dfm13_baltic_sources.json',
                     'config/dfm13_jjzha_sources.json', 'data/dfm13/dala-v2-audit34-with-recovery-v1/manifest.json'):
        specs[filename] = load(filename)
    language_manifest = specs['data/dfm13/dala-v2-audit34-with-recovery-v1/manifest.json']
    expected_languages = {s['language'] for s in language_manifest['sources']}
    integrated_dala = {(r.get('language'), r.get('task')) for r in
        load(assembly['registry_path'])['additions']
        if r['name'] in ready and r.get('audit_contract') == 'dala-compact-whole-pair-four-labels-v1'}
    expected_dala = {(language, task) for language in expected_languages
                     for task in ('acceptability', 'correction')}
    checks = dict(dala_missing=sorted(expected_dala-integrated_dala),
                  baltic_integrated=sum(n.startswith('dfm13_baltic_synthetic_') for n in ready),
                  wave4_integrated=sum(n.startswith('dfm13_wave4_synthetic_') for n in ready),
                  tlpc_integrated=sum(n.startswith('dfm13_tlpc_grounded_') for n in ready))
    publication = []
    local_readiness = {}
    baltic_readiness = Path('data/dfm13/baltic-finished-release-20261004-v1/upload-readiness.json')
    if baltic_readiness.exists():
        local_readiness = {e['name']: e for e in load(baltic_readiness)['packages']}
    for name, row in rows.items():
        entry = row['registry_evidence'][-1]['entry']
        path = entry.get('export_manifest') or entry.get('manifest')
        folder = Path(path).parent if path else None
        card = folder/'README.md' if folder else None
        local = local_readiness.get(name, {})
        receipt = entry.get('local_upload_readiness_receipt')
        verified_local = False
        if receipt and file_hash(receipt) == entry.get('local_upload_readiness_sha256'):
            proof = load(receipt)
            verified_local = proof.get('valid') is True and proof.get('upload_ready') is True
        if local.get('upload_ready') and card and card.exists():
            verified_local = file_hash(card) == local.get('readme_sha256')
        if (entry.get('publication_contract') == 'accepted-local-wave-translation-v1'
                and row['integrated'] and card and card.exists()):
            import yaml
            text = card.read_text()
            metadata = yaml.safe_load(text.split('---', 2)[1]) if text.startswith('---') else None
            source_pin = assembly['files'].get(str(Path(entry['output']).resolve()))
            verified_local = bool(metadata and metadata.get('configs') and source_pin and
                source_pin['sha256'] == entry['output_sha256'] and
                list(signature(Path(entry['output']))) == source_pin['signature'] and
                file_hash(path) == entry['export_manifest_sha256'])
        publication.append(dict(name=name, local_card=str(card) if card else None,
            card_exists=bool(card and card.exists()),
            recorded_uploaded_revision=row['recorded_hf_revision'],
            ready=bool(row['recorded_hf_revision']) or verified_local,
            reason='recorded_publication' if row['recorded_hf_revision'] else
                   ('verified_local_readiness_receipt' if verified_local else
                    local.get('remaining', 'local_package_rights_and_payload_verification_required'))))
    reconciliation_path = Path('data/dfm13/all-source-finalization-20261004-v1/reconciliation.json')
    reconciliation = load(reconciliation_path) if reconciliation_path.exists() else {}
    checks['all_registered_finished_integrated'] = all(r['stage'] in ('verified_integrated', 'held') for r in rows.values())
    checks['specification_reconciled'] = reconciliation.get('all_specifications_disposed') is True
    checks['local_publication_ready'] = reconciliation.get('all_integrated_packages_locally_upload_ready') is True
    checks['inherited_dfm12_coverage_verified'] = reconciliation.get('inherited_dfm12_coverage_verified') is True
    composition_ref = Path('data/dfm13/authoritative-composition.json')
    if composition_ref.exists():
        composition = load(composition_ref)
        composition_path = Path(composition['root'])/'composition.json'
        checks['inherited_dfm12_coverage_verified'] = (
            composition.get('inherited_coverage_verified') is True and
            composition.get('additions_sha256') == reference['assembly_sha256'] and
            file_hash(composition_path) == composition['composition_sha256'])
    complete = (not checks['dala_missing'] and checks['baltic_integrated']==12 and
                checks['wave4_integrated']==66 and checks['tlpc_integrated']==2 and
                checks['all_registered_finished_integrated'] and checks['specification_reconciled'] and
                checks['local_publication_ready'] and checks['inherited_dfm12_coverage_verified'])
    destinations = {}
    for row, state in zip(rows.values(), publication):
        entry = row['registry_evidence'][-1]['entry']
        repo = (entry.get('hf_repo_id') or entry.get('intended_hf_repo_id') or
                local_readiness.get(row['name'], {}).get('hf_repo_id'))
        if repo:
            destination = destinations.setdefault(repo, dict(repo=repo, components=[], published=False, local_ready=False))
            destination['components'].append(row['name'])
            destination['published'] |= bool(row['recorded_hf_revision'])
            destination['local_ready'] |= state['ready']
    queue_path = Path('exports_dfm13_dala_languages/queue.json')
    if queue_path.exists():
        for item in load(queue_path)['items']:
            repo = item['hf_repo_id']
            destinations.setdefault(repo, dict(repo=repo, components=[], published=False, local_ready=False,
                                               proposed=True, queue_evidence=str(queue_path)))
    for inventory_path in (Path('exports_dfm13_dala_languages/inventory.json'),
                           Path('exports_dfm13_inherited_dala/inventory.json')):
        if inventory_path.exists():
            for package in load(inventory_path)['packages']:
                repo = package['hf_repo_id']
                record = destinations.setdefault(repo, dict(repo=repo, components=[], published=False))
                record.update(local_ready=package.get('local_package_ready') is True,
                              local_readiness_evidence=str(inventory_path))
    inherited_path = Path('data/dfm13/dfm12-full-inheritance-20261004-v2/inheritance.json')
    if inherited_path.exists():
        for source in load(inherited_path)['sources']:
            if source['publication']['status'] != 'verified_published':
                repo = source['hf_repo_id']
                item = destinations.setdefault(repo, dict(repo=repo, components=[], published=False, local_ready=False))
                if source['name'] not in item['components']:
                    item['components'].append(source['name'])
                item['inherited'] = True
    collision_path = Path('docs/reports/dfm13_inherited_dala_collision_20261004.json')
    if collision_path.exists():
        collision = load(collision_path)
        comparisons = collision.get('comparisons', [])
        if collision.get('complete') and collision.get('no_upload_or_overwrite'):
            if len(comparisons) != 12 or len({c['repo_id'] for c in comparisons}) != 12:
                raise ValueError('Inherited publication comparison scope')
            for c in comparisons:
                if not (c['exact_producer_manifest_equal'] and c['exact_audited_train_pairs_equal']
                        and c['local_source_manifest_sha256'] == c['remote_manifest_sha256']
                        and c['local_train_pairs_sha256'] == c['remote_train_pairs_sha256']
                        and c['local_train_rows_per_task'] == c['remote_train_rows_per_task']
                        == c['local_producer_train_rows_per_task']):
                    raise ValueError('Inherited producer equivalence not established')
                if file_hash(c['remote_manifest_cache']) != c['remote_manifest_sha256']:
                    raise ValueError('Inherited producer evidence drift')
                if c['repo_id'] in destinations:
                    destinations[c['repo_id']].update(
                        published=True,remote_revision=c['revision'],
                        publication_receipt=str(collision_path),
                        publication_receipt_sha256=file_hash(collision_path),
                        publication_basis='existing_producer_exact_manifest_and_audited_pairs',
                        local_projection_byte_identical_to_remote=False,
                        local_projection_evidence='exports_dfm13_inherited_dala/inventory.json',
                        new_upload_required=False)
    upload_roots = [Path('data/dfm13/upload-ready150-20261004-v1'),
                    Path('data/dfm13/upload-ready150-20261004-v2'),
                    Path('data/dfm13/upload-wave4-ready66-20261004-v1'),
                    Path('data/dfm13/upload-baltic-ready2-20261004-v1'),
                    Path('data/dfm13/upload-baltic-ready6-20261005-v1')]
    upload_roots.extend(sorted(Path('data/dfm13/upload-remaining-ready-20261004-v1/batches').glob('batch-*')))
    verified_campaign_repos = set()
    for upload_root in upload_roots:
        if not (upload_root/'publication-receipts.json').exists():continue
        if file_hash(upload_root/'queue.json')!=load(upload_root/'seal.json')['sha256']:
            raise ValueError('Publication queue seal drift')
        authorized={p['repo']:p for p in load(upload_root/'queue.json')['packages']}
        for repo, receipt in load(upload_root/'publication-receipts.json').items():
            if receipt.get('status')!='verified':continue
            if repo not in authorized or receipt['files']!=authorized[repo]['files'] or not receipt.get('remote_payloads_sha256_verified'):
                raise ValueError('Unexpected publication receipt')
            verified_campaign_repos.add(repo)
            if repo in destinations:
                destinations[repo].update(published=True,remote_revision=receipt['revision'],
                    publication_receipt=str(upload_root/'publication-receipts.json'))
    for row, state in zip(rows.values(), publication):
        entry=row['registry_evidence'][-1]['entry']
        repo=(entry.get('hf_repo_id') or entry.get('intended_hf_repo_id') or
              local_readiness.get(row['name'],{}).get('hf_repo_id'))
        destination=destinations.get(repo,{})
        state['requires_upload']=not destination.get('published',False)
        if destination.get('publication_receipt'):
            overlay=dict(hf_repo_id=repo,hf_revision=destination['remote_revision'],
                         status='verified_published',receipt=destination['publication_receipt'])
            row['publication_overlay']=overlay
            row['publication_pending']=False
            state.update(ready=True,reason='remote_verified_external_receipt',uploaded=True,
                         publication_overlay=overlay)
    pending_repos = [d for d in destinations.values() if not d['published']]
    result = dict(version=1, time=time.time(), complete=complete, completion_checks=checks,
                publication_destinations=list(destinations.values()),
                named_pending_repositories=len(pending_repos),
                publication_campaign=dict(expected=258, verified=len(verified_campaign_repos),
                    pending_repositories=len(pending_repos),
                    complete=len(verified_campaign_repos)==258 and not pending_repos,
                    excludes_reused_inherited_producers=12,
                    assembly_integration_complete=complete),
                named_pending_with_explicit_local_readiness=sum(d['local_ready'] for d in pending_repos),
                destination_count_is_final=False,
                expected_unpublished_repositories=0 if not pending_repos else len(pending_repos),
                original_publication_campaign_repositories=258,
                publication_readiness=publication, reconciliation=reconciliation,
                completeness_reason='Finalization and specification-to-component reconciliation still in progress',
                authoritative=reference, registry_inputs=inputs, components=list(rows.values()),
                stage_counts=dict(Counter(r['stage'] for r in rows.values())), specifications=specs,
                policy_exclusions=['RepoChat', 'SearchArena', 'Mimir Search',
                    'dfm13_wave4_ParsiAI_FarsInstruct_fa_pn_sum',
                    'dfm13_wave4_ParsiAI_FarsInstruct_fa_wiki_sum'],
                pending=['remaining21 DaLA finalization', 'Dutch/Persian baseline versus recovery deduplication',
                         'DaLA13 and Baltic/TLPC successor assembly',
                         'Boole uncapped-LB recovered wave4 release export/tokenization/integration',
                         'HF publication receipts and source-specific attribution readiness'],
                no_sampling=True, gpu_actions=False)
    return resolve_grouped_publications(result)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--watch', action='store_true')
    a = p.parse_args()
    while True:
        result = build()
        write_json(a.output, result)
        print(result['stage_counts'], result['completion_checks'], flush=True)
        if not a.watch or result['complete']:
            break
        time.sleep(60)
        os.execv(sys.executable, [sys.executable, '-m', 'scripts.dfm13_finalization_inventory',
                                '--output', str(a.output), '--watch'])
