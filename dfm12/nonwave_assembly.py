"""Narrow audited Arena/JJzha publication and native-token admission contracts."""
from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3

ARENA = frozenset(('ai_arenaen_preferred', 'arena_human_preference_140k',
    'arena_human_preference_100k', 'arena_human_preference_55k', 'comparia_preferred',
    'helpsteer3_edit', 'helpsteer3_preference', 'arena_expert5k'))
JJZHA = frozenset(('jjzha_skillspan', 'jjzha_kompetencer', 'jjzha_green',
    'jjzha_imdb_dutch', 'jjzha_dutch_exam', 'jjzha_croco'))
NAMES = ARENA | JJZHA
_RELEASE_CACHE = {}


def release_state(path):
    """Track every mutable input used by the shared Arena selection guard."""
    from .io import load
    from scripts.assemble_dfm13_additions import signature
    release = load(path); paths = {str(Path(path).resolve()), *release['pins']}
    for selection in release['selections']:
        paths.add(selection['readiness']); receipt = load(selection['readiness'])
        paths.update(receipt['pins'])
        root = Path(receipt['ledger']).resolve().parent
        paths.update(str(root/name) for name in ('ledger.sqlite', 'ledger.sqlite-wal',
            'input.sqlite', 'input.sqlite-wal', 'plan.json', 'seal.json', 'manifest.json', 'snapshot.json'))
        if (root/'plan.json').exists():
            plan = load(root/'plan.json'); manifest = plan['manifest']; paths.update(plan['pins'])
            paths.update(str(Path(plan['source'])/name) for name in ('manifest.json', 'seal.json'))
        else:
            manifest = load(root/'manifest.json')
        paths.update(s['path'] for s in manifest['sources'])
    return {str(Path(p).resolve()): signature(Path(p)) if Path(p).exists() else None for p in paths}


def checked_release(path):
    from scripts.dfm13_arena_authorized_release import validate_release
    key = str(Path(path).resolve()); before = release_state(path)
    cached = _RELEASE_CACHE.get(key)
    if cached and cached[0] == before:
        return cached[1], before
    release = validate_release(path)
    after = release_state(path)
    if before != after:
        raise ValueError('Arena evidence changed during shared validation')
    _RELEASE_CACHE[key] = (after, release)
    return release, after


def unready_reason(entry):
    if entry.get('name') not in NAMES:
        return 'unsupported_non_wave_contract'
    if type(entry.get('repeat')) is not int or entry['repeat'] <= 0:
        return 'invalid_or_zero_nonwave_repeat'
    if not entry.get('hf_revision') or not entry.get('hf_repo_id'):
        return 'nonwave_publication_not_ready'
    if entry['name'] in ARENA:
        if entry.get('publication_status') != 'verified':
            return 'nonwave_publication_not_ready'
    elif entry.get('status') != 'accepted_uploaded':
        return 'nonwave_publication_not_ready'
    if entry.get('context_view') and entry.get('context_view_sha256'):
        return None
    if entry.get('tokenized_sequences_over_4096', 0) or entry.get('tokenization_admission_blocker'):
        return 'nonwave_full_native_rows_exceed_4096_no_truncation'
    if (entry.get('tokenization_performed') is not True or
            not all(entry.get(k) for k in ('tokenized_path', 'tokenization_receipt',
                                          'tokenization_receipt_sha256'))):
        return 'nonwave_target_only_tokenization_not_ready'
    return None


def jjzha_row(row, job, prepared):
    from scripts.finalize_dfm13_jjzha import validate, policy, is_imdb
    if job is None:
        raise ValueError('Missing JJzha ledger row')
    if prepared.get('status') not in ('prepared', 'pending_audit'):
        raise ValueError('Unknown JJzha preparation status')
    encoded, status, raw_evidence = job
    original, evidence = json.loads(encoded), json.loads(raw_evidence)
    validate(original)
    if status not in ('accepted', 'accepted_repair') or not policy(original):
        raise ValueError('JJzha unresolved/rejected/policy-denied row')
    if status == 'accepted_repair':
        if evidence.get('reaudit', {}).get('verdict') != 'keep':
            raise ValueError('JJzha repair lacks keep')
        if is_imdb(original) and original['messages'][-1]['content'].strip().lower() not in ('positief', 'negatief'):
            raise ValueError('JJzha IMDb answer changed task')
    elif prepared['status'] == 'pending_audit':
        decision = evidence.get('audit') or evidence.get('original', {}).get('result', {})
        if decision.get('verdict') != 'keep':
            raise ValueError('JJzha original lacks keep')
    expected = copy.deepcopy(original)
    expected['metadata'].update(audit_required=False, quality_status=status,
        quality_method='model_review' if prepared['status'] == 'pending_audit' else 'source_specific_validation')
    if expected != row:
        raise ValueError('JJzha exported row differs from accepted ledger')


