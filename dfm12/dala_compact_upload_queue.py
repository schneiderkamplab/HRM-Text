"""Freeze explicit completed-subset upload intent and Tesla's train-only intake."""
import argparse
from pathlib import Path
from .io import load, file_hash, write_json

CONTRACT = 'dala-compact-whole-pair-four-labels-v1'
SCOPE = {'en':'baseline', 'de':'baseline', 'fr':'baseline', 'es':'baseline',
         'it':'baseline', 'pt-PT':'baseline', 'cs':'baseline', 'nl':'recovery', 'fa':'recovery'}


def pinned(path):
    return dict(path=str(Path(path).resolve()), sha256=file_hash(path))


def prepare_item(root, language, pool):
    group = root/'groups'/(language+'-'+pool)
    integration = load(group/'integration.json')
    if integration.get('status') != 'complete_train_only' or integration.get('contract') != CONTRACT:
        raise ValueError('Incomplete/unknown integration')
    if integration['export'] != pinned(group/'export.json'):
        raise ValueError('Export receipt drift')
    export = load(group/'export.json')
    if (export['snapshot'] != pinned(group/'snapshot.json') or export['language'] != language
            or export['contract'] != CONTRACT or export.get('producer_v2_audit_equivalent') is not False):
        raise ValueError('Snapshot/contract mismatch')
    snapshot = load(group/'snapshot.json')
    if snapshot.get('terminal') is not True or snapshot.get('consistent_read_transaction') is not True:
        raise ValueError('Nonterminal audit')
    components = integration['components']
    if len(components) != 2 or {c['task'] for c in components} != {'acceptability','correction'}:
        raise ValueError('Both train tasks required')
    for c in components:
        if (c['split'] != 'train' or c['status'] != 'accepted_local_tokenized'
                or c['audit_contract'] != CONTRACT or c['language'] != language
                or c.get('producer_v2_audit_equivalent') is not False
                or c['export_receipt'] != pinned(group/'export.json')
                or c['snapshot'] != pinned(group/'snapshot.json')
                or c['rows'] <= 0 or c['tokens'] <= 0):
            raise ValueError('Invalid train-only component')
    files = []
    for spec in export['files']:
        relative = Path(spec['relative'])
        if relative.parts[0] != 'exports':
            continue
        path = Path(spec['path']).resolve()
        if not path.is_relative_to((group/'exports').resolve()) or path != (group/relative).resolve():
            raise ValueError('Export path escapes group')
        if len(relative.parts) != 3 or relative.parts[1] not in ('acceptability','correction'):
            raise ValueError('Unknown task export')
        if relative.name not in {s+'.jsonl.gz' for s in ('train_representative',
                'validation_representative','validation_challenge','test_representative','test_challenge')}:
            raise ValueError('Unknown split export')
        if not path.is_file():
            raise ValueError('Missing export')
        files.append(dict(spec, repo_path='data/'+str(Path(*relative.parts[1:]))))
    if not files:
        raise ValueError('No all-split exports')
    for task in ('acceptability','correction'):
        n = sum(f['rows'] for f in files if f['repo_path'] == 'data/'+task+'/train_representative.jsonl.gz')
        if n != next(c['rows'] for c in components if c['task'] == task):
            raise ValueError('Train export/tokenized count mismatch')
    return dict(language=language, subset=pool, status='queued_for_upload', uploaded=False,
        remote_revision=None, remote_verification_receipt=None,
        proposed_repo_id='schneiderkamplab/dfm13-dala-v2-'+language.lower()+'-compact-'+pool,
        audit_contract=CONTRACT, producer_v2_audit_equivalent=False,
        integration=pinned(group/'integration.json'), export=pinned(group/'export.json'),
        snapshot=pinned(group/'snapshot.json'), files=files, counts=export['counts'],
        upload_file_hashes='Pinned by finalized export receipt; uploader must rehash before upload',
        train_components=components)


def prepare(root, output):
    items = [prepare_item(root, lang, pool) for lang,pool in SCOPE.items()]
    output.mkdir(parents=True, exist_ok=False)
    queue = dict(schema='dala-v2-completed-nine-upload-queue-v1', user_authorized=True,
        operation='upload_completed_subsets_and_combined_train_integration', items=items,
        uploaded=False, gpu_actions=False, source_finalizer_root=str(root.resolve()),
        source_finalizer_modified=False, integration_owner='Tesla',
        publication_requirements=[
            'Preserve all split/view task files and per-row source/license/author/URL provenance',
            'Publish model-audit and source attribution notices without claiming one license covers all sources',
            'Disclose compact automated review, not native or isolated-per-edit certification',
            'Verify every local export hash before upload and every remote attachment hash after commit',
            'Only verified remote revision and receipt can mark uploaded; do not overwrite v1 repos',
            'NL and FA here are recovery-only; do not imply their baseline pools are included'],
        registry_components=18, inventory_script=pinned(__file__))
    write_json(output/'queue.json', queue)
    components = [c for item in items for c in item['train_components']]
    write_json(output/'integration-handoff.json', dict(schema=CONTRACT, inherits='dfm12',
        additions=components, owner='Tesla', source_queue=pinned(output/'queue.json'),
        combined_integration_requested=True, combined_integration_performed=False,
        training_rows=sum(c['rows'] for c in components), tokens=sum(c['tokens'] for c in components),
        uploaded=False, central_registry_modified=False))
    write_json(output/'seal.json', dict(queue=pinned(output/'queue.json'),
        integration=pinned(output/'integration-handoff.json')))
    return queue


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('data/dfm13/dala-v2-compact-finalized-20261004-v1'))
    p.add_argument('--output',type=Path,default=Path('data/dfm13/dala-v2-upload-nine-20261004-v1'))
    a=p.parse_args(); q=prepare(a.root,a.output)
    print('QUEUED',len(q['items']),'uploaded',q['uploaded'])
