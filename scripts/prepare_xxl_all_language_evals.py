"""Recover the exact pinned 34-language heldouts from their published HF files."""
import copy
import argparse
import gzip
import hashlib
import heapq
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
from huggingface_hub import HfApi, hf_hub_download
from dfm12.io import digest, file_hash, load, write_json
from dfm12.dala_compact_finalize import accepted, canonical

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data/dfm14/evaluation/all50'
GROUPS = (
    ('dfm13_dala_v2_existing21_20261006', 'dfm_evals_dfm13_dala_v2_existing21_20261006'),
    ('dfm13_dala_heldout_20261006', 'dfm_evals_dfm13_multilingual_20261006'),
)


def recover(item):
    language, entry = item
    source_language = 'pt-PT' if language == 'pt_pt' else language
    repo = f'schneiderkamplab/dfm13-dala-v2-{source_language}-compact'
    revision = HfApi().dataset_info(repo).sha
    selected, pins = {}, []
    for kind in ('acceptability', 'correction'):
        filename = f'data/{kind}/test_representative.jsonl.gz'
        path = Path(hf_hub_download(repo, filename, repo_type='dataset', revision=revision))
        expected = next(p['sha256'] for p in entry['input_pins'] if p['path'].endswith(filename))
        if file_hash(path) != expected:
            raise ValueError(f'Published heldout differs from pinned input: {repo}/{filename}')
        pins.append({'path':str(path), 'sha256':expected})
        heap, seen = [], set()
        with gzip.open(path, 'rt') as stream:
            import json
            for line in stream:
                row = json.loads(line)
                if row['variant'] != 'corrupted':
                    continue
                original, audit = row['provenance'], row['compact_audit']
                record = canonical(original, source_language, 'pair')
                if (row['split'] != 'test' or row['view'] != 'representative'
                        or not accepted(record, audit['decision'], 'done')
                        or audit['source_row_sha256'] != digest(original)):
                    raise ValueError('Invalid heldout audit binding')
                key = record['id']
                if key in seen:
                    raise ValueError('Duplicate heldout pair')
                seen.add(key)
                rank = int(hashlib.sha256(('4242:'+key).encode()).hexdigest(), 16)
                value = (-rank, key, row)
                if len(heap) < 1000:
                    heapq.heappush(heap, value)
                elif rank < -heap[0][0]:
                    heapq.heapreplace(heap, value)
        selected[kind] = {key:row for _,key,row in heap}
    if set(selected['acceptability']) != set(selected['correction']):
        raise ValueError('LA/GEC selections differ')
    keys = sorted(selected['acceptability'], key=lambda k:hashlib.sha256(('4242:'+k).encode()).hexdigest())
    rows = []
    for key in keys:
        row = selected['acceptability'][key]
        rows.append(dict(id=key, original=row['provenance']['original'],
                         corrupted=row['provenance']['corrupted'], provenance=row['provenance'],
                         compact_audit=row['compact_audit'], publication_pool=row['publication_pool'],
                         source_row_hashes={k:digest(v[key]) for k,v in selected.items()}))
    path = OUT/language/'pairs.json'
    write_json(path, rows)
    if file_hash(path) != entry['selected']['sha256']:
        raise ValueError('Reconstructed selection is not byte-identical: '+language)
    local = copy.deepcopy(entry)
    local['selected']['path'] = str(path)
    local['input_pins'] = pins
    local['recovery_evidence'] = dict(repo=repo, revision=revision,
        original_input_pins=entry['input_pins'],
        policy='Exact original selected-file SHA and both published test-file SHAs verified; remote build receipts retained as provenance, not local runtime pins.')
    print('Verified byte-identical heldout', language, len(rows), flush=True)
    return language, local


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    tasks = []
    for manifest_name, suite_name in GROUPS:
        local_manifest = OUT/f'{manifest_name}.json'
        if not args.verify_only:
            manifest = load(ROOT/'config'/f'{manifest_name}.json')
            with ThreadPoolExecutor(max_workers=4) as pool:
                manifest['languages'] = dict(pool.map(recover, manifest['languages'].items()))
            write_json(local_manifest, manifest)
        else:
            manifest = load(local_manifest)
            original = load(ROOT/'config'/f'{manifest_name}.json')
            for language, entry in manifest['languages'].items():
                assert file_hash(entry['selected']['path']) == original['languages'][language]['selected']['sha256']
        suite = yaml.safe_load((ROOT/'config'/f'{suite_name}.yaml').read_text())
        for group in suite['sets'].values():
            for task in group['tasks']:
                task['name'] = task['name'].replace('/work/dfm/HRM-Text', str(ROOT))
                task['args'] = ['manifest='+str(local_manifest) if s.startswith('manifest=') else s
                                for s in task['args']]
        local_suite = OUT/f'{suite_name}.yaml'
        local_suite.write_text(yaml.safe_dump(suite, sort_keys=False))
        registry_name = manifest_name.replace('_20261006', '_registry_20261006')
        for entry in load(ROOT/'config'/f'{registry_name}.json'):
            tasks.append({**entry, 'config':str(local_suite)})
    # Exercise all task constructors before publishing readiness.
    from dfm_evals.tasks.dala_dfm13_heldout import make
    for manifest_name, _ in GROUPS:
        path = OUT/f'{manifest_name}.json'
        manifest = load(path)
        for language in manifest['languages']:
            for kind, budget in [('acceptability',32), ('correction',512)]:
                seen = set()
                for shard in range(4):
                    task = make(language, kind, str(path), 4, shard, budget,
                                allowed_languages=tuple(manifest['languages']))
                    ids = {s.id for s in task.dataset}
                    assert len(ids) == 500 and not seen & ids
                    seen.update(ids)
                assert len(seen) == 2000
    write_json(OUT/'ready.json', {'tasks':tasks, 'languages':34, 'samples_per_task':2000,
                                'exact_original_selections':True})


if __name__ == '__main__':
    main()
