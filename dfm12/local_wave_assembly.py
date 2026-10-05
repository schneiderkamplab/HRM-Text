"""Explicit local-only OPUS translation contract; publication remains pending."""
import re
from pathlib import Path

CONTRACT = 'accepted-local-wave-translation-v1'


def unready(entry):
    if not re.fullmatch(r'dfm13_wave4_opus_[a-z_]+', entry.get('name', '')):
        return 'unsupported_local_source'
    if (entry.get('uploaded') is not False or entry.get('hf_revision') is not None
            or entry.get('status') != 'accepted_local_tokenized'):
        return 'invalid_local_publication_state'
    if (entry.get('tokenization_performed') is not True or not entry.get('selection_receipt')
            or not entry.get('tokenization_receipt') or not entry.get('tokenized_path')):
        return 'local_tokenization_not_ready'
    if type(entry.get('repeat')) is not int or entry['repeat'] != 1:
        return 'invalid_local_repeat'
    return None


def publication(entry, source, pins, api):
    api.require(unready(entry) is None, 'Invalid local admission contract')
    export = api.read_json(source.parent.parent/'manifest.json', pins, entry['export_manifest_sha256'])
    selection = api.read_json(entry['selection_receipt'], pins, entry['selection_receipt_sha256'])
    api.require(selection['ready'] is True and not selection['pending_components'], 'Unfinished selection')
    api.require(type(selection['selected_pairs']) is int and selection['selected_pairs'] > 0,
                'Invalid selected pair count')
    api.require(selection['sha256'] == export['selection_sha256'] == entry['selection_sha256'], 'Selection binding mismatch')
    api.pin(selection['path'], pins, selection['sha256'])
    api.require(export['rows'] == 2*selection['selected_pairs'] and
                export['rendered_tokens'] == selection['combined_rendered_tokens'] <= selection['token_cap'],
                'Selection budget/count mismatch')
    # Bind the exact source freeze and budget instead of treating an export flag as approval.
    root = Path(entry['selection_receipt']).parent.parent.parent
    manifest = root/'combined-audit-manifest.json'
    if not manifest.exists():
        manifest = root/'audit/translation-manifest.json'
    api.pin(manifest, pins, selection['audit_manifest_sha256'])
    budget = api.read_json(root/'translations/token-budgets.json', pins, selection['budget_receipt_sha256'])
    api.pin(budget['source_report'], pins, budget['source_report_sha256'])
    for sha, relative in export['attribution_files'].items():
        path = (source.parent.parent/relative).resolve()
        api.require(path.is_relative_to(source.parent.parent), 'Attribution escapes package')
        evidence = api.read_json(path, pins, sha)['entry']
        license_id = evidence.get('license', '').lower()
        api.require(evidence.get('status') == 'approved' and bool(evidence.get('url')) and
                    re.fullmatch(r'cc-by(?:-sa)?-[234]\.0|cc0-1\.0|public-domain', license_id),
                    'Unapproved local attribution')
    return export, export


def registry(roots):
    from dfm12.io import load, file_hash
    entries = []
    for root, integration in roots:
        for item in load(integration)['sources']:
            # Language variants contain underscores: derive the canonical name from the pair.
            folder = Path('exports_dfm13')/('dfm13-wave4-opus-'+item['pair'])
            manifest = folder/'manifest.json'
            export = load(manifest)
            receipt = integration.parent/item['name']/'verified.json'
            selection = root/'translation-release'/item['pair']/'receipt.json'
            entries.append(dict(export, publication_contract=CONTRACT, status='accepted_local_tokenized',
                uploaded=False, hf_revision=None, publication_pending=True,
                manifest=str(manifest.resolve()), export_manifest_sha256=file_hash(manifest),
                selection_receipt=str(selection.resolve()), selection_receipt_sha256=file_hash(selection),
                tokenization_performed=True, tokenization_receipt=str(receipt.resolve()),
                tokenization_receipt_sha256=file_hash(receipt), tokenized_path=item['output'],
                tokenized_rows=item['rows'], tokenized_tokens=item['tokens']))
    if len({e['name'] for e in entries}) != len(entries):
        raise ValueError('Duplicate local source')
    return dict(inherits='dfm12', additions=entries)
