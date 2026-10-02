"""Detached, fail-closed completion of the explicitly authorized Arena release."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import file_hash, load, lock, write_json
from scripts import export_dfm13_audited_arena as exporter

NAMES = {
    'dfm13-ai-arenaen-preferred': 'ai_arenaen_preferred',
    'dfm13-arena-human-preference-100k-preferred': 'arena_human_preference_100k',
    'dfm13-arena-human-preference-140k-preferred': 'arena_human_preference_140k',
    'dfm13-arena-human-preference-55k-preferred': 'arena_human_preference_55k',
    'comparia': 'comparia_preferred',
    'helpsteer3_edit': 'helpsteer3_edit',
    'helpsteer3_preference': 'helpsteer3_preference',
    'expert5k': 'arena_expert5k',
}


def repair_license_links(output, destinations_path):
    """Record a card-only HF metadata correction; leave data and source pins intact."""
    with lock(output/'.export.lock'):
        exporter.validate(output)
        inventory_path=output/'manifest.json'
        inventory=load(inventory_path)
        destinations=load(destinations_path)
        before=file_hash(inventory_path)
        changes=[]
        for package in inventory['packages']:
            card=output/package['name']/'README.md'
            text=card.read_text()
            old='license_link: ./manifest.json'
            if old not in text:
                continue
            meta=load(card.parent/'manifest.json')
            sources=meta['licenses']
            if len(sources)!=1:
                raise ValueError('Ambiguous source license link')
            repo=destinations[meta['component']]['repo_id']
            link='https://huggingface.co/datasets/'+repo+'/blob/main/manifest.json'
            prior=file_hash(card)
            card.write_text(text.replace(old,'license_link: '+link))
            package['card_sha256']=file_hash(card)
            changes.append(dict(path=str(card),before_sha256=prior,after_sha256=file_hash(card),license_link=link))
        if changes:
            write_json(inventory_path,inventory)
            write_json(output/'private/card-license-link-repair.json',dict(
                reason='HF requires HTTPS license_link, not relative URI',data_changed=False,
                before_inventory_sha256=before,after_inventory_sha256=file_hash(inventory_path),changes=changes))


def integrate(output, config_path, destinations_path):
    """Register pinned full-history rows; never tokenize, sample, or start training."""
    result = exporter.validate(output)
    ready = load(output/'private/publication-ready.json')
    if ready['inventory_sha256'] != result['inventory_sha256']:
        raise ValueError('Integration readiness drift')
    destinations = load(destinations_path)
    uploads = load(output/'private/upload-receipts.json')
    before = file_hash(config_path)
    config = load(config_path)
    additions = {entry['name']: entry for entry in config['additions']}
    if len(additions) != len(config['additions']):
        raise ValueError('Duplicate registry entries')
    registered, pending = [], []
    for package in load(output/'manifest.json')['packages']:
        folder = output/package['name']
        meta = load(folder/'manifest.json')
        name = NAMES[meta['component']]
        source = meta['licenses']
        if len(source) != 1:
            raise ValueError('Expected one pinned upstream source per package')
        source = source[0]
        entry = dict(additions.get(name, {}))
        legacy={key:entry.pop(key) for key in ('file','selection') if key in entry}
        if legacy:
            entry['upstream_conversion_provenance']=legacy
        entry.update(name=name, repo_id=source['source'], revision=source['revision'],
            license=source['license'], output=str(folder/'data/train.jsonl'),
            rows=package['rows'], output_sha256=meta['files']['data/train.jsonl'],
            target_policy='target_message_index_only_with_full_native_history', repeat=1,
            converter='scripts/export_dfm13_audited_arena.py',
            export_manifest=str(folder/'manifest.json'), export_manifest_sha256=package['manifest_sha256'],
            audit_quality_basis='automated accepted/recovered/repaired; unresolved and holds excluded; not certified gold',
            release_authorization=ready['release_path'], release_authorization_sha256=ready['release_sha256'],
            length_policy=meta['length_policy'], tokenization_performed=False)
        destination = destinations.get(meta['component'])
        if destination:
            repo = destination['repo_id']
            receipt = uploads.get(repo, {})
            if (receipt.get('status') != 'verified' or receipt.get('rows') != package['rows']
                    or receipt.get('manifest_sha256') != package['manifest_sha256']):
                raise ValueError('Required replacement not verified: '+repo)
            entry.update(hf_repo_id=repo, hf_revision=receipt['revision'], publication_status='verified')
        else:
            entry.update(publication_status='pending_canonical_repository_name')
            pending.append(meta['component'])
        additions[name] = entry
        registered.append(name)
    backup = output/'private/dfm13_sources.before-integration.json'
    if backup.exists():
        raise ValueError('Integration already attempted; preserve prior receipt')
    write_json(backup, config)
    config['additions'] = list(additions.values())
    if file_hash(config_path) != before:
        raise ValueError('Concurrent source registry edit')
    write_json(config_path, config)
    receipt = dict(stage='integrated', registered=registered, rows=result['rows'],
        config=str(config_path), before_sha256=before, after_sha256=file_hash(config_path),
        export_inventory_sha256=result['inventory_sha256'], pending_hf_components=pending,
        source_registration_only=True, tokenization_performed=False, sampling_performed=False,
        training_started=False, completed=time.time())
    write_json(output/'private/integration-receipt.json', receipt)
    return receipt


def run(args):
    output = args.output.resolve()
    receipt_path = output/'private/driver-status.json'
    with lock(output/'.release-driver.lock'):
        state = dict(pid=os.getpid(), started=time.time(), stage='waiting_export',
                     expected_packages=8, quality_certified=False)
        def update(stage, **details):
            state.update(stage=stage, updated=time.time(), **details)
            write_json(receipt_path,state)
            print(json.dumps(state),flush=True)
        try:
            update('waiting_export')
            deadline = time.monotonic()+1800
            while len(load(output/'manifest.json')['packages']) != 8:
                if time.monotonic()>deadline:
                    raise TimeoutError('Export did not complete within 30 minutes')
                time.sleep(10)
            update('validating')
            repair_license_links(output,args.destinations)
            checked=exporter.validate(output)
            update('authorizing', rows=checked['rows'])
            exporter.authorize(output,args.release)
            update('uploading_authorized_repositories')
            uploads=exporter.upload(output,args.destinations)
            update('integrating', uploaded_repositories=list(uploads))
            integration=integrate(output,args.config,args.destinations)
            update('complete_authorized_publication_and_integration', integration=integration)
            write_json(output/'private/completion-receipt.json',state)
        except BaseException as error:
            update('blocked',error=type(error).__name__+': '+str(error))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--release',type=Path,required=True)
    parser.add_argument('--destinations',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=ROOT/'config/dfm13_sources.json')
    run(parser.parse_args())
