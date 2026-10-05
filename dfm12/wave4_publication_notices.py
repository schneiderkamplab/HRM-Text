"""Prepare source notices and publication cards without uploading or changing exports."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import requests

from .io import write_json, file_hash

OH = 'https://huggingface.co/datasets/teknium/OpenHermes-2.5'
REPAIRED = 'https://huggingface.co/datasets/schneiderkamplab/dfm8-openhermes-en'
WIKI = 'https://huggingface.co/datasets/wikimedia/wikipedia'
TERMS = 'https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use/en'
CC = 'https://creativecommons.org/licenses/by-sa/4.0/'
CC3 = 'https://creativecommons.org/licenses/by-sa/3.0/legalcode'


def notice(item):
    sources = item['sources']
    text = ['# Source attribution and modifications', '',
        'The per-row ATTRIBUTION.jsonl maps exported conversation IDs to source identities. '
        'Original source metadata also remains in data/train.jsonl. Generated dialogue is a '
        'model-produced adaptation, not an original source quotation or a human-certified translation.']
    if 'wikimedia/wikipedia' in sources:
        text += ['', '## Wikipedia text',
            f'Source: [Wikimedia Wikipedia dataset]({WIKI}), credited to the contributors '
            'of each article identified by document_url in ATTRIBUTION.jsonl. Article links '
            'provide access to contributor histories. Source snapshot revisions and hashes '
            'are preserved; these are dataset revisions, not exact article revision IDs.',
            f'The pinned dataset card identifies original text under [CC BY-SA 3.0]({CC3}) '
            '(and GFDL where applicable); retained source text keeps its original notice. '
            f'Our adapted Wikipedia text is distributed under [CC BY-SA 4.0]({CC}), '
            'the later-version adaptation option in CC BY-SA 3.0 section 4(b). '
            'This notice applies to that material, not an assertion '
            'of exclusive ownership of the entire mixed package. See '
            f'[Wikimedia reuse terms, section 7]({TERMS}#7._Licensing_of_Content). '
            'Retained source passages, references and notices are not stripped. '
            'Changes include excerpt selection, generated questions/answers, summaries, '
            'rewrites and multi-turn adaptation; there is no Wikimedia endorsement.']
    if 'schneiderkamplab/dfm8-openhermes-en' in sources:
        text += ['', '## OpenHermes lineage',
            f'Teknium, OpenHermes 2.5 (2023), [upstream compilation]({OH}), via '
            f'[DFM8 repaired English OpenHermes]({REPAIRED}). This release uses the '
            'existing user-approved OpenHermes synthetic-source policy. Approval is '
            'recorded as project policy, not represented as an upstream SPDX license grant.',
            'Original source row IDs, cached-file hashes and available component labels '
            'are preserved in ATTRIBUTION.jsonl. Empty component labels remain unknown '
            'within the identified upstream compilation; no component is guessed and no '
            'row is excluded solely for that omission. Source-specific terms/notices remain '
            'applicable. The pinned upstream card credits component creators; no blanket '
            'permissive license is invented for this mixed compilation.',
            'DFM8 repair and subsequent target-language generation modify the upstream '
            'conversations. The local source file hashes bind actual inputs; current '
            'upstream card snapshots are documentation evidence, not the source-data revision.']
    if any(k.startswith('synthetic_') for k in sources):
        text += ['', '## Synthetic task specifications',
            'Math/code references and fictional tool scenarios are generated task '
            'specifications, not claims of real transactions. Odd-slot source-free '
            'multi-turn tasks are explicitly identified as synthetic. No external '
            'source identity is fabricated for these rows.']
    text += ['', '## Audit limitations',
        'Acceptance uses existing model reviews and deterministic checks. Empty-rationale '
        'technical recovery preserves the original complete keep verdict and does not '
        'invent a rationale. These are not human/native-language certification claims.']
    return '\n\n'.join(text) + '\n'


def snapshot(url, path):
    with requests.get(url, timeout=60, stream=True) as response:
        response.raise_for_status()
        payload = bytearray()
        for part in response.iter_content(65536):
            payload.extend(part)
            if len(payload) > 2000000: raise ValueError('Unexpectedly large evidence document')
    path.write_bytes(payload)
    return dict(url=url, path=str(path), sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))


def run(inventory, registry, output):
    items = json.loads((inventory/'complete.json').read_text())['results']
    entries = {e['name']: e for e in json.loads(registry.read_text())['additions']}
    assert len(items) == len(entries) == 66
    output.mkdir(parents=True, exist_ok=False)
    evidence = output/'evidence'; evidence.mkdir()
    docs = []
    for repo, name, revision in [('teknium/OpenHermes-2.5', 'openhermes', None),
            ('schneiderkamplab/dfm8-openhermes-en', 'repaired-openhermes', '9a461da6fa1e2792f9ba6430861804443b82d3db'),
            ('wikimedia/wikipedia', 'wikipedia', 'b04c8d1ceb2f5cd4588862100d08de323dccfbaa')]:
        if revision is None:
            response = requests.get('https://huggingface.co/api/datasets/'+repo, timeout=60)
            response.raise_for_status(); revision=response.json()['sha']
        docs.append(snapshot(f'https://huggingface.co/datasets/{repo}/resolve/{revision}/README.md', evidence/(name+'.md')))
    try:
        docs.append(snapshot(TERMS, evidence/'wikimedia-terms.html'))
    except requests.HTTPError as error:
        if error.response.status_code != 403: raise
        record=dict(url=TERMS,http_snapshot_status=403,raw_snapshot_saved=False,
            separately_browser_verified_sections=['7.2 attribution', '7.7 reuse', '7.8 modifications'],
            checked_date='2026-10-04',limitation='Direct HTTP denied; browser-visible official source inspected, not a saved full terms snapshot')
        write_json(evidence/'wikimedia-terms-access.json',record)
        docs.append(dict(**record,path=str(evidence/'wikimedia-terms-access.json'),
            sha256=file_hash(evidence/'wikimedia-terms-access.json')))
    docs.append(snapshot(CC, evidence/'cc-by-sa-4.0.html'))
    docs.append(snapshot(CC3, evidence/'cc-by-sa-3.0.html'))
    write_json(evidence/'manifest.json', dict(documents=docs))
    packages=[]
    for item in items:
        e=entries[item['name']]
        assert e['output_sha256']==item['output_sha256']
        gaps=set(item['metadata_gaps'])-{'missing_openhermes_source'}
        if gaps: raise ValueError('Unresolved provenance: '+str(gaps))
        folder=output/item['name']; folder.mkdir()
        shutil.copyfile(inventory/item['name']/'ATTRIBUTION.jsonl',folder/'ATTRIBUTION.jsonl')
        (folder/'NOTICE.md').write_text(notice(item))
        card=Path(e['export_manifest']).parent/'README.md'
        shutil.copyfile(card.parent/'SOURCE_INVENTORY.json',folder/'SOURCE_INVENTORY.json')
        (folder/'README.md').write_text(card.read_text()+'\n## Attribution and source policy\n\n'
            'See [NOTICE.md](NOTICE.md) and the per-conversation [ATTRIBUTION.jsonl](ATTRIBUTION.jsonl). '
            'Unknown OpenHermes component labels are disclosed under the identified upstream '
            'compilation and approved synthetic-source policy, not silently reassigned. '
            'This prepared card does not itself record an HF upload.\n')
        pins={str(p):file_hash(p) for p in folder.iterdir()}
        packages.append(dict(name=item['name'],rows=item['rows'],pins=pins,
            source_export_sha256=e['output_sha256'],unknown_component_rows=item['metadata_gaps'].get('missing_openhermes_source',0)))
    write_json(output/'complete.json',dict(packages=packages,package_count=66,rows=sum(i['rows'] for i in items),
        evidence_manifest_sha256=file_hash(evidence/'manifest.json'),inventory_sha256=file_hash(inventory/'complete.json'),
        registry_sha256=file_hash(registry),policy='user-approved OpenHermes synthetic source; preserve unknown components',
        metadata_exclusions=0,uploaded=False,upload_authorized=False,sealed_exports_modified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('inventory','registry','output'):p.add_argument('--'+arg,type=Path,required=True)
    a=p.parse_args();run(a.inventory,a.registry,a.output)
