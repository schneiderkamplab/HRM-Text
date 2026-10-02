"""Immutable Arena ledger exports; publication requires existing readiness guard."""
import argparse
from contextlib import ExitStack
import fcntl
import json
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import digest, file_hash, load, lock, write_json
from scripts import dfm13_arena_export_readiness as guard
from scripts.dfm13_arena_authorized_release import validate_release

COMPONENTS = {
    'dfm13-ai-arenaen-preferred': ('ai-arenaen', 'cc-by-4.0'),
    'dfm13-arena-human-preference-100k-preferred': ('arena-100k', 'other'),
    'dfm13-arena-human-preference-140k-preferred': ('arena-140k', 'other'),
    'dfm13-arena-human-preference-55k-preferred': ('arena-55k', 'apache-2.0'),
    'comparia': ('comparia', 'other'),
    'helpsteer3_edit': ('helpsteer3-edit', 'cc-by-4.0'),
    'helpsteer3_preference': ('helpsteer3-preference', 'cc-by-4.0'),
    'expert5k': ('expert5k', 'other'),
}
LENGTH_POLICY = 'Full original history and target preserved; no truncation or 4096-token cutoff. Training length filtering is separate and not performed.'
MASK_POLICY = 'Only messages[target_message_index] is a training target. All other messages, including earlier assistants and tool results, are context. Consumer must enforce target-only loss using the pinned native Gemma template.'


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def backup(source, destination):
    with readonly(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)


def identity(row):
    target = row.get('target_message_index')
    messages = row.get('messages')
    if (not isinstance(row.get('id'), str) or not isinstance(messages, list)
            or type(target) is not int or not 0 <= target < len(messages)
            or messages[target].get('role') != 'assistant'):
        raise ValueError('Invalid assistant target')
    for message in messages:
        if not isinstance(message, dict) or message.get('role') not in ('system', 'developer', 'user', 'assistant', 'tool'):
            raise ValueError('Invalid message')
    meta = row.get('metadata', {})
    if not all(meta.get(k) for k in ('source', 'revision', 'license')):
        raise ValueError('Missing source/license provenance')
    if not messages[target].get('content') and not messages[target].get('tool_calls'):
        raise ValueError('Empty target')
    # Include all model-input fields, not attribution IDs, in exact deduplication.
    return digest({k: v for k, v in row.items() if k not in ('id', 'metadata')})


def dump_line(handle, value):
    handle.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')


def source_component(source):
    key = source.get('name') or Path(source['path']).parts[-3]
    if key not in COMPONENTS:
        raise ValueError('Unapproved component: ' + key)
    return key


def snapshot(repair_root, destination):
    """Caller holds both controller locks; derived snapshots retain origin mapping."""
    plan = load(repair_root / 'plan.json')
    original = Path(plan['source'])
    destination.mkdir(parents=True)
    for label, origin in (('original', original), ('repair', repair_root)):
        folder = destination / label
        folder.mkdir()
        (folder / 'controller.lock').touch()
        backup(origin / 'ledger.sqlite', folder / 'ledger.sqlite')
        names = ('manifest.json', 'seal.json') if label == 'original' else ('plan.json', 'seal.json', 'complete.json')
        for name in names:
            shutil.copyfile(origin / name, folder / name)
    folder = destination / 'repair'
    backup(repair_root / 'input.sqlite', folder / 'input.sqlite')
    shutil.copyfile(repair_root / 'snapshot.json', folder / 'origin-input-snapshot.json')
    write_json(folder / 'snapshot.json', {'sha256': file_hash(folder / 'input.sqlite'),
        'derived_readonly_backup_of': str(repair_root / 'input.sqlite')})
    write_json(destination / 'origins.json', {'original': str(original), 'repair': str(repair_root)})
    return plan


