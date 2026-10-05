"""Exact-document FinePDF publisher receipt adapter; no broader rights grant."""
import json
from pathlib import Path

from .finepdf_rights_subset import REPO, REVISION, grant, scope

NAMES = {
    'dfm13_wave3_finepdfs_' + language + '_exact_ccby_v1_' + task
    for language, tasks in (
        ('lt', ('denoising', 'paragraph_reordering', 'prefix_continuation', 'span_filling')),
        ('lv', ('denoising', 'prefix_continuation')),
    ) for task in tasks
}


def publication(entry, source, pins, api):
    require = api.require
    require(entry['name'] in NAMES, 'FinePDF scope not authorized')
    language = entry['name'].split('_')[3]
    folder = source.parent.parent
    require(Path(entry['export_manifest']).resolve() == folder / 'manifest.json',
            'FinePDF manifest path mismatch')
    export = api.read_json(entry['export_manifest'], pins, entry['export_manifest_sha256'])
    inventory = api.read_json(folder.parent / 'publication.json', pins)
    require(dict(path=folder.name, manifest_sha256=entry['export_manifest_sha256'])
            in inventory['packages'], 'FinePDF export absent from publication inventory')
    integrated = api.read_json(folder.parent / 'integrated.json', pins)
    matches = [r for r in integrated['records'] if r.get('name') == entry['name']]
    require(len(matches) == 1, 'FinePDF upload receipt missing or duplicated')
    receipt = matches[0]
    require(all(entry.get(k) == v for k, v in receipt.items()
                if k != 'tokenization_performed'), 'FinePDF upload receipt differs')
    require(export.get('repo_id') == REPO and export.get('revision') == REVISION
            and export.get('license') == 'cc-by-4.0'
            and export.get('database_license') == 'odc-by-1.0', 'FinePDF license/source mismatch')
    require(export.get('rights_receipt_sha256') == scope(language)[2],
            'FinePDF rights evidence not authorized')
    require(export.get('files') == entry.get('files'), 'FinePDF attachments changed')
    for relative, sha in export['files'].items():
        path = (folder / relative).resolve()
        require(path.is_relative_to(folder), 'FinePDF attachment escapes package')
        api.pin(path, pins, sha)
    api.pin(folder / 'rights-receipt.json', pins, scope(language)[2])
    with source.open() as handle:
        for line in handle:
            require(grant(json.loads(line), language) is not None,
                    'FinePDF row lacks exact-document rights')
    return receipt, export
