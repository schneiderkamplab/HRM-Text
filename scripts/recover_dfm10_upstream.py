"""Reconstruct the five DFM10 tasks absent from derivative export packages."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from huggingface_hub import HfApi, hf_hub_download
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.acquire_dfm10_hf import DEFAULT, save, sha

SPECS = [
 ('dacoref', 'alexandrainst/dacoref', None, ['data/train-00000-of-00001-ffdeed5775622c14.parquet']),
 ('nordjylland', 'alexandrainst/nordjylland-news-summarization', None, ['data/train-00000-of-00001-4fb110c0f6314175.parquet']),
 ('charter', 'danish-foundation-models/synthetic-values-model-charter', '5c14264c4bd5901fe93c0c8bbf9d296cde658fcc', ['sft_train.jsonl', 'sft_test.jsonl', 'dpo_train.jsonl', 'dpo_test.jsonl']),
 ('elrc', 'qanastek/ELRC-Medical-V2', '7f5633e7f9903947a9e51ab0e12ff483574aeebf', ['csv/en-da.csv']),
 ('nhs', 'NHSEDataScience/synthetic_clinical_notes', '368a5bd2a55090a0bae3436f2823d606c5077158', ['silver/synthetic_clinical_notes.csv']),
]


def run(work=DEFAULT):
    dest = work / 'upstream'
    dest.mkdir(exist_ok=True)
    lock = dest / 'lock.json'
    if not lock.exists():
        api = HfApi()
        save(lock, [{'name': name, 'repo_id': repo, 'revision': rev or api.dataset_info(repo).sha, 'files': files} for name, repo, rev, files in SPECS])
    receipts = []
    for item in json.loads(lock.read_text()):
        files = []
        for rel in item['files']:
            path = Path(hf_hub_download(item['repo_id'], rel, repo_type='dataset', revision=item['revision'], local_dir=dest / item['name']))
            files.append({'path': rel, 'sha256': sha(path), 'bytes': path.stat().st_size})
        receipts.append(dict(item, downloaded=files))
        save(dest / 'acquisition-receipt.json', receipts)
        print('Acquired upstream', item['name'], flush=True)
    code = dest / 'code'
    code.mkdir(exist_ok=True)
    modules = {}
    for name in ('alexandra', 'medical', 'synthetic_values_model_charter'):
        path = code / (name + '.py')
        path.write_bytes(subprocess.check_output(['git', 'show', 'ccbb215:scripts/prepare_dfm10_'+name+'.py'], cwd=ROOT))
        spec = importlib.util.spec_from_file_location('frozen_dfm10_'+name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    out = dest / 'converted'
    out.mkdir(exist_ok=True)
    alex = modules['alexandra']
    for name, task, fn in [('dacoref', 'alexandra_dacoref__train.jsonl', alex.dacoref_rows), ('nordjylland', 'alexandra_nordjylland_original__train.jsonl', alex.nordjylland_rows)]:
        source = next((dest / name / 'data').glob('*.parquet'))
        alex.write_jsonl(out / task, fn(source))
    medical = modules['medical']
    medical.convert_elrc(dest / 'elrc/csv/en-da.csv', out / 'elrc_medical_en_da__train.parquet')
    medical.convert_nhs(dest / 'nhs/silver/synthetic_clinical_notes.csv', out / 'nhs_synthetic_clinical_notes__train.parquet')
    subprocess.run([sys.executable, str(code / 'synthetic_values_model_charter.py'), '--input-dir', str(dest / 'charter'), '--sft-output-dir', str(out / 'charter'), '--preference-output-dir', str(dest / 'preferences'), '--force'], check=True)
    save(dest / 'conversion-receipt.json', {'converter_revision': 'ccbb215', 'code': {p.name: sha(p) for p in code.glob('*.py')}, 'outputs': {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()}})
    print('Five upstream tasks reconstructed; token equivalence remains to be verified', flush=True)


if __name__ == '__main__':
    run()
