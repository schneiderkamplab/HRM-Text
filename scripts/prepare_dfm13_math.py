"""Pinned MATH train worked solutions, test-only overlap screening, CPU tokenization."""
import argparse
from collections import Counter, defaultdict
import json
import os
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import digest, file_hash, load, write_json
from utils.functions import last_boxed_only_string

REPO = 'EleutherAI/hendrycks_math'
REVISION = '21a5633873b6a120296cce3e2df9d5550074f4a3'
CONFIGS = ('algebra', 'counting_and_probability', 'geometry', 'intermediate_algebra',
           'number_theory', 'prealgebra', 'precalculus')
NAME = 'hendrycks_math_worked'


def normalized_problem(problem):
    if not isinstance(problem, str) or not problem.strip():
        raise ValueError('Empty/non-string problem')
    return ' '.join(problem.split())


def worked_solution(solution):
    if not isinstance(solution, str) or not solution.strip():
        raise ValueError('Empty/non-string solution')
    answer = last_boxed_only_string(solution)
    if not answer:
        # A TeX macro may take one unbraced digit as its argument (e.g. \boxed 2$).
        # Normalize only that unambiguous syntax for the shared extractor; retain source prose.
        extraction_text = re.sub(r'(\\(?:boxed|fbox))\s+([0-9])(?=\$)', r'\1{\2}', solution)
        answer = last_boxed_only_string(extraction_text)
    if not answer:
        raise ValueError('Missing extractable final box')
    terminal = '\\boxed{' + answer + '}'
    # Never remove reasoning or intermediate boxes from the original worked solution.
    response = solution if solution.rstrip().endswith(terminal) else solution + '\n\nFinal answer: ' + terminal
    return response, answer, response != solution


def screen(train, test):
    exact, normalized = defaultdict(list), defaultdict(list)
    for item in test:
        problem = item['row']['problem']
        exact[problem].append(item['id'])
        normalized[normalized_problem(problem)].append(item['id'])
    seen, retained, excluded = {}, [], []
    for item in train:
        row = item['row']
        problem = row['problem']
        key = normalized_problem(problem)
        base = dict(id=item['id'], config=item['config'], row_index=item['row_index'],
                    source_row_sha256=digest(row), problem_sha256=digest(problem),
                    normalized_problem_sha256=digest(key))
        matches = exact.get(problem) or normalized.get(key)
        if matches:
            excluded.append(dict(base, reason='train_test_exact' if problem in exact else 'train_test_whitespace',
                                 matched_test_ids=matches))
            continue
        if key in seen:
            winner = seen[key]
            excluded.append(dict(base, reason='train_duplicate_exact' if problem == winner['problem'] else 'train_duplicate_whitespace',
                winner_id=winner['id'], same_solution=row['solution'] == winner['solution']))
            continue
        try:
            response, answer, appended = worked_solution(row['solution'])
        except ValueError as error:
            excluded.append(dict(base, reason='invalid_solution', detail=str(error)))
            continue
        seen[key] = dict(id=item['id'], problem=problem, solution=row['solution'])
        retained.append(dict(id=item['id'], messages=[dict(role='user',content=problem),
            dict(role='assistant',content=response)], target_message_index=1,
            chat_template_kwargs=dict(enable_thinking=False), metadata=dict(
                source=REPO, revision=REVISION, split='train', config=item['config'],
                source_file=item['source_file'], source_file_sha256=item['source_file_sha256'],
                source_row_index=item['row_index'], source_row_sha256=digest(row),
                level=row.get('level'), type=row.get('type'), license='mit',
                original_solution_sha256=digest(row['solution']), final_answer=answer,
                terminal_box_appended=appended, quality_basis='original source worked solution; not model audited')))
    return retained, excluded


