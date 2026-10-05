"""Read-only Hub inventory comparison against DFM12 source pins."""
import json
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download
from dfm12.io import write_json

ROOT = Path('docs/reports/dyna-source-scan-20261005')


def files(info):
    return {s.rfilename: dict(size=s.size, blob_id=s.blob_id,
            sha256=getattr(s.lfs, 'sha256', None)) for s in info.siblings
            if s.rfilename.endswith(('.parquet', '.jsonl', '.jsonl.gz')) and
            not s.rfilename.startswith(('annotations/', 'meta/'))}


def main():
    api = HfApi()
    locked = json.loads(Path('data/dfm12/sources.lock.json').read_text())['sources']
    baseline = {s['repo']: s for s in locked.values() if 'dyna' in s['repo'] and '/dala-' not in s['repo']}
    discovered = {d.id: d for query in ('dynaword', 'dyna-instruct', 'dynainstruct')
                  for d in api.list_datasets(search=query)}
    results = []
    for repo in sorted(discovered):
        print('SCAN', repo, flush=True)
        info = api.dataset_info(repo, files_metadata=True)
        current = files(info)
        pin = baseline.get(repo)
        old = files(api.dataset_info(repo, revision=pin['revision'], files_metadata=True)) if pin else {}
        item = dict(repo=repo, revision=info.sha, modified=str(info.last_modified),
                    baseline_revision=pin['revision'] if pin else None,
                    current_files=current, baseline_files=old,
                    added=sorted(set(current)-set(old)) if pin else [],
                    removed=sorted(set(old)-set(current)) if pin else [],
                    changed=sorted(p for p in current.keys() & old.keys() if current[p] != old[p]),
                    baseline_selected_files=pin.get('files', []) if pin else [],
                    card=info.card_data.to_dict() if info.card_data else {})
        folder = ROOT / repo.replace('/', '__')
        try:
            card = hf_hub_download(repo, 'README.md', repo_type='dataset', revision=info.sha)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'README.upstream.md').write_bytes(Path(card).read_bytes())
        except Exception as exc:
            item['card_error'] = str(exc)
        if pin and info.sha != pin['revision']:
            commits = []
            for c in api.list_repo_commits(repo, repo_type='dataset'):
                if c.commit_id == pin['revision']:
                    break
                commits.append(dict(id=c.commit_id, date=str(c.created_at), title=c.title))
            item['commits_since_pin'] = commits
        results.append(item)
        write_json(ROOT / 'inventory.json', results)
        print(json.dumps({k:item[k] for k in ('repo','baseline_revision','added','changed','removed')}), flush=True)
    # Danish has no complete local revision pin here: use an explicitly labelled
    # pre-DFM12 temporal baseline, not a claim about exact inherited coverage.
    repo = 'danish-foundation-models/danish-dynaword'
    item = next(e for e in results if e['repo'] == repo)
    revision = 'c2f51be06848df26b5aad71cafeec1bc6064b1cc'
    old = files(api.dataset_info(repo, revision=revision, files_metadata=True))
    item['temporal_baseline'] = dict(revision=revision, basis='2026-09-01; not exact local training pin',
        added=sorted(set(item['current_files'])-set(old)),
        changed=sorted(p for p in item['current_files'].keys() & old.keys() if item['current_files'][p] != old[p]))
    write_json(ROOT / 'inventory.json', results)
    for item in results:
        repo = item['repo']
        if repo not in ('SlayerLab/polish-dynaword', 'danish-foundation-models/danish-dynaword',
                        'danish-foundation-models/faroese-dynaword'):
            continue
        names = {Path(p).parent.name for p in item['added'] if p.endswith('.parquet')}
        if repo.endswith('/danish-dynaword'):
            names = {'logir', 'adl'}
        available = api.list_repo_files(repo, repo_type='dataset', revision=item['revision'])
        wanted = [p for p in available if p.startswith('data/') and len(Path(p).parts) > 2
                  and Path(p).parts[1] in names and (p.endswith('.md') or p.endswith('.sample.jsonl'))]
        folder = ROOT / repo.replace('/', '__') / 'source_review'
        for name in wanted:
            src = hf_hub_download(repo, name, repo_type='dataset', revision=item['revision'])
            dest = folder / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(Path(src).read_bytes())


if __name__ == '__main__':
    main()
