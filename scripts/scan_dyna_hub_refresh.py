"""Read-only Dyna Hub refresh against saved October inventories; no corpus edits."""
import argparse
import json
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

from scripts.scan_dyna_source_updates import files

REVIEW = {
    'danish-foundation-models/swedish-dynaword': ['rd-sou', 'rd-ds', 'rd-prop', 'swedish-pd',
        'sweachum', 'sweacsam', 'attasidor', 'lb-restricted', 'wikisource', 'gutenberg'],
    'danish-foundation-models/norwegian-dynaword': ['nva-cc-by', 'nva-cc-by-sa', 'nva-cc0',
        'wiktionary-nob', 'hoyesterett'],
    'danish-foundation-models/danish-dynaword': ['comparia', 'trykkefrihedens_skrifter',
        'enevaeldens_nyheder', 'cellar'],
}


def save_review_cards(output):
    inventory = {x['repo']: x for x in json.loads((output/'inventory.json').read_text())}
    for repo, names in REVIEW.items():
        for name in names:
            path = hf_hub_download(repo, f'data/{name}/{name}.md', repo_type='dataset',
                                   revision=inventory[repo]['revision'])
            target = output/repo.replace('/', '__')/'source_cards'
            target.mkdir(exist_ok=True)
            (target/(name+'.md')).write_bytes(Path(path).read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('docs/reports/dyna-source-scan-20261027'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    prior = {x['repo']: (x['revision'], x['current_files'], 'October 5 scan')
             for x in json.loads(Path('docs/reports/dyna-source-scan-20261005/inventory.json').read_text())}
    for x in json.loads(Path('data/dfm15/organization-inventory.json').read_text()):
        prior[x['repo_id']] = (x['revision'], {f['path']: dict(sha256=f['sha256'], size=f['bytes'])
                                             for f in x['files']}, 'DFM15 organization scan')
    api = HfApi()
    ids = set()
    for query in ('dynaword', 'dyna-instruct', 'dynainstruct', 'dyna_instruct'):
        ids.update(x.id for x in api.list_datasets(search=query))
    rows = []
    for repo in sorted(ids):
        print('SCAN', repo, flush=True)
        try:
            info = api.dataset_info(repo, files_metadata=True)
            current = files(info)
            old_revision, old, basis = prior.get(repo, (None, {}, None))
            old = {p:v for p,v in old.items() if not p.startswith(('annotations/', 'meta/'))}
            # Older organization inventories omit Git blob IDs for small files.
            # Equal commits prove equality; absent hashes do not prove changes.
            if old_revision == info.sha:
                old = current
            elif any(not v.get('sha256') and not v.get('blob_id') for v in old.values()):
                old = files(api.dataset_info(repo, revision=old_revision, files_metadata=True))
            changed = [p for p in current.keys() & old.keys()
                       if (current[p]['sha256'] or current[p]['blob_id']) != (old[p].get('sha256') or old[p].get('blob_id'))]
            row = dict(repo=repo, revision=info.sha, modified=str(info.last_modified),
                       baseline_revision=old_revision, baseline_basis=basis, files=current,
                       added=sorted(current.keys()-old.keys()), removed=sorted(old.keys()-current.keys()),
                       changed=sorted(changed), card=info.card_data.to_dict() if info.card_data else {})
            folder = args.output/repo.replace('/', '__')
            folder.mkdir(exist_ok=True)
            for name in ('README.md', 'CHANGELOG.md'):
                try:
                    path = hf_hub_download(repo, name, repo_type='dataset', revision=info.sha)
                    (folder/name).write_bytes(Path(path).read_bytes())
                except Exception as exc:
                    row[name+'_error'] = type(exc).__name__
        except Exception as exc:
            row = dict(repo=repo, error=type(exc).__name__ + ': ' + str(exc))
        rows.append(row)
        (args.output/'inventory.json').write_text(json.dumps(rows, indent=2)+'\n')
        print(json.dumps({k:v for k,v in row.items() if k not in ('files', 'card')}), flush=True)
    save_review_cards(args.output)


if __name__ == '__main__':
    main()