def download(download_dir):
    from huggingface_hub import HfApi, hf_hub_download
    import pyarrow.parquet as pq
    expected = {f'{config}/{split}-00000-of-00001.parquet' for config in CONFIGS for split in ('train','test')}
    available = HfApi().list_repo_files(REPO, repo_type='dataset', revision=REVISION)
    if {p for p in available if p.endswith('.parquet')} != expected:
        raise ValueError('Pinned parquet inventory differs from expected seven train/test configurations')
    card = Path(hf_hub_download(REPO,'README.md',repo_type='dataset',revision=REVISION,local_dir=download_dir))
    import yaml
    frontmatter = yaml.safe_load(card.read_text().split('---',2)[1])
    if frontmatter.get('license') != 'mit':
        raise ValueError('Unexpected pinned source license')
    inventories, rows = [], {'train':[], 'test':[]}
    for config in CONFIGS:
        for split in ('train','test'):
            name=f'{config}/{split}-00000-of-00001.parquet'
            path=Path(hf_hub_download(REPO,name,repo_type='dataset',revision=REVISION,local_dir=download_dir))
            sha=file_hash(path)
            table=pq.read_table(path)
            if set(table.column_names) != {'problem','solution','level','type'}:
                raise ValueError('Unexpected MATH schema')
            inventories.append(dict(config=config,split=split,path=str(path.resolve()),sha256=sha,rows=len(table)))
            for index,row in enumerate(table.to_pylist()):
                rows[split].append(dict(id=f'hendrycks_math:{config}:{split}:{index}',config=config,
                    row_index=index,source_file=name,source_file_sha256=sha,row=row))
    if len(rows['train']) != 7500 or len(rows['test']) != 5000:
        raise ValueError('Unexpected pinned split totals')
    return rows, inventories, dict(path=str(card.resolve()),sha256=file_hash(card),license='mit')


def prepare(output, download_dir):
    if output.exists():
        raise ValueError('Fresh output required; preserve existing artifacts')
    rows, sources, license_evidence=download(download_dir)
    retained, excluded=screen(rows['train'],rows['test'])
    output.mkdir(parents=True)
    metadata=output/'metadata'
    metadata.mkdir()
    with (output/'train.jsonl').open('x') as stream:
        for row in retained:
            stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    with (metadata/'screening.jsonl').open('x') as stream:
        for row in excluded:
            stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    manifest=dict(schema='dfm13-math-worked-v1',name=NAME,repo_id=REPO,revision=REVISION,
        license='mit',license_evidence=license_evidence,source_files=sources,train_rows=7500,test_rows_screening_only=5000,
        rows=len(retained),exclusions=dict(Counter(row['reason'] for row in excluded)),
        retained_by_config=dict(Counter(row['metadata']['config'] for row in retained)),
        terminal_box_appended=sum(row['metadata']['terminal_box_appended'] for row in retained),
        train_sha256=file_hash(output/'train.jsonl'),screening_sha256=file_hash(metadata/'screening.jsonl'),
        overlap_policy='Exclude exact and collapsed-whitespace problem matches across all test configurations; dedup train problems in fixed config/row order.',
        train_dedup_policy='First eligible worked solution wins; differing duplicate solutions recorded.',
        final_box_policy='Preserve entire original solution; normalize unbraced single-digit TeX box arguments before last_boxed_only_string extraction; append canonical terminal box only when not already terminal.',
        corpus_overlap='Not whole-corpus deduplicated. Existing RLVR MATH direct answers (7,498, repeat 10) share problems intentionally; this worked-solution addition is repeat 5. Prior raw math_train prefix lookup had no match and is not absence proof.',
        repeat=5,hard_truncation=False,test_rows_in_output=0,
        pins={str(p.resolve()):file_hash(p) for p in (Path(__file__),ROOT/'utils/functions.py',ROOT/'scripts/tokenize_chat_template.py',ROOT/'data/dfm11_tokenizer/tokenizer.json',ROOT/'data/dfm11_tokenizer/chat_template.jinja')})
    assert len(retained)+len(excluded)==7500
    write_json(metadata/'manifest.json',manifest)
    return manifest


