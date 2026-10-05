"""Restartable fourth-wave CPU discovery, downloads and parallel audit preparation."""
import argparse
from contextlib import contextmanager
import time
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from pathlib import Path

from . import opus
from .baltic_audit import preflight, MODEL
from .baltic_opus import configuration as baltic_configuration, prepare_one
from .io import digest, file_hash, load, lock, rows, write_json
from .jobs import Queue, audit_payload

LANGUAGES = dict(sq='Albanian', be='Belarusian', bs='Bosnian', bg='Bulgarian',
    hr='Croatian', hu='Hungarian', lb='Luxembourgish', sr='Serbian', sk='Slovak',
    sl='Slovenian', fa='Persian')
SOURCES = {
    'alban-labs/Kapibara': ['sq'],
    'administraktor/hrvatski-dataset-v2': ['hr'],
    'jvalline/LuxIT_wiki_subset': ['lb'],
    'CohereLabs/aya_dataset': ['sq', 'hu', 'sr', 'fa'],
    'utter-project/EuroBlocks-SFT-2512': ['bg', 'hr', 'hu', 'sk', 'sl'],
    'ParsiAI/FarsInstruct': ['fa'],
    'MatinaAI/matina_persian_text_corpus': ['fa'],
    'Targoman/TLPC': ['fa'],
}


@contextmanager
def queue_lock(path):
    deadline = time.monotonic()+1800
    while True:
        manager = lock(path)
        try:
            manager.__enter__()
            break
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise TimeoutError('Audit enqueue lock remained busy')
            time.sleep(1)
    try:
        yield
    finally:
        manager.__exit__(None, None, None)


def configuration():
    cfg = baltic_configuration()
    cfg['languages'].update(LANGUAGES)
    requested = [list(p) for p in combinations(sorted(cfg['languages']), 2)
                 if set(p) & LANGUAGES.keys()]
    legs = [sorted(['en', lang]) for lang in cfg['languages'] if lang != 'en']
    cfg.update(requested_pairs=requested,
               opus_pairs=sorted({tuple(p) for p in requested + legs}))
    cfg['pair_budgets'] = {'-'.join(p): dict(
        fraction=cfg['english_translation_fraction'] if 'en' in p else cfg['other_translation_fraction'],
        directions='combined', routes='direct and pivot combined',
        shortfall='report; no repeat inflation') for p in requested}
    return cfg


def downloads(root):
    from huggingface_hub import HfApi, snapshot_download
    api = HfApi()
    for repo, languages in SOURCES.items():
        if repo in ('MatinaAI/matina_persian_text_corpus', 'Targoman/TLPC'):
            print('BOUNDED PLAN REQUIRED', repo, 'dfm12.wave4_persian_local; no whole-repository retry', flush=True)
            continue
        dest = root/'downloads'/repo.replace('/', '--')
        receipt = dest/'wave4-download.json'
        if receipt.exists() and load(receipt).get('status') == 'downloaded':
            continue
        try:
            info = api.dataset_info(repo)
            pin = dict(repo=repo, revision=info.sha, languages=languages,
                       license=(info.card_data.to_dict() if info.card_data else {}).get('license'),
                       status='downloading', training_ready=False)
            write_json(receipt, pin)
            snapshot_download(repo, repo_type='dataset', revision=info.sha,
                local_dir=dest, max_workers=4,
                allow_patterns=['*.parquet', '*.jsonl', '*.jsonl.gz', '*.json',
                                '*.csv', '*.txt', '*.txt.gz', '*.md', '*LICENSE*', '*.zip'])
            pin['status'] = 'downloaded'
            write_json(receipt, pin)
            print('DOWNLOADED', repo, flush=True)
        except Exception as exc:
            write_json(receipt, dict(repo=repo, status='blocked', error=str(exc),
                                    training_ready=False))
            print('DOWNLOAD BLOCKED', repo, str(exc), flush=True)


def wikipedia(root):
    from huggingface_hub import HfApi, snapshot_download
    repo = 'wikimedia/wikipedia'
    info = HfApi().dataset_info(repo)
    for language in LANGUAGES:
        dest = root/'downloads'/('wikipedia-'+language)
        receipt = dest/'wave4-download.json'
        if receipt.exists() and load(receipt).get('status') == 'downloaded':
            continue
        pattern = '20231101.'+language+'/train-*.parquet'
        try:
            import fnmatch
            if not any(fnmatch.fnmatch(f.rfilename, pattern) for f in info.siblings):
                raise ValueError('No matching language files')
            snapshot_download(repo, repo_type='dataset', revision=info.sha,
                local_dir=dest, max_workers=4, allow_patterns=[pattern, 'README.md'])
            write_json(receipt, dict(repo=repo, revision=info.sha, language=language,
                config='20231101.'+language, status='downloaded', training_ready=False,
                purpose='document-preserving transformations and synthetic grounding'))
            print('WIKIPEDIA', language, 'downloaded', flush=True)
        except Exception as exc:
            write_json(receipt, dict(repo=repo, language=language, status='blocked', error=str(exc)))


