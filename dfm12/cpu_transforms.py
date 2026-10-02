"""Recover accepted baselines, then prepare reviewed multilingual candidates."""
from pathlib import Path
import time

from huggingface_hub import HfApi, snapshot_download

from . import catalog, prepare
from .io import load, lock, write_json


SELECTION = {
    'nl': ['wikiwijs', 'naturalis', 'pbl', 'european_parliament', 'dienst_publiek_en_communicatie'],
    'no': ['wikipedia-nob', 'wikipedia-nno'],
    'sv': ['wikipedia-sv', 'riksdagen-propositioner', 'riksdagen-protokoll'],
    'is': ['wikipedia', 'igc-journals-22-10', 'igc-law', 'igc-parla'],
    'fo': ['wikipedia', 'faroese-blark-small'],
    'pl': ['wikipedia', 'govpl', 'parliamentary', 'sejm_api'],
}


def main():
    root = Path('data/dfm12').resolve()
    cfg = catalog.config()
    inventory = load(root / 'sources.lock.json')['sources']
    with lock(root / '.cpu-transforms.lock'):
        baseline_path = root / 'baselines.json'
        if not baseline_path.exists():
            for task in cfg['tasks']:
                name = 'danish-dynaword-' + task
                repo = 'schneiderkamplab/' + name
                revision = HfApi().dataset_info(repo).sha
                print('BASELINE DOWNLOAD', repo, revision, flush=True)
                snapshot_download(repo, repo_type='dataset', revision=revision, max_workers=4,
                                  local_dir=root / 'baseline_sources' / name,
                                  allow_patterns=['data/*.parquet', 'data/*.jsonl', 'data/*.jsonl.gz', 'README.md'])
                write_json(root / 'baseline_revisions' / (name + '.json'), {'repo': repo, 'revision': revision})
            write_json(baseline_path, prepare.transformation_baseline(root / 'baseline_sources', cfg))
        renderer = prepare.Renderer(load('data/sampled_dfm11/metadata.json')['tokenizer_info'], cfg['max_seq_len'])
        for suffix, constituents in SELECTION.items():
            name = 'dynaword-' + suffix
            source = inventory[name]
            files = [f for f in source['files'] if f.split('/')[1] in constituents]
            if {f.split('/')[1] for f in files} != set(constituents):
                raise ValueError(f'Selection missing from pinned inventory: {name}')
            with lock(root / '.catalog.lock'):
                write_json(root / 'approvals' / (name + '.json'), {
                    'revision': source['revision'], 'files': files,
                    'evidence': '2026-09-24 pinned HF source-card review: reference, educational, scientific and parliamentary texts; '
                                'CC-BY/CC-BY-SA or official public-domain content. Exclude social media and bulk historical OCR. '
                                'Norwegian Wikipedia retains upstream attribution/share-alike obligations despite the collection CC0 label. '
                                'This approves candidate preparation only; independent row-level language/quality audit remains mandatory.',
                    'source_card': f"https://huggingface.co/datasets/{source['repo']}/blob/{source['revision']}/README.md"})
                if suffix == 'no':
                    approval_path = root / 'approvals' / (name + '.json')
                    approval = load(approval_path)
                    approval['language_by_file'] = {f: ('nb' if '/wikipedia-nob/' in f else 'nn') for f in files}
                    write_json(approval_path, approval)
            # The other CPU campaign owns the downloads. A snapshot receipt, not
            # mere file existence, is the completion signal.
            while True:
                status = load(root / 'cpu-preparation.json') if (root / 'cpu-preparation.json').exists() else {}
                state = status.get(name, {})
                if state.get('download') == 'complete':
                    break
                if state.get('error'):
                    raise RuntimeError(f'Download failed for {name}: {state}')
                print('WAIT DOWNLOAD', name, flush=True)
                time.sleep(60)
            print('TRANSFORM', name, flush=True)
            prepare.prepare_transforms(root, name, load(baseline_path), cfg, renderer)
            prepare.enqueue_candidates(root, name, cfg['model'], limit=100)
            print('TRANSFORM COMPLETE', name, flush=True)


if __name__ == '__main__':
    main()
