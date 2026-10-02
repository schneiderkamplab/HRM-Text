"""Integrate producer pair-audited DaLA releases using shared screening/tokenization.

Creates train-only local additions and a pinned registry. No upload or live
sampled-corpus modification. Public three-split packages remain producer-owned.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

from .io import file_hash, load, lock, write_json
from .records import chat_fingerprint,validate_messages
from .scandi_overlap import text_hash,normalized
from .screen_parallel import prepare_screen_row

PRODUCER=Path('/work/mimir/DaLA')
sys.path.insert(0,str(PRODUCER/'scripts'))
import hf_package_runtime as runtime


def heldout_index(packages,output):
    """Protect *all* producer heldout pairs, including audit-rejected pairs."""
    path=output/'heldout.sqlite';receipt=output/'heldout.json'
    snapshot=load(packages/'audit-snapshot.json')
    sources=[s for s in snapshot['sources'] if not s['component'].endswith(':train')]
    if receipt.exists():
        if load(receipt)['sources']!=sources:raise ValueError('Heldout sources changed')
        return path
    if path.exists():raise FileExistsError('Incomplete heldout index')
    c=sqlite3.connect(path);c.executescript('CREATE TABLE held(hash TEXT PRIMARY KEY) WITHOUT ROWID; CREATE TABLE documents(hash TEXT PRIMARY KEY) WITHOUT ROWID;')
    count=0
    for source in sources:
        if file_hash(source['path'])!=source['sha256']:raise ValueError('Heldout input changed')
        for line in open(source['path']):
            p=json.loads(line);count+=1
            c.executemany('INSERT OR IGNORE INTO held VALUES (?)',[(text_hash(p[k]),) for k in ('original','corrupted')])
            c.execute('INSERT OR IGNORE INTO documents VALUES (?)',(p['document_sha256'],))
        c.commit()
    c.close();write_json(receipt,dict(sources=sources,pairs=count,method='exact normalized text and source document hash; all twelve raw heldout pools',sha256=file_hash(path)))
    return path


def prepare_language(job):
    lang,package,output,held,reference,reference_receipt=job
    package,output=Path(package),Path(output)
    receipt=output/'components'/lang/'integration.json'
    if receipt.exists():
        result=load(receipt)
        for comp in result['components']:
            for item in comp['data_files']:
                if file_hash(item['path'])!=item['sha256']:raise ValueError('Completed component changed')
        return result
    config=load(package/'metadata/config.json');proof=load(package/'metadata/validation.json');assert proof['status']=='passed'
    inputs=package/'provenance/train.pairs.jsonl.gz';manifest=load(package/'metadata/manifest.json')
    assert file_hash(inputs)==manifest['files']['provenance/train.pairs.jsonl.gz']['sha256']
    h=sqlite3.connect(Path(held).as_uri()+'?mode=ro&immutable=1',uri=True)
    refs=sqlite3.connect(Path(reference).as_uri()+'?mode=ro&immutable=1',uri=True)
    h.execute('PRAGMA mmap_size=1073741824')
    refs.execute('PRAGMA mmap_size=8589934592')
    # Pin the indexed reference files against the published inventory.
    for item in load(reference_receipt)['files']:
        stored=refs.execute('SELECT sha256 FROM files WHERE path=?',(item['path'],)).fetchone()
        if not stored or stored[0]!=item['sha256']:raise ValueError('Reference index not pinned')
    counts=Counter();handles={};files={t:[] for t in runtime.TASKS};shard_counts=Counter();seen=set()
    reject=output/'components'/lang/'screening-exclusions.jsonl.gz';reject.parent.mkdir(parents=True,exist_ok=True)
    def close(task):
        if task in handles:
            handle,path=handles.pop(task);handle.close()
            files[task].append(dict(path=str(path),sha256=file_hash(path),bytes=path.stat().st_size,rows=shard_counts[task]));shard_counts[task]=0
    with gzip.open(reject,'wt',encoding='utf-8',compresslevel=1) as omitted:
        for p in runtime.read_gzip(inputs):
            counts['input_pairs']+=1
            assert p['split']=='train' and p['language']==lang and p['audit']['result']['decision']=='pass'
            assert all(p['audit']['result'].get(k)=='yes' for k in ('original_correct','corrupted_incorrect','edit_is_grammar_or_spelling','meaning_preserved'))
            hashes=[text_hash(p[k]) for k in ('original','corrupted')];reasons=[]
            if h.execute('SELECT 1 FROM documents WHERE hash=?',(p['document_sha256'],)).fetchone():reasons.append('heldout_document')
            if any(h.execute('SELECT 1 FROM held WHERE hash=?',(v,)).fetchone() for v in hashes):reasons.append('heldout_sentence')
            if any(v in seen for v in hashes):reasons.append('duplicate_sentence_within_language')
            rows=[]
            for task in runtime.TASKS:
                for clean in (True,False):
                    row=runtime.chat_row(p,clean,dict(config,task=task));messages=row['messages'];validate_messages(messages)
                    record=dict(id=f"dala-{lang}-{task}:{p['pair_id']}:{'clean' if clean else 'corrupted'}",messages=messages,language=lang,task=task,audit_context=dict(original=p['original'],corrupted=p['corrupted']))
                    prepared=prepare_screen_row(record);reasons.extend(prepared['reasons'])
                    for value in prepared['chats']:
                        kinds=refs.execute("SELECT kind FROM fingerprints WHERE kind IN ('inherited_chat','heldout_chat') AND hash=?",(value,)).fetchall()
                        reasons.extend(x[0] for x in kinds)
                    for value in prepared['texts']:
                        if refs.execute("SELECT 1 FROM fingerprints WHERE kind='heldout_text' AND hash=?",(value,)).fetchone():reasons.append('reference_heldout_text')
                    record.pop('audit_context');rows.append((task,record))
            if reasons:
                reasons=sorted(set(reasons));counts.update('excluded:'+x for x in reasons);omitted.write(json.dumps(dict(pair_id=p['pair_id'],reasons=reasons))+'\n');continue
            seen.update(hashes);counts['retained_pairs']+=1
            for task,row in rows:
                if task not in handles or shard_counts[task]>=50000:
                    close(task)
                    path=output/'accepted_inputs'/f'dfm12-dala-{lang.lower()}-{task}'/f'train-{len(files[task]):05d}.jsonl.gz';path.parent.mkdir(parents=True,exist_ok=True)
                    handles[task]=(gzip.open(path,'wt',encoding='utf-8',compresslevel=1),path)
                handles[task][0].write(json.dumps(row,ensure_ascii=False)+'\n');shard_counts[task]+=1
    for task in list(handles):close(task)
    h.close();refs.close()
    components=[dict(name=f'dfm12-dala-{lang.lower()}-{task}',language=lang,task=task,repeat=1,rows=2*counts['retained_pairs'],data_files=files[task],source_package=str(package),source_manifest_sha256=file_hash(package/'metadata/manifest.json'),audit_contract='producer_pair_audit_four_yes',screening_exclusions=dict(path=str(reject),sha256=file_hash(reject))) for task in runtime.TASKS]
    result=dict(language=lang,counts=dict(counts),components=components);write_json(receipt,result)
    print('INTEGRATED',lang,dict(counts),flush=True);return result


def validate_additions(path):
    """Shared admission hook for the normal DFM12 build workflow."""
    result=load(path)
    if result.get('status')!='complete_audited_train_only' or not result.get('user_authorized_local_integration'):
        raise ValueError('Local DaLA integration incomplete/unapproved')
    for key, checksum in (('tokenizer_path','tokenizer_sha256'),('chat_template_path','chat_template_sha256')):
        if file_hash(result['tokenizer_info'][key]) != result[checksum]:
            raise ValueError('Tokenizer/template changed')
    names=set()
    for component in result['components']:
        if component['name'] in names:
            raise ValueError('Duplicate component')
        names.add(component['name'])
        if component['audit_contract']!='producer_pair_audit_four_yes':raise ValueError('Unknown audit contract')
        package=Path(component['source_package'])
        if file_hash(package/'metadata/manifest.json') != component['source_manifest_sha256']:
            raise ValueError('Producer package changed')
        if load(package/'metadata/validation.json').get('status') != 'passed':
            raise ValueError('Unvalidated producer package')
        if component['rows'] != sum(item['rows'] for item in component['data_files']):
            raise ValueError('Component row count mismatch')
        for item in component['data_files']:
            if not Path(item['path']).name.startswith('train-'):
                raise ValueError('Heldout file in training integration')
            if file_hash(item['path'])!=item['sha256']:raise ValueError('Changed local accepted input')
    return result


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--packages',type=Path,default=PRODUCER/'export-upload/european-audited-20260928');p.add_argument('--output',type=Path,default=Path('data/dfm12/dala-audited-european-20260928'));p.add_argument('--workers',type=int,default=12);a=p.parse_args()
    output=a.output.resolve();output.mkdir(parents=True,exist_ok=True)
    os.environ.update(CUDA_VISIBLE_DEVICES='',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='1')
    with lock(output/'.lock'):
        inventory=load(a.packages/'packages.json');assert inventory['status']=='validated_local_upload_preparation'
        held=heldout_index(a.packages,output)
        ref=Path('data/dfm12/european-expansion-20260926/screened').resolve()
        local_reference=Path('/tmp/dala-dfm12-reference-20260928.sqlite')
        reference_snapshot=output/'reference-snapshot.json'
        if not reference_snapshot.exists():
            if local_reference.exists():
                raise FileExistsError('Unpinned reference cache exists')
            src=sqlite3.connect((ref/'overlap.sqlite').as_uri()+'?mode=ro',uri=True)
            dst=sqlite3.connect(local_reference)
            src.backup(dst);dst.close();src.close()
            write_json(reference_snapshot,dict(path=str(local_reference),sha256=file_hash(local_reference),
                       inventory_sha256=file_hash(ref/'reference-inputs.json')))
        pin=load(reference_snapshot)
        if file_hash(local_reference)!=pin['sha256'] or file_hash(ref/'reference-inputs.json')!=pin['inventory_sha256']:
            raise ValueError('Reference snapshot changed')
        jobs=[(item['language'],item['path'],str(output),str(held),str(local_reference),str(ref/'reference-inputs.json')) for item in inventory['packages']]
        with ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(prepare_language,jobs))
        components=[c for r in results for c in r['components']]
        info=load('data/sampled_dfm11/metadata.json')['tokenizer_info'];assert not info.get('enable_thinking')
        subprocess.run([sys.executable,'scripts/tokenize_chat_template.py',str(output/'accepted_inputs'),'--tokenizer-path',info['tokenizer_path'],'--chat-template',info['chat_template_path'],'--output-dir',str(output/'tokenized'),'--max-seq-len','4096','--workers',str(a.workers)],check=True)
        import numpy as np
        token_counts={}
        for folder in (output/'tokenized').iterdir():
            if not folder.is_dir():continue
            name=folder.name.split('__')[0];count=token_counts.setdefault(name,dict(rows=0,tokens=0))
            inst=np.load(folder/'inst_len.npy',mmap_mode='r');resp=np.load(folder/'resp_len.npy',mmap_mode='r');assert len(inst)==len(resp)
            count['rows']+=len(inst);count['tokens']+=int(inst.sum())+int(resp.sum())
        for comp in components:
            comp['tokenization']=token_counts[comp['name']]
            # Complete short two-message pairs should never require truncation.
            if comp['tokenization']['rows']!=comp['rows']:raise ValueError('Tokenization dropped training rows')
        manifest=dict(status='complete_audited_train_only',user_authorized_local_integration=True,upload_performed=False,components=components,tokenized=str(output/'tokenized'),tokenizer_info=info,tokenizer_sha256=file_hash(info['tokenizer_path']),chat_template_sha256=file_hash(info['chat_template_path']),producer_packages_sha256=file_hash(a.packages/'packages.json'),reference_inventory_sha256=file_hash(ref/'reference-inputs.json'),reference_inventory=str(ref/'reference-inputs.json'),heldout_receipt_sha256=file_hash(output/'heldout.json'),screening_limitations=['Partial inherited references only','Exact overlap only; no fuzzy/semantic decontamination'],human_linguistic_validation=False)
        write_json(output/'integration.json',manifest);validate_additions(output/'integration.json')
        write_json(Path('data/dfm12/local-audited-dala-additions.json'),dict(path=str(output/'integration.json'),sha256=file_hash(output/'integration.json')))
        print('DFM12_AUDITED_DALA_READY',output/'integration.json',flush=True)

if __name__=='__main__':main()