def enqueue(root, component, path):
    sealed = preflight((component, str(path), str(root/'audit-ready'/component)))
    with queue_lock(root/'audit/.enqueue.lock'):
        q = Queue(root/'audit/jobs.sqlite')
        try:
            q.db.execute('CREATE TABLE IF NOT EXISTS components (name TEXT PRIMARY KEY, sha TEXT NOT NULL)')
            old = q.db.execute('SELECT sha FROM components WHERE name=?', (component,)).fetchone()
            if old:
                if old[0] != sealed['sha256']:
                    raise ValueError('Previously queued component changed')
                return
            q.db.execute('BEGIN IMMEDIATE')
            try:
                for index, row in enumerate(rows(sealed['path']), 1):
                    q.add('audit', audit_payload(row, MODEL))
                    # Release the writer lock regularly so live audit clients
                    # can claim and complete jobs while large sources enqueue.
                    if index % 512 == 0:
                        q.db.execute('COMMIT')
                        q.db.execute('BEGIN IMMEDIATE')
                q.db.execute('INSERT INTO components VALUES (?, ?)', (component, sealed['sha256']))
                q.db.execute('COMMIT')
            except BaseException:
                q.db.execute('ROLLBACK')
                raise
            write_json(root/'audit/status.json', dict(jobs=q.status(), training_ready=False))
        finally:
            q.close()


def parallel(root, workers):
    cfg = configuration()
    directory = root/'translations'
    write_json(directory/'config.json', cfg)
    inventory = opus.discover(directory, cfg)
    for item in inventory['pairs'].values():
        for entry in item['corpora']:
            if entry['corpus'] in ('MIZAN', 'SETIMES'):
                entry.update(status='approved',
                    license='cc-by-4.0' if entry['corpus']=='MIZAN' else 'cc-by-sa-3.0',
                    license_evidence=f"https://opus.nlpl.eu/legacy/{entry['corpus']}.php")
    write_json(directory/'opus/inventory.json', inventory)
    jobs = [(directory, pair, item, cfg) for pair, item in inventory['pairs'].items()]
    requested = {'-'.join(p) for p in cfg['requested_pairs']}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for job, result in zip(jobs, pool.map(prepare_one, jobs)):
            pair = job[1]
            if pair in requested and result['state']=='direct_candidates_ready':
                enqueue(root, 'direct-'+pair, directory/'candidates'/('opus-'+pair)/'candidates.jsonl')
    write_json(root/'parallel-stage.json', dict(status='direct_stage_finished',
        missing_work=['additional approved institutional corpora', 'English pivots',
                      'combined token budget enforcement after audit'], training_ready=False))


def institutional(root, workers):
    from .european_opus import review
    cfg = configuration()
    directory = root/'institutional-translations'
    inventory = load(root/'translations/opus/inventory.json')
    # Separate immutable components: do not mutate candidates already under audit.
    for item in inventory['pairs'].values():
        item['corpora'] = [entry for entry in item['corpora']
                           if entry['corpus'] not in ('Tatoeba', 'MIZAN', 'SETIMES')]
    write_json(directory/'opus/inventory.json', inventory)
    write_json(directory/'config.json', cfg)
    review(directory)
    inventory = load(directory/'opus/inventory.json')
    jobs = [(directory, pair, item, cfg) for pair,item in inventory['pairs'].items()
            if any(e.get('status')=='approved' for e in item['corpora'])]
    requested = {'-'.join(p) for p in cfg['requested_pairs']}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for job,result in zip(jobs,pool.map(prepare_one,jobs)):
            pair = job[1]
            if pair in requested and result['state']=='direct_candidates_ready':
                enqueue(root,'institutional-'+pair,directory/'candidates'/('opus-'+pair)/'candidates.jsonl')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['downloads', 'parallel', 'wikipedia', 'institutional'])
    p.add_argument('--root', type=Path, default=Path('data/dfm13/wave4'))
    p.add_argument('--workers', type=int, default=8)
    a = p.parse_args()
    with lock(a.root/(a.stage+'.lock')):
        if a.stage == 'downloads':
            downloads(a.root)
        elif a.stage == 'wikipedia':
            wikipedia(a.root)
        elif a.stage == 'institutional':
            institutional(a.root,a.workers)
            # Also reconcile direct work produced by an older, still-live process.
            from .wave_job_coverage import reconcile
            reconcile(a.root)
        else:
            parallel(a.root, a.workers)


if __name__ == '__main__':
    main()
