"""Restore historical DynaWord HF inputs without reading local source payloads.

Only cache *receipts* are read as provenance. All training bytes come from HF
or this experiment's fresh downloads. Production trees remain untouched.
"""
import argparse
import fcntl
import json
from pathlib import Path
import time

from huggingface_hub import HfApi, snapshot_download

from scripts.queue_dfm_hf_rebuild import ROOT, load, write_json


HISTORICAL_REVISIONS = {
    'danish_dynaword': '7e97f781b6843de62827275d5facc0a8799df80c',
    'nemotron_agentic': '49e79a3be5ab8cf7511a12958b95cfd6408cd8db',
}


def repair(queue, name='danish_dynaword'):
    with (queue / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = load(queue / 'plan.json')
        acquisition = Path(plan['acquisition'])
        manifest_path = acquisition / 'dfm1-hf-inputs.json'
        manifest = load(manifest_path)
        source = next(s for s in manifest['hf_sources'] if s['name'] == name)
        info = HfApi().dataset_info(source['repo_id'], revision=HISTORICAL_REVISIONS[name], files_metadata=True)
        files = [dict(path=f.rfilename, size=f.size, blob_id=f.blob_id,
                      lfs_sha256=getattr(f.lfs, 'sha256', None))
                 for f in info.siblings if f.rfilename.endswith(('.parquet', '.jsonl'))
                 and (name == 'danish_dynaword' or f.rfilename in
                      ('data/interactive_agent.jsonl', 'data/search.jsonl', 'data/tool_calling.jsonl'))]
        if name == 'danish_dynaword':
            reference = {p.name for p in (ROOT / 'data/tokenized_mixed').iterdir()
                         if p.is_dir() and p.name.startswith('danish_dynaword__')}
            names = {'danish_dynaword__' + f['path'].replace('/', '__') for f in files}
            if names != reference or len(files) != 45:
                raise ValueError('Historical DynaWord file inventory does not match preserved DFM1')
        receipts = ROOT / 'data/downloads/datasets' / name / '.cache/huggingface/download'
        for f in files:
            lines = (receipts / (f['path'] + '.metadata')).read_text().splitlines()
            if lines[0] != info.sha or lines[1] not in (f['blob_id'], f['lfs_sha256']):
                raise ValueError(f'Historical receipt differs: {f["path"]}')
        destination = acquisition / 'downloads' / (name + '-' + info.sha)
        print(f'Downloading historical {name}: {len(files)} files, '
              f'{sum(f["size"] for f in files)} bytes', flush=True)
        snapshot_download(source['repo_id'], repo_type='dataset', revision=info.sha,
                          allow_patterns=[f['path'] for f in files], local_dir=destination,
                          cache_dir=acquisition / 'hf-cache', max_workers=8)
        for f in files:
            if (destination / f['path']).stat().st_size != f['size']:
                raise ValueError(f'Download incomplete: {f["path"]}')
        work = queue / 'dfm1'
        archive = work / ('superseded-' + str(time.time_ns()))
        archive.mkdir()
        write_json(archive / 'acquisition-manifest.json', manifest)
        write_json(archive / 'plan.json', plan)
        # Preserve failed/partial outputs for diagnosis, outside tokenizer traversal.
        for tree in ('inputs', 'filtered', 'converted'):
            stale = work / tree / name
            if stale.exists():
                stale.rename(archive / tree)
        source.update(revision=info.sha, resolved_revision=info.sha,
                      revision_basis='historical HF cache receipts for all selected files',
                      files=files, allow_patterns=[f['path'] for f in files],
                      download_path=str(destination), status='downloaded')
        write_json(manifest_path, manifest)
        row = plan['rows'][0]
        row.update(status='pending', phase=None, completed_stages=[],
                   stages=['prepare', 'filter', 'convert', 'split_swe', 'layout',
                           'tokenize', 'sample', 'compare'])
        row.pop('error', None)
        plan['tokenizer_workers'] = 32
        write_json(queue / 'plan.json', plan)
        print(f'Historical {name} restored; DFM1 queue reset for strict incremental conversion.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue', type=Path, required=True)
    parser.add_argument('--source', choices=HISTORICAL_REVISIONS, default='danish_dynaword')
    args = parser.parse_args()
    repair(args.queue.resolve(), args.source)
