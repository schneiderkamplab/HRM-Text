"""Publish only the 64 exactly verified, HF-reconstructed DFM10 OPUS inputs."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import sys
import time
import numpy as np
from huggingface_hub import HfApi, hf_hub_download
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.acquire_dfm10_hf import save, sha
from scripts.replay_dfm_serial import equal_arrays

WORK = ROOT / 'data/rebuild_hf_dfm/serial-queue/dfm10-hf-v2'
REPO = 'schneiderkamplab/dfm10-opus-da-en-rebuild-ready'
REGISTRY = ROOT / 'config/data/dfm10_rebuild_ready_packages.json'
FIELDS = ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len')


def verified_inputs(work):
    cfg = json.loads((work/'hf_recipe.json').read_text())
    inputs = json.loads((work/'inputs-verified.json').read_text())
    tokens = json.loads((work/'all-token-comparison.json').read_text())
    if (cfg.get('recipe') != 'dfm10-hf-v2' or inputs.get('config_sha256') != sha(work/'hf_recipe.json')
            or tokens.get('status') != 'matched' or tokens.get('tasks') != 4351):
        raise ValueError('Exact HF-only reconstruction has not passed token verification')
    tasks = [t for t in cfg['tasks'] if t['component'] == 'opus_da_en_repaired']
    if len(tasks) != 64 or len({t['task'] for t in tasks}) != 64:
        raise ValueError('OPUS task inventory differs')
    for task in tasks:
        if Path(task['task']).name != task['task'] or not task['task'].endswith('.parquet'):
            raise ValueError('Unsafe/non-Parquet OPUS task')
        source = (ROOT/task['source']).resolve(strict=True)
        if not source.is_relative_to((work/'payloads').resolve()):
            raise ValueError('OPUS payload outside new HF-only reconstruction')
        provenance = task.get('hf_provenance', {})
        if provenance.get('repo_id') != 'schneiderkamplab/dfm10-opus-da-en-repaired':
            raise ValueError('OPUS HF lineage missing')
    return cfg, tasks


def package(work):
    cfg, tasks = verified_inputs(work)
    dest = work/'opus-hf-package'
    (dest/'data').mkdir(parents=True, exist_ok=True)
    files=[]
    for i, task in enumerate(tasks, 1):
        source = (ROOT/task['source']).resolve(strict=True)
        if source.stat().st_size != task['source_size'] or sha(source) != task['sha256']:
            raise ValueError('Verified OPUS input changed')
        for field in FIELDS:
            equal_arrays(np.load(work/'union'/task['task']/(field+'.npy'), mmap_mode='r'),
                         np.load(ROOT/'data/tokenized_dfm10'/task['task']/(field+'.npy'), mmap_mode='r'),
                         task['task']+'/'+field)
        target = dest/'data'/task['task']
        if not target.exists(): os.link(source, target)
        if sha(target) != task['sha256']: raise ValueError('Stale publication payload')
        files.append({'path': 'data/'+task['task'], 'task':task['task'], 'bytes':task['source_size'], 'sha256':task['sha256'], 'upstream':{k:v for k,v in task['hf_provenance'].items() if k in ('repo_id','revision','source_file','sha256','rows','format')}})
        print(f'OPUS verified and packaged {i}/64', flush=True)
    provenance = dest/'provenance'
    provenance.mkdir(exist_ok=True)
    for source,name in [(work/'historical_adapter.py','tokenize_chat_template.py'), (work/'chat_template.jinja','chat_template.jinja'), (ROOT/'scripts/tokenize_historical_chat.py','tokenize_historical_chat.py'), (ROOT/'scripts/materialize_dfm10_hf.py','materialize_dfm10_hf.py')]:
        shutil.copyfile(source, provenance/name)
    save(provenance/'tokenizer-recipe.json', {k:cfg[k] for k in ('tokenizer_repo','tokenizer_revision','tokenizer_post_processor','tokenizer_semantic_sha256','adapter_revision','template_revision')})
    save(provenance/'verification.json', {'status':'matched','tasks':64,'arrays_per_task':5,'scope':'all OPUS token and instance/response index values against historical DFM10; whole-corpus sampled verification is separate','dfm10_config_sha256':sha(work/'hf_recipe.json')})
    upstream=tasks[0]['hf_provenance']
    card=Path(hf_hub_download(upstream['repo_id'],'README.md',repo_type='dataset',revision=upstream['revision'],local_dir=work/'opus-upstream-card'))
    shutil.copyfile(card, provenance/'upstream-README.md')
    save(dest/'manifest.json', {'version':1,'dataset':'DFM10 OPUS DA/EN','format':'Parquet condition/instruction/response; exact task boundaries and row order','files':files,'provenance':[{'path':str(p.relative_to(dest)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(provenance.iterdir())]})
    (dest/'README.md').write_text('---\nlanguage:\n- da\n- en\ntask_categories:\n- translation\n---\n# DFM10 OPUS rebuild-ready inputs\n\n'
        'These 64 converted Parquet shards were reconstructed exclusively from pinned HF exports. '
        'All five token/index arrays for every task match the historical DFM10 reference exactly. '
        'This is task-level verification; it does not claim that full DFM10 sampled-epoch verification has finished.\n\n'
        'Download at the pinned revision and verify every manifest checksum. Preserve the filenames under data/ '
        'as tokenizer task names and retain Parquet row order. The condition column is significant. '
        'Use the pinned tokenizer, BOS post-processor and Gemma chat template recorded under provenance/. '
        'No regrouping of chat export rows or model-based conversion is needed. Tokenization and final comparisons remain required.\n\n'
        'Upstream attribution and source-specific licenses continue to apply; this package grants no new blanket license. '
        'See provenance/upstream-README.md and the per-file pinned upstream identities. No agreement-only data are included.\n')
    allowed={f['path'] for f in files}|{'manifest.json','README.md'}|{str(p.relative_to(dest)) for p in provenance.iterdir()}
    actual={str(p.relative_to(dest)) for p in dest.rglob('*') if p.is_file()}
    if actual != allowed: raise ValueError('Unexpected publication files')
    return dest


def publish(work, api):
    package_dir=package(work)
    commit_path=work/'opus-hf-upload.json'
    if not commit_path.exists():
        created=work/'opus-hf-created.json'
        if not created.exists():
            api.create_repo(repo_id=REPO, repo_type='dataset', private=False, exist_ok=False)
            save(created, {'repo_id':REPO})
        result=api.upload_folder(repo_id=REPO, repo_type='dataset', folder_path=package_dir,
                                commit_message='Publish 64 exactly verified DFM10 OPUS converted shards')
        save(commit_path, {'repo_id':REPO,'revision':result.oid,'manifest_sha256':sha(package_dir/'manifest.json')})
    saved=json.loads(commit_path.read_text())
    if saved['manifest_sha256'] != sha(package_dir/'manifest.json'):
        raise ValueError('Package changed after upload')
    remote={x.rfilename:x for x in api.dataset_info(REPO,revision=saved['revision'],files_metadata=True).siblings}
    for path in package_dir.rglob('*'):
        if not path.is_file(): continue
        rel=str(path.relative_to(package_dir));entry=remote[rel]
        actual=entry.lfs.sha256 if entry.lfs else sha(Path(hf_hub_download(REPO,rel,repo_type='dataset',revision=saved['revision'],local_dir=work/'opus-upload-check')))
        if actual != sha(path) or entry.size != path.stat().st_size:
            raise ValueError('Remote upload verification failed: '+rel)
    saved.update(status='uploaded_sha256_verified',tasks=64)
    save(work/'opus-hf-publication.json',saved)
    registry=json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {}
    registry['opus_da_en_repaired']=saved
    save(REGISTRY,registry)
    print('Published and verified',REPO,saved['revision'],flush=True)


def run(wait):
    if (WORK/'opus-publication-cancelled.json').exists():
        raise RuntimeError('OPUS publication cancelled by user; new explicit authorization required')
    with (WORK/'opus-publish.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        status=WORK/'opus-publication-status.json'
        if (WORK/'opus-hf-publication.json').exists(): return
        try:
            while True:
                try: verified_inputs(WORK)
                except FileNotFoundError:
                    if not wait: raise
                    save(status,{'status':'waiting','gate':'exact DFM10 HF-only token-array verification','repo_id':REPO})
                    time.sleep(30)
                    continue
                break
            save(status,{'status':'verifying_and_publishing','repo_id':REPO})
            publish(WORK,HfApi())
            save(status,{'status':'published','repo_id':REPO})
        except Exception as exc:
            save(status,{'status':'blocked','error':str(exc),'repo_id':REPO})
            raise


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wait',action='store_true')
    run(p.parse_args().wait)