def card(name, license_tag, sources):
    license_header = f'license: {license_tag}'
    if license_tag == 'other':
        license_header += '\nlicense_name: source-and-provider-terms\nlicense_link: ./manifest.json'
    return f'''---
{license_header}
task_categories: [text-generation]
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train.jsonl
---
# {name}

Model-audited preferred responses, including explicitly identified model repairs.
Not certified gold and not manually verified in full. Independent review is
sample-based where declared in the publication receipt; holds are excluded.
Repository split name `train` is a storage convention, not training admission.

{LENGTH_POLICY}

{MASK_POLICY}

No tokenization, regex fix, template rewriting, or training admission occurs in
this export. Native tools/calls/results and template kwargs are retained exactly.
Original metadata can say unaudited: it is preserved source-stage provenance;
the parallel provenance file records subsequent model audit/repair lineage.

Source revisions and license strings: {json.dumps(sources, ensure_ascii=False)}
Source/provider obligations remain applicable to repaired responses. Repair
teacher and audit implementation pins are recorded in the manifest. Do not infer
a blanket license grant from an upstream preferred vote or a quality verdict.
Exact duplicates are excluded with attribution in duplicates.jsonl. Inherited
DFM12 exhaustive overlap and post-repair benchmark semantic screening are not
claimed; this package does not silently relax later training-admission gates.
'''