def publication(entry, pins, api=None):
    if api is None:
        from scripts import assemble_dfm13_additions as api
    from dfm12.wave_publication_holds import entry_quality_hold
    api.require(entry['name'] in NAMES and not entry_quality_hold(entry), 'Nonwave scope/hold')
    source = api.pin(entry['output'], pins, entry['output_sha256'])
    folder = source.parent.parent
    if entry['name'] in ARENA:
        from scripts import export_dfm13_audited_arena as exporter
        root = folder.parent
        result = exporter.validate(root)
        ready = api.read_json(root/'private/publication-ready.json', pins)
        api.require(ready.get('publication_checks_passed') is True and
                    ready['inventory_sha256'] == result['inventory_sha256'], 'Arena readiness mismatch')
        api.require(ready['release_path'] == entry['release_authorization'] and
                    ready['release_sha256'] == entry['release_authorization_sha256'], 'Arena authorization mismatch')
        api.pin(ready['release_path'], pins, ready['release_sha256'])
        release, release_inputs = checked_release(ready['release_path'])
        for path, state in release_inputs.items():
            if state is not None:
                api.pin(path, pins)
        for path, sha in release['pins'].items():
            api.pin(path, pins, sha)
        for selection in release['selections']:
            readiness = api.read_json(selection['readiness'], pins)
            for path, sha in readiness['pins'].items():
                api.pin(path, pins, sha)
        receipt = api.read_json(root/'private/upload-receipts.json', pins)[entry['hf_repo_id']]
        manifest = api.read_json(entry['export_manifest'], pins, entry['export_manifest_sha256'])
        api.require(receipt['status'] == 'verified' and receipt['revision'] == entry['hf_revision']
                    and receipt['manifest_sha256'] == entry['export_manifest_sha256']
                    and receipt['rows'] == entry['rows'] == manifest['rows'], 'Arena upload mismatch')
        api.require(entry['target_policy'] == 'target_message_index_only_with_full_native_history'
                    and manifest['mask_policy'] == exporter.MASK_POLICY and manifest['regex_fix'] is False,
                    'Arena mask/regex contract changed')
        api.require(any(x['source'] == entry['repo_id'] and x['revision'] == entry['revision']
                        and x['license'] == entry['license']
                        for x in manifest['licenses']), 'Arena source lineage mismatch')
        for relative, sha in manifest['files'].items():
            api.pin(folder/relative, pins, sha)
        inventory = api.read_json(root/'manifest.json', pins, result['inventory_sha256'])
        for batch in inventory['batches']:
            for path, sha in {**batch['pins'], **batch['snapshot_pins']}.items():
                api.pin(path, pins, sha)
        quality = 'automated model audit; not certified gold'
    else:
        receipt = api.read_json(entry['manifest'], pins)
        manifest = api.read_json(folder/'manifest.json', pins)
        api.require(receipt.get('uploaded') is True and receipt['hf_revision'] == entry['hf_revision'],
                    'JJzha publication mismatch')
        for key in ('name', 'rows', 'output', 'output_sha256', 'license', 'repeat'):
            api.require(receipt[key] == manifest[key] == entry[key], 'JJzha publication field: '+key)
        for key, field in (('source_repo', 'repo_id'), ('source_revision', 'revision'), ('repo_id', 'hf_repo_id')):
            api.require(receipt[key] == manifest[key] == entry[field], 'JJzha lineage field: '+key)
        api.require(entry['target_policy'] == 'final_assistant_only_native_gemma', 'JJzha target policy')
        prepared = api.read_json(Path(receipt['audit_ledger']).parent/'prepared.json', pins)['manifests'][entry['name']]
        api.require(prepared['spec']['repo_id'] == entry['repo_id'] and
                    prepared['spec']['revision'] == entry['revision'] and
                    prepared['spec']['license'] == entry['license'], 'JJzha preparation lineage')
        for path, sha in prepared['raw_sha256'].items():
            api.pin(path, pins, sha)
        api.pin(prepared['output'], pins, prepared['output_sha256'])
        with closing(sqlite3.connect(Path(receipt['audit_ledger']).resolve().as_uri()+'?mode=ro', uri=True)) as db:
            db.execute('BEGIN')
            count = 0
            seen = set()
            with source.open() as stream:
                for line in stream:
                    row = json.loads(line)
                    api.require(row['id'] not in seen, 'Duplicate JJzha export ID')
                    seen.add(row['id'])
                    job = db.execute('SELECT row,status,evidence FROM jobs WHERE id=? AND source=?',
                                     (row['id'], entry['name'])).fetchone()
                    jjzha_row(row, job, prepared)
                    count += 1
            api.require(count == entry['rows'], 'JJzha row count')
        quality = ('automated model audit' if prepared['status'] == 'pending_audit'
                   else 'source-specific validation; not blanket model audited')
    api.pin(folder/'README.md', pins)
    return dict(source=str(source), quality_basis=quality, license=entry['license'],
                repo_id=entry['repo_id'], revision=entry['revision'])


