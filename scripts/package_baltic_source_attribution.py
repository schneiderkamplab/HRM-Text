"""External Baltic publication packets; no sealed release or registry mutations."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sqlite3

from dfm12.io import atomic, digest, file_hash, load, lock, write_json

RELEASE = Path('data/dfm13/baltic-finished-release-20261004-v1')
OUTPUT = Path('exports_dfm13/baltic-source-attribution-20261004-v1')
HERMES = 'schneiderkamplab/dfm8-openhermes-en'
LOCAL = Path('data/dfm13/baltic/local-sources.json')
EURO = Path('docs/reports/baltic-source-rights-20261003/evidence-europarl')


def classify(source, local):
    if not source:
        return 'synthetic_scenario', 'No external source supplied', True
    name = source.get('source', source.get('repo'))
    if name == HERMES:
        return name, 'User-authorized inherited OpenHermes; upstream constituent terms retained, no blanket relicensing', True
    if name not in local or source.get('source_sha256') != local[name]['sha256']:
        raise ValueError('Unbound or unknown source')
    if not source.get('document_url') or not source.get('source_document_id'):
        raise ValueError('Missing document attribution')
    return name, local[name]['license'], not name.startswith('Europarl_')


def verify(root):
    root = Path(root)
    manifest = load(root/'publication-manifest.json')
    for relative, sha in manifest['files'].items():
        p = (root/relative).resolve()
        if not p.is_relative_to(root.resolve()) or file_hash(p) != sha:
            raise ValueError('Publication packet hash/path mismatch')
    if file_hash(root/'data/train.jsonl') != manifest['original_output_sha256']:
        raise ValueError('Sealed payload changed')
    count = 0
    with (root/'data/train.jsonl').open() as data, (root/'attribution.jsonl').open() as attrs:
        for line in data:
            row = json.loads(line); attr = json.loads(next(attrs))
            if attr['row_id'] != row['id'] or attr['row_sha256'] != digest(row):
                raise ValueError('Attribution row binding mismatch')
            count += 1
        if next(attrs, None) is not None or count != manifest['rows']:
            raise ValueError('Attribution coverage mismatch')
    return manifest


def prepare(output=OUTPUT):
    output = Path(output)
    with lock(str(output)+'.lock'):
        if output.exists():
            raise ValueError('Fresh external root required')
        local = {x['name']: x for x in load(LOCAL)}
        for item in local.values():
            if file_hash(item['path']) != item['sha256']:
                raise ValueError('Document source hash mismatch')
        for name, sha in load(EURO/'receipt.json')['files'].items():
            if file_hash(EURO/name) != sha:
                raise ValueError('Europarl evidence changed')
        seeds = sqlite3.connect('file:data/dfm13/baltic/seeds/seeds.sqlite?mode=ro', uri=True)
        results = []; checked_files = {}
        pins = {str(RELEASE/n):file_hash(RELEASE/n) for n in ('registry.json','complete.json','source-proof.json')}
        output.mkdir(parents=True)
        for entry in load(RELEASE/'registry.json')['additions']:
            family = entry['name'].split('_',4)[4]
            if family in ('math_code','tool_dialogue'):
                continue
            language = entry['name'].split('_')[3]
            repo = 'schneiderkamplab/dfm13-multilingual-'+family.replace('_','-')+'-'+language
            folder = output/repo.split('/')[1]; (folder/'data').mkdir(parents=True)
            source_path = Path(entry['output'])
            if file_hash(source_path) != entry['output_sha256']:
                raise ValueError('Release output changed')
            shutil.copyfile(source_path, folder/'data/train.jsonl')
            shutil.copyfile(entry['export_manifest'], folder/'ORIGINAL_MANIFEST.json')
            shutil.copyfile(LOCAL, folder/'SOURCE_INVENTORY.json')
            shutil.copyfile('data/dfm11_source_cache/dfm8-openhermes-en/README.md', folder/'OPENHERMES_SOURCE_README.md')
            shutil.copytree(EURO, folder/'evidence-europarl')
            counts = Counter(); held = 0; n = 0
            with atomic(folder/'attribution.jsonl') as attrs, source_path.open() as data:
                for line in data:
                    row = json.loads(line); source = row.get('provenance',{}).get('source')
                    name, terms, ready = classify(source, local)
                    if source:
                        pool = 'openhermes' if name == HERMES else language
                        found = seeds.execute('SELECT payload FROM seeds WHERE pool=? AND source_id=?', (pool,source['id'])).fetchone()
                        if found is None:
                            raise ValueError('Source absent from original seed pool')
                        payload = json.loads(found[0])
                        if any(payload.get(k) != v for k,v in source.items() if k not in ('generation_and_review_required',)):
                            raise ValueError('Source differs from original seed')
                        if name == HERMES:
                            path = source['file']; expected = source['file_sha256']
                            if path not in checked_files: checked_files[path] = file_hash(path)
                            if checked_files[path] != expected: raise ValueError('OpenHermes source file drift')
                    counts[name] += 1; held += not ready; n += 1
                    attr = dict(row_id=row['id'], row_sha256=digest(row), source=name,
                        source_binding=source, terms=terms, publication_evidence_ready=ready,
                        changes='Gemma-generated translation/adaptation or grounded task; not an original source statement',
                        attribution=('Wikipedia contributors; article/history URL retained' if name.startswith('Wikipedia_') else
                                     'European Parliament via OPUS Europarl v8; sitting identity retained; official per-sitting link unverified' if name.startswith('Europarl_') else
                                     'Inherited DFM8 OpenHermes; source row ID and constituent label retained'))
                    attrs.write(json.dumps(attr,ensure_ascii=False)+'\n')
            if n != entry['rows']: raise ValueError('Release row count mismatch')
            (folder/'README.md').write_text(f'''---
language: [{language}]
task_categories: [text-generation]
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train.jsonl
---
# {repo.split('/')[-1]}

{n} full conversations; {entry['training_targets']} assistant targets. Repeat1.
Payload bytes are unchanged from the accepted Baltic release. Native Gemma4,
all assistant targets and full history/tools preserved. Generated by Gemma4
26B and independently model-audited; not certified gold or native-speaker review.

## Source attribution and terms
Every row has a hash-bound attribution.jsonl entry and original provenance.
Wikipedia excerpts: Wikipedia contributors, CC-BY-SA-3.0/GFDL as recorded by
the pinned source inventory. Article URLs identify contributor history; retain
attribution, modification notice and applicable ShareAlike terms. Terms:
https://creativecommons.org/licenses/by-sa/3.0/ and https://www.gnu.org/licenses/fdl-1.3.html .
OpenHermes: inherited DFM8 cleaned/repaired source, original row and constituent
labels retained. Explicit user inclusion/publication authorization2026-10-04;
the local DFM8 card does not declare a blanket license. No invented license
or independent rights-holder grant is asserted. See OPENHERMES_SOURCE_README.md.
Europarl: original European Parliament terms, not CC or public domain. Captured
notice and OPUS attribution are under evidence-europarl/. Archive/sitting IDs
are preserved; verified official sitting links and adaptation scope remain
unresolved in the existing rights review. Original-source statements must not
be attributed to the generated answers. No Parliament endorsement.

## Publication state
Source counts: {json.dumps(dict(counts),sort_keys=True)}.
Europarl unresolved rows: {held}. Whole-package upload-ready: {held == 0}.
No rows were removed, rewritten or silently relicensed to make a package ready.
No blanket package license is asserted. This packet adds metadata only and
does not modify sealed release manifests, token arrays or integration pins.
''')
            files = {str(p.relative_to(folder)):file_hash(p) for p in folder.rglob('*') if p.is_file()}
            manifest = dict(name=entry['name'],hf_repo_id=repo,rows=n,training_targets=entry['training_targets'],
                original_output_sha256=entry['output_sha256'],original_export_manifest_sha256=entry['export_manifest_sha256'],
                source_counts=dict(counts), unresolved_europarl_rows=held, upload_ready=held==0,
                uploaded=False, integration_changed=False, files=files)
            if files['ORIGINAL_MANIFEST.json'] != entry['export_manifest_sha256']: raise ValueError('Original manifest drift')
            write_json(folder/'publication-manifest.json',manifest); verify(folder)
            results.append(dict(name=entry['name'],path=str(folder),hf_repo_id=repo,rows=n,
                source_counts=dict(counts),unresolved_europarl_rows=held,upload_ready=held==0,
                manifest_sha256=file_hash(folder/'publication-manifest.json')))
        seeds.close()
        for path,sha in pins.items():
            if file_hash(path)!=sha: raise ValueError('Sealed release changed during packaging')
        receipt = dict(packages=results,source_pins=pins,openhermes_input_pins=checked_files,
            source_inventory_sha256=file_hash(LOCAL),sealed_release_unchanged=True,uploaded=False,
            authorization='User2026-10-04: OpenHermes allowed; DynaWord/DynaInstruct licenses fine. Not an invented Europarl grant.')
        write_json(output/'handoff.json',receipt)
        return receipt


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args();print(json.dumps(prepare(args.output),indent=2))