def prepare(repair_root, output, version, holds_path=guard.HOLDS):
    repair_root, output, holds_path = map(lambda p: Path(p).resolve(), (repair_root, output, holds_path))
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,60}', version):
        raise ValueError('Unsafe version')
    if not guard.terminal_ready(repair_root / 'ledger.sqlite'):
        raise ValueError('Repair pipeline not terminal/unlocked')
    plan = load(repair_root / 'plan.json')
    original = Path(plan['source'])
    if not guard.terminal_ready(original / 'ledger.sqlite'):
        raise ValueError('Original pipeline not terminal/unlocked')
    output.mkdir(parents=True, exist_ok=True)
    with lock(output / '.export.lock'), ExitStack() as stack:
        for root in sorted((original, repair_root)):
            h = stack.enter_context((root / 'controller.lock').open('rb'))
            fcntl.flock(h, fcntl.LOCK_EX | fcntl.LOCK_NB)
        inventory_path = output / 'manifest.json'
        inventory = load(inventory_path) if inventory_path.exists() else dict(
            schema='dfm13-audited-arena-export-v1', version=version, batches=[], packages=[], admission=False)
        if inventory['version'] != version:
            raise ValueError('Version mismatch')
        if inventory['batches']:
            validate(output)
        batch_name = repair_root.name
        if any(b['name'] == batch_name for b in inventory['batches']):
            raise ValueError('Batch already exported; validate instead')
        private = output / 'private' / batch_name
        if private.exists():
            raise ValueError('Partial batch exists; preserve it and use a fresh root')
        private.mkdir(parents=True)
        holds = guard.strict_json(holds_path.read_text())
        # Pin the original hold source as well as the copy: later additions invalidate readiness.
        shutil.copyfile(holds_path, private / 'holds.json')
        pins = {str(holds_path): file_hash(holds_path), str(Path(__file__).resolve()): file_hash(__file__),
                str(Path(guard.__file__).resolve()): file_hash(guard.__file__)}
        for root, names in ((original, ('manifest.json', 'seal.json')),
                            (repair_root, ('plan.json', 'seal.json', 'complete.json', 'snapshot.json'))):
            for name in names:
                pins[str(root / name)] = file_hash(root / name)
        plan = snapshot(repair_root, private / 'snapshots')
        for source in plan['manifest']['sources']:
            if file_hash(source['path']) != source['sha256']:
                raise ValueError('Source hash drift')
            pins[source['path']] = source['sha256']
            if source.get('manifest_path'):
                if file_hash(source['manifest_path']) != source['manifest_sha256']:
                    raise ValueError('Source manifest hash drift')
                pins[source['manifest_path']] = source['manifest_sha256']
        template_pins = {p: h for p, h in plan['manifest'].get('pins', {}).items()
                         if Path(p).name in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja')}
        if not template_pins:
            raise ValueError('Missing tokenizer/template provenance')
        pins.update(template_pins)
        for path, expected in pins.items():
            if file_hash(path) != expected:
                raise ValueError('Pin drift: ' + path)
        seen = {}
        for package in inventory['packages']:
            with (output / package['name'] / 'data/train.jsonl').open() as stream:
                for line in stream:
                    row = guard.strict_json(line)
                    seen[identity(row)] = {'package': package['name'], 'id': row['id']}
        selections = {}
        packages = {}
        for source in plan['manifest']['sources']:
            component = source_component(source)
            short, license_tag = COMPONENTS[component]
            name = component if component.startswith('dfm13-') else f'dfm13-{short}'
            folder = output / name
            (folder / 'data').mkdir(parents=True, exist_ok=False)
            packages[source['path']] = dict(name=name, component=component, license_tag=license_tag,
                rows=0, held=0, duplicates=0, rejected=0, needs_review=0, sources={}, source=source,
                stream=stack.enter_context((folder / 'data/train.jsonl').open('x')),
                provenance=stack.enter_context((folder / 'provenance.jsonl').open('x')),
                duplicate_stream=stack.enter_context((folder / 'duplicates.jsonl').open('x')))
        rdb = stack.enter_context(readonly(private / 'snapshots/repair/ledger.sqlite'))
        odb = stack.enter_context(readonly(private / 'snapshots/repair/input.sqlite'))
        checked = set()
        exclusions = stack.enter_context((private / 'exclusions.jsonl').open('x'))
        for table in ('rejected', 'needs_review'):
            for seq, raw in rdb.execute(f'SELECT seq,record FROM {table} ORDER BY seq'):
                record = guard.strict_json(raw)
                packages[record['source']['path']][table] += 1
                dump_line(exclusions, dict(seq=seq, source_id=record['source_id'], disposition=table,
                                          record_sha256=digest(record)))
        for seq, raw in rdb.execute('SELECT seq,record FROM accepted ORDER BY seq'):
            record = guard.strict_json(raw)
            row, status, audit, source, line = guard.source_row(odb, plan['manifest'], seq, checked)
            package = packages[source['path']]
            kind = 'repaired' if record.get('candidate') is not None else ('original' if status == 'complete' else 'recovered')
            candidate = record['candidate'] if kind == 'repaired' else row
            actual = digest(candidate)
            if record.get('seq') != seq or record.get('original_row_sha256') != digest(row):
                raise ValueError('Accepted original provenance mismatch')
            if (record.get('source_id') != row['id'] or record.get('source_line') != line
                    or record.get('source') != {'path': source['path'], 'sha256': source['sha256']}):
                raise ValueError('Accepted source provenance mismatch')
            if kind == 'original' and (record.get('decision') != audit.get('result') or record['decision'].get('verdict') != 'keep'):
                raise ValueError('Accepted original keep mismatch')
            proof = dict(seq=seq, source_id=row['id'], candidate_sha256=actual)
            blocked = guard.blocked(proof, original / 'ledger.sqlite', holds)
            blocked += guard.blocked(proof, repair_root / 'ledger.sqlite', holds)
            if blocked:
                package['held'] += 1
                dump_line(exclusions, dict(proof, disposition='independent_hold', findings=blocked))
                continue
            key = identity(candidate)
            if key in seen:
                package['duplicates'] += 1
                duplicate = dict(proof, metadata=candidate['metadata'], winner=seen[key], fingerprint=key)
                dump_line(package['duplicate_stream'], duplicate)
                dump_line(exclusions, dict(duplicate, disposition='exact_duplicate'))
                continue
            seen[key] = dict(package=package['name'], id=candidate['id'])
            group = package['name'] + '--' + kind
            ledger = private / 'snapshots' / ('original' if kind == 'original' else 'repair') / 'ledger.sqlite'
            selection = selections.setdefault(group, dict(ledger=str(ledger), candidates=[]))
            selection['candidates'].append(dict(seq=seq, kind=kind, candidate_sha256=actual))
            dump_line(package['stream'], candidate)
            dump_line(package['provenance'], dict(proof, kind=kind, original_row_sha256=digest(row),
                source=record['source'], source_line=line, fingerprint=key, selection_group=group,
                origin_ledger=str((original if kind == 'original' else repair_root) / 'ledger.sqlite'),
                record_sha256=digest(record), audit_result=audit.get('result') if audit else None,
                decision=record.get('decision'), fresh_reaudit=record.get('fresh_reaudit'),
                quality_basis='model_audit; independent_review_scope_recorded_separately', admission=False))
            meta = candidate['metadata']
            package['sources'][digest({k: meta[k] for k in ('source', 'revision', 'license')})] = {k: meta[k] for k in ('source', 'revision', 'license')}
            package['rows'] += 1
        groups = []
        for group, selection in selections.items():
            path = private / 'selections' / (group + '.json')
            write_json(path, selection)
            evidence = {}
            if guard.check_selection(Path(selection['ledger']), selection, holds, evidence):
                raise ValueError('Held candidate survived filtering')
            groups.append(dict(name=group, path=str(path), sha256=file_hash(path), **evidence))
        for package in packages.values():
            folder = output / package['name']
            for key in ('stream', 'provenance', 'duplicate_stream'):
                package.pop(key).close()
            sources = list(package.pop('sources').values())
            write_json(folder / 'manifest.json', dict(schema='dfm13-audited-arena-package-v1',
                name=package['name'], component=package['component'], rows=package['rows'],
                disposition_counts={k: package[k] for k in ('rows','held','duplicates','rejected','needs_review')},
                upstream_rows=package['source']['rows'], source=package['source'], licenses=sources,
                files={n: file_hash(folder/n) for n in ('data/train.jsonl','provenance.jsonl','duplicates.jsonl')},
                length_policy=LENGTH_POLICY, mask_policy=MASK_POLICY, template_pins=template_pins,
                regex_fix=False, tokenization_performed=False, admission=False, quality_certified=False,
                inherited_overlap='not exhaustively screened', post_repair_benchmark_screen='not performed',
                batch=batch_name, audit_manifest_version=plan['manifest']['version'],
                audit_model=plan['manifest']['model'], audit_implementation_pins=plan['manifest']['pins']))
            (folder / 'README.md').write_text(card(package['name'], package['license_tag'], sources))
            inventory['packages'].append(dict(name=package['name'], rows=package['rows'], batch=batch_name,
                manifest_sha256=file_hash(folder/'manifest.json'), card_sha256=file_hash(folder/'README.md')))
        snapshot_pins = {str(p): file_hash(p) for p in (private/'snapshots').rglob('*')
                         if p.is_file() and not p.name.endswith(('-shm','-wal')) and p.name != 'controller.lock'}
        batch = dict(name=batch_name, origin=str(repair_root), pins=pins, snapshot_pins=snapshot_pins,
                     holds=str(private/'holds.json'), holds_sha256=file_hash(private/'holds.json'), groups=groups,
                     exclusions=str(private/'exclusions.jsonl'))
        exclusions.close()
        batch['exclusions_sha256'] = file_hash(batch['exclusions'])
        inventory['batches'].append(batch)
        write_json(inventory_path, inventory)
        result = validate(output)
        write_json(private / 'validation.json', result)
        return result


def validate(output):
    output = Path(output).resolve()
    inventory = load(output/'manifest.json')
    if inventory.get('schema') != 'dfm13-audited-arena-export-v1':
        raise ValueError('Unknown export inventory')
    seen, total = set(), 0
    names = set()
    for batch in inventory['batches']:
        for p, h in {**batch['pins'], **batch['snapshot_pins']}.items():
            if file_hash(p) != h:
                raise ValueError('Export input drift: ' + p)
        if file_hash(batch['holds']) != batch['holds_sha256'] or file_hash(batch['exclusions']) != batch['exclusions_sha256']:
            raise ValueError('Hold/exclusion drift')
        for group in batch['groups']:
            if file_hash(group['path']) != group['sha256']:
                raise ValueError('Selection drift')
    for package in inventory['packages']:
        name = package['name']
        if not re.fullmatch(r'dfm13-[a-z0-9-]+', name) or name in names:
            raise ValueError('Unsafe/duplicate package')
        names.add(name)
        folder = output/name
        if not folder.resolve().is_relative_to(output):
            raise ValueError('Package escapes export root')
        if file_hash(folder/'manifest.json') != package['manifest_sha256'] or file_hash(folder/'README.md') != package['card_sha256']:
            raise ValueError('Package metadata drift')
        meta = load(folder/'manifest.json')
        if set(meta['files']) != {'data/train.jsonl','provenance.jsonl','duplicates.jsonl'}:
            raise ValueError('Unexpected file inventory')
        for p,h in meta['files'].items():
            if not (folder/p).resolve().is_relative_to(folder.resolve()) or file_hash(folder/p) != h:
                raise ValueError('Data file drift/escape')
        count = 0
        with (folder/'data/train.jsonl').open() as data, (folder/'provenance.jsonl').open() as provenance:
            for line in data:
                row, proof = guard.strict_json(line), guard.strict_json(provenance.readline())
                key = identity(row)
                if key in seen or key != proof['fingerprint'] or digest(row) != proof['candidate_sha256'] or row['id'] != proof['source_id']:
                    raise ValueError('Duplicate or row/provenance mismatch')
                seen.add(key)
                count += 1
            if provenance.readline():
                raise ValueError('Extra provenance rows')
        if count != package['rows'] or count != meta['rows'] or sum(meta['disposition_counts'].values()) != meta['upstream_rows']:
            raise ValueError('Row accounting mismatch')
        total += count
    return dict(packages=len(names), rows=total, admission=False, upload_authorized=False,
                inventory_sha256=file_hash(output/'manifest.json'))


def certify(output, reviews_path):
    output = Path(output).resolve()
    with lock(output/'.export.lock'):
        result = validate(output)
        reviews = load(reviews_path)
        inventory = load(output/'manifest.json')
        receipts = []
        for batch in inventory['batches']:
            for group in batch['groups']:
                review = reviews[group['name']]
                path = Path(group['path'])
                receipt = output/'private'/'certification'/f"{group['name']}.json"
                selection = load(path)
                guard.prepare(Path(selection['ledger']), path, receipt,
                              Path(review['manual_review']), Path(batch['holds']), Path(review['assessment']))
                guard.enforce(receipt)
                receipts.append(dict(path=str(receipt), sha256=file_hash(receipt)))
        write_json(output/'private/publication-ready.json', dict(**result, receipts=receipts,
            reviews_path=str(Path(reviews_path).resolve()), reviews_sha256=file_hash(reviews_path),
            publication_checks_passed=True, quality_certified=False))
        return result


def authorize(output, release_path):
    """Bind the explicit automated release to every exported row, without gold claims."""
    output, release_path = Path(output).resolve(), Path(release_path).resolve()
    with lock(output/'.export.lock'):
        result = validate(output)
        release = validate_release(release_path)
        allowed = set()
        for entry in release['selections']:
            for row in load(entry['selection'])['candidates']:
                allowed.add((str(Path(entry['ledger']).resolve()), row['seq'], row['candidate_sha256']))
        for package in load(output/'manifest.json')['packages']:
            with (output/package['name']/'provenance.jsonl').open() as stream:
                for line in stream:
                    row = guard.strict_json(line)
                    if (row['origin_ledger'], row['seq'], row['candidate_sha256']) not in allowed:
                        raise ValueError('Export row absent from authorized selection')
        write_json(output/'private/publication-ready.json', dict(**result,
            release_path=str(release_path), release_sha256=file_hash(release_path),
            publication_checks_passed=True, quality_certified=False, manual_per_row_verified=False))
        return result


def upload(output, destinations_path):
    from huggingface_hub import HfApi, CommitOperationAdd, CommitOperationDelete, hf_hub_download
    from huggingface_hub.errors import RepositoryNotFoundError
    output = Path(output).resolve()
    destinations = load(destinations_path)
    with lock(output/'.export.lock'):
        result = validate(output)
        ready = load(output/'private/publication-ready.json')
        if ready['inventory_sha256'] != result['inventory_sha256'] or not ready.get('publication_checks_passed'):
            raise ValueError('Publication readiness mismatch')
        if file_hash(ready['release_path']) != ready['release_sha256']:
            raise ValueError('Release authorization drift')
        validate_release(ready['release_path'])
        api = HfApi()
        api.whoami()
        path = output/'private/upload-receipts.json'
        saved = load(path) if path.exists() else {}
        for package in load(output/'manifest.json')['packages']:
            if package['rows'] == 0:
                continue
            component = load(output/package['name']/'manifest.json')['component']
            if component not in destinations:
                continue
            destination = destinations[component]
            repo = destination['repo_id']
            if not re.fullmatch(r'schneiderkamplab/dfm13-[a-z0-9-]+', repo):
                raise ValueError('Unsafe destination')
            if saved.get(repo,{}).get('status') == 'verified':
                if saved[repo]['manifest_sha256'] != package['manifest_sha256']:
                    raise ValueError('Uploaded package drift')
                continue
            try:
                info = api.repo_info(repo, repo_type='dataset')
                exists = True
            except RepositoryNotFoundError:
                exists = False
            if exists and repo not in saved and info.sha != destination.get('expected_revision'):
                raise ValueError('Replacement revision changed: '+repo)
            if not exists and destination.get('allow_create') is not True:
                raise ValueError('New repository not explicitly authorized: '+repo)
            folder = output/package['name']
            files = ['README.md','manifest.json','data/train.jsonl','provenance.jsonl','duplicates.jsonl']
            if repo in saved and saved[repo]['manifest_sha256'] != package['manifest_sha256']:
                raise ValueError('Partial upload package drift')
            previous_files = api.list_repo_files(repo, repo_type='dataset') if exists else []
            saved[repo] = dict(status='publishing', manifest_sha256=package['manifest_sha256'],
                previous_revision=info.sha if exists else None, started=time.time())
            write_json(path,saved)
            api.create_repo(repo,repo_type='dataset',exist_ok=exists,private=False)
            commit = api.create_commit(repo,repo_type='dataset',commit_message='Replace unaudited rows with user-authorized model-audited selection; not certified gold',
                parent_commit=info.sha if exists else None,
                operations=[CommitOperationAdd(path_in_repo=n,path_or_fileobj=str(folder/n)) for n in files]
                + [CommitOperationDelete(path_in_repo=n) for n in previous_files if n not in files and n != '.gitattributes'])
            if set(api.list_repo_files(repo,repo_type='dataset',revision=commit.oid))- {'.gitattributes'} != set(files):
                raise ValueError('Remote inventory mismatch')
            for n in files:
                remote = hf_hub_download(repo,n,repo_type='dataset',revision=commit.oid)
                if file_hash(remote) != file_hash(folder/n):
                    raise ValueError('Remote byte mismatch')
            saved[repo].update(status='verified', revision=commit.oid, rows=package['rows'], completed=time.time())
            write_json(path,saved)
        return saved


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','validate','certify','authorize','upload'])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repair-root',type=Path)
    parser.add_argument('--version',default='20261001-v1')
    parser.add_argument('--holds',type=Path,default=guard.HOLDS)
    parser.add_argument('--reviews',type=Path)
    parser.add_argument('--release',type=Path)
    parser.add_argument('--destinations',type=Path)
    args=parser.parse_args()
    if args.command=='prepare': result=prepare(args.repair_root,args.output,args.version,args.holds)
    elif args.command=='validate': result=validate(args.output)
    elif args.command=='certify': result=certify(args.output,args.reviews)
    elif args.command=='authorize': result=authorize(args.output,args.release)
    else: result=upload(args.output,args.destinations)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