def verify(entry, contract, pins, api=None):
    if api is None:
        from scripts import assemble_dfm13_additions as api
    api.require(unready_reason(entry) is None, 'Nonwave tokenization/publication not ready')
    if entry.get('context_view'):
        from .nonwave_context_view import verify as verify_view
        return verify_view(entry, contract, pins, api)
    provenance = publication(entry, pins, api)
    source = Path(provenance['source'])
    receipt = api.read_json(entry['tokenization_receipt'], pins, entry['tokenization_receipt_sha256'])
    api.require(receipt.get('schema') == 'dfm13-nonwave-target-only-tokenization-v1'
                and receipt.get('source_sha256') == entry['output_sha256']
                and receipt.get('target_policy') == entry['target_policy']
                and receipt.get('hard_truncation') is False and receipt.get('regex_fix') is False,
                'Nonwave token receipt policy/payload mismatch')
    root = Path(entry['tokenized_path']).resolve(strict=True)
    api.require(Path(receipt['output']).resolve() == root, 'Nonwave token output mismatch')
    inventory = receipt['files']
    api.require(bool(inventory) and {str(p.resolve()) for p in root.rglob('*') if p.is_file()} ==
                {str(Path(p).resolve()) for p in inventory}, 'Nonwave token inventory mismatch')
    for path, sha in inventory.items():
        api.require(Path(path).resolve().is_relative_to(root), 'Nonwave token path escape')
        api.pin(path, pins, sha)
    info = api.read_json(root/'tokenizer_info.json', pins)
    api.require(api.token_contract(info, pins) == contract, 'Nonwave tokenizer/template mismatch')
    completion = api.read_json(root/'completion.json', pins)
    api.require(completion['rows'] == entry['rows'] and completion['skipped_rows_this_run'] == 0
                and completion['max_seq_len'] is None, 'Nonwave dropped/truncated rows')
    parts = sorted(p for p in root.iterdir() if p.is_dir())
    api.require(bool(parts) and len(parts) == completion['files'], 'Nonwave shard inventory mismatch')
    verified = [dict(api.verify_arrays(p, contract['vocab_size'], pins), path=str(p),
                     link_name=entry['name']+'__'+p.name) for p in parts]
    rows = sum(p['rows'] for p in verified); tokens = sum(p['tokens'] for p in verified)
    api.require(rows == entry['rows'] == receipt['rows'] == entry['tokenized_rows'] and
                tokens == receipt['tokens'] == entry['tokenized_tokens'], 'Nonwave token counts mismatch')
    parity = api.verify_native_sample(source, verified, info, rows)
    return dict(provenance, name=entry['name'], repeat=entry['repeat'], rows=rows, tokens=tokens,
        parts=verified, tokenized_root=str(root), native_token_parity=parity,
        hf_repo_id=entry['hf_repo_id'], hf_revision=entry['hf_revision'],
        publication_contract='audited-nonwave-target-only-v1', target_policy=entry['target_policy'])
