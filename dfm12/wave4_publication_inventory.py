"""Read-only source attribution inventory; never grants publication permission."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

from .io import write_json


def attribution(row):
    provenance = row.get('provenance', {})
    source = provenance.get('source') or {}
    if not source:
        if (provenance.get('contract_version') == 4 and provenance.get('family') == 'multiturn'
                and isinstance(provenance.get('slot'), int) and provenance['slot'] % 2 == 1):
            return dict(kind='synthetic_multiturn', basis='multilingual_tasks.spec_for odd-slot source-free branch'), []
        kind = 'synthetic_reference' if provenance.get('reference') else 'synthetic_scenario' if provenance.get('scenario') else 'unidentified'
        return dict(kind=kind), ([] if kind != 'unidentified' else ['missing_source_or_reference'])
    result = {k: source[k] for k in ('id', 'repo', 'source', 'revision', 'source_sha256',
        'document_url', 'source_document_id', 'offset', 'file', 'ordinal', 'file_sha256',
        'license', 'source_metadata') if k in source}
    result['kind'] = source.get('repo', source.get('source', 'unidentified'))
    gaps = []
    if result['kind'] == 'wikimedia/wikipedia':
        for key in ('document_url', 'source_document_id', 'revision', 'source_sha256'):
            if not source.get(key): gaps.append('missing_' + key)
    elif 'openhermes' in result['kind'].lower():
        metadata = source.get('source_metadata') or {}
        for key in ('openhermes_source', 'source_row_id'):
            if not metadata.get(key): gaps.append('missing_' + key)
        if not source.get('file_sha256'): gaps.append('missing_file_sha256')
    else:
        gaps.append('source_specific_attribution_review_needed')
    return result, gaps


def package(entry, root):
    folder = root / entry['name']
    folder.mkdir()
    sources, components, gaps, licenses = Counter(), Counter(), Counter(), Counter()
    count = 0
    digest = hashlib.sha256()
    with Path(entry['output']).open('rb') as src, (folder / 'ATTRIBUTION.jsonl').open('x') as out:
        for raw in src:
            digest.update(raw)
            row = json.loads(raw)
            source, missing = attribution(row)
            sources[source['kind']] += 1
            component = (source.get('source_metadata') or {}).get('openhermes_source')
            if component: components[component] += 1
            licenses[source.get('license', 'not_declared_per_row')] += 1
            gaps.update(missing)
            out.write(json.dumps(dict(id=row['id'], attribution=source, metadata_gaps=missing), ensure_ascii=False) + '\n')
            count += 1
    if digest.hexdigest() != entry['output_sha256'] or count != entry['rows']:
        raise ValueError('Sealed source drift: ' + entry['name'])
    result = dict(name=entry['name'], rows=count, sources=dict(sources),
        openhermes_components=dict(components), metadata_gaps=dict(gaps), license_labels=dict(licenses),
        output_sha256=entry['output_sha256'], publication_authorized=False,
        status='metadata_gaps' if gaps else 'attribution_inventory_complete_terms_review_pending')
    write_json(folder / 'inventory.json', result)
    (folder / 'PUBLICATION_NOTES.md').write_text(
        '# Publication preparation: ' + entry['name'] + '\n\n'
        'This supplement does not replace the sealed dataset card or authorize upload.\n'
        'ATTRIBUTION.jsonl binds each exported row ID to preserved source metadata; source text is not duplicated.\n'
        'Wikipedia document URLs identify attributed articles; the dataset revision is not an article revision.\n'
        'OpenHermes component and original row identifiers must remain visible; an aggregate source label is not a license grant.\n'
        'Synthetic references/scenarios do not imply a blanket license for the mixed dataset.\n'
        'Generated responses adapt source material; automated acceptance is not human review.\n'
        'Source-specific notices and license evidence must be resolved before separate publication authorization.\n')
    print(json.dumps(dict(name=entry['name'], rows=count, metadata_gaps=dict(gaps))), flush=True)
    return result


def run(registry, output):
    raw = registry.read_bytes()
    entries = json.loads(raw)['additions']
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'launch.json', dict(registry=str(registry), registry_sha256=hashlib.sha256(raw).hexdigest(),
        packages=len(entries), upload_authorized=False, workers=8))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda e: package(e, output), entries))
    write_json(output / 'complete.json', dict(packages=len(results), rows=sum(r['rows'] for r in results),
        results=results, upload_authorized=False, sealed_exports_modified=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.registry, args.output)