def tokenize(output, tokenized):
    import numpy as np
    if tokenized.exists():
        raise ValueError('Fresh tokenized directory required')
    manifest=load(output/'metadata/manifest.json')
    for name,sha in manifest['pins'].items():
        if file_hash(name)!=sha:
            raise ValueError('Implementation/tokenizer pin drift')
    cmd=[sys.executable,str(ROOT/'scripts/tokenize_chat_template.py'),str(output),'-o',str(tokenized),
         '--tokenizer-path',str(ROOT/'data/dfm11_tokenizer/tokenizer.json'),
         '--chat-template',str(ROOT/'data/dfm11_tokenizer/chat_template.jinja'),'--workers','1']
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with (output/'metadata/tokenization.log').open('x') as log:
        subprocess.run(cmd,env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    completion=load(tokenized/'completion.json')
    if completion['rows']!=manifest['rows'] or completion['skipped_rows_this_run'] or completion['max_seq_len'] is not None:
        raise ValueError('Tokenization changed row coverage or length policy')
    arrays=list(tokenized.rglob('tokens.npy'))
    if len(arrays)!=1:
        raise ValueError('Expected one tokenized training file; screening metadata must not be tokenized')
    folder=arrays[0].parent
    vectors={name:np.load(folder/(name+'.npy'),mmap_mode='r') for name in ('tokens','inst_start','inst_len','resp_start','resp_len')}
    n=manifest['rows']
    if any(len(vectors[name])!=n for name in ('inst_start','inst_len','resp_start','resp_len')):
        raise ValueError('Index count mismatch')
    lengths=vectors['inst_len']+vectors['resp_len']
    if (not np.all(vectors['resp_start']==vectors['inst_start']+vectors['inst_len'])
            or not np.all(vectors['resp_len']>0)
            or not np.all(vectors['inst_start'][1:]==(vectors['resp_start']+vectors['resp_len'])[:-1])
            or int(lengths.sum())!=len(vectors['tokens'])):
        raise ValueError('Token index/target coverage mismatch')
    receipt=dict(rows=n,tokens=len(vectors['tokens']),prompt_tokens=int(vectors['inst_len'].sum()),
        target_tokens=int(vectors['resp_len'].sum()),max_sequence_tokens=int(lengths.max()),
        sequences_over_4096=int((lengths>4096).sum()),workers=1,hard_truncation=False,regex_fix=False,
        command=cmd,output=str(tokenized.resolve()),converted_manifest_sha256=file_hash(output/'metadata/manifest.json'),
        files={str(p.resolve()):file_hash(p) for p in tokenized.rglob('*') if p.is_file()})
    write_json(output/'metadata/tokenization-receipt.json',receipt)
    return receipt


def register(config_path,output,tokenized):
    before=file_hash(config_path)
    config=load(config_path)
    if any(s['name']==NAME for s in config['additions']):
        raise ValueError('Math already registered; refuse duplicate')
    manifest=load(output/'metadata/manifest.json')
    receipt=load(output/'metadata/tokenization-receipt.json')
    if receipt['converted_manifest_sha256']!=file_hash(output/'metadata/manifest.json'):
        raise ValueError('Tokenization manifest drift')
    if file_hash(output/'train.jsonl')!=manifest['train_sha256']:
        raise ValueError('Converted row drift')
    for path,sha in {**manifest['pins'],**receipt['files']}.items():
        if file_hash(path)!=sha:
            raise ValueError('Tokenization input/output drift: '+path)
    entry=dict(name=NAME,repo_id=REPO,revision=REVISION,license='mit',split='train',configs=list(CONFIGS),
        output=str((output/'train.jsonl').resolve()),output_sha256=manifest['train_sha256'],rows=manifest['rows'],
        repeat=5,target_policy='worked_solution_single_assistant_target',converter='scripts/prepare_dfm13_math.py',
        manifest=str((output/'metadata/manifest.json').resolve()),manifest_sha256=file_hash(output/'metadata/manifest.json'),
        tokenized_output=str(tokenized.resolve()),tokenization_receipt=str((output/'metadata/tokenization-receipt.json').resolve()),
        tokenization_receipt_sha256=file_hash(output/'metadata/tokenization-receipt.json'),tokens=receipt['tokens'],
        hard_truncation=False,corpus_overlap=manifest['corpus_overlap'])
    write_json(output/'metadata/registry-before.json',config)
    config['additions'].append(entry)
    if file_hash(config_path)!=before:
        raise ValueError('Concurrent registry edit')
    write_json(config_path,config)
    write_json(output/'metadata/registration-receipt.json',dict(config=str(config_path.resolve()),
        before_sha256=before,after_sha256=file_hash(config_path),entry=entry,previous_additions_preserved=True))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'data/converted_sources/dfm13_math_worked')
    p.add_argument('--download-dir',type=Path,default=ROOT/'data/downloads/datasets/hendrycks_math'/REVISION)
    p.add_argument('--tokenized-output',type=Path,default=ROOT/'data/tokenized_dfm13_additions/hendrycks_math_worked')
    p.add_argument('--config',type=Path,default=ROOT/'config/dfm13_sources.json')
    p.add_argument('--tokenize',action='store_true')
    p.add_argument('--register',action='store_true')
    args=p.parse_args()
    if args.register and not args.tokenize:
        p.error('--register requires --tokenize')
    print(json.dumps(prepare(args.output,args.download_dir)),flush=True)
    if args.tokenize:
        print(json.dumps(tokenize(args.output,args.tokenized_output)),flush=True)
    if args.register:
        register(args.config,args.output,args.tokenized_output)


if __name__=='__main__':
    main()
