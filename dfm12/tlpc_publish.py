"""Scoped TLPC release successor; never rewrites generation manifests or broad gates."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

from .io import atomic, digest, file_hash, load, lock, write_json
from .tlpc_release import CONTRACT, NAMES, readonly, units
from .tlpc_sources import REPO, REVISION, normalize
from .records import chat_fingerprint
from .scandi_overlap import text_hash


def extra_index(root):
    root=Path(root); path=root/'persian-references.sqlite'; marker=root/'persian-references.json'
    if marker.exists():
        receipt=load(marker)
        if file_hash(path)!=receipt['sha256']: raise ValueError('Reference drift')
        return receipt
    registry=load('config/dfm13_sources.json')
    entries=[e for e in registry['additions'] if e.get('output') and '_fa' in e['name'] and not e['name'].startswith('dfm13_tlpc_')]
    counts=Counter(); files={}
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS refs(kind TEXT,hash TEXT,PRIMARY KEY(kind,hash)) WITHOUT ROWID')
        for entry in entries:
            source=Path(entry['output']); sha=file_hash(source)
            if sha!=entry['output_sha256']: raise ValueError('Registered Persian payload changed')
            files[str(source)]=sha
            with source.open() as handle:
                for line in handle:
                    row=json.loads(line);messages=row['messages']
                    db.execute('INSERT OR IGNORE INTO refs VALUES(?,?)',('chat',chat_fingerprint(messages)))
                    for m in messages:
                        if isinstance(m.get('content'),str) and len(m['content'])>=160:
                            db.execute('INSERT OR IGNORE INTO refs VALUES(?,?)',('text',text_hash(m['content'])))
                    counts['registered_persian_rows']+=1
            db.commit()
        dala=Path('data/dfm13/dala-v2-compact-finalized-20261004-v1/groups/fa-recovery/heldout.sqlite')
        with readonly(dala) as held:
            for kind,key in held.execute('SELECT kind,key FROM held'):
                db.execute('INSERT OR IGNORE INTO refs VALUES(?,?)',('dala_'+kind,key))
                counts['dala_heldout_units']+=1
        files[str(dala.resolve())]=file_hash(dala)
    receipt=dict(files=files,counts=dict(counts),sha256=file_hash(path),coverage='current registered Persian source outputs plus Persian DaLA held-out index')
    write_json(marker,receipt);return receipt


def merge(root):
    root=Path(root).resolve(); validation=load(root/'validation.json')
    if not validation['complete']: raise ValueError('Validation not complete')
    extra=extra_index(root); packages=[]
    with lock(root/'merge.lock'), readonly(root/'persian-references.sqlite') as refs:
        for family,name in NAMES.items():
            folder=root/'packages'/name.replace('_','-');output=folder/'data/train.jsonl'
            if (folder/'manifest.json').exists():
                prior=load(folder/'manifest.json')
                if prior['output_sha256']!=file_hash(output):raise ValueError('Existing package changed')
                packages.append(prior);continue
            counts=Counter(); normalized_seen=set(); source_ids=set()
            private=root/(name+'-selection.jsonl')
            with atomic(output) as out, atomic(private) as evidence, atomic(folder/'exclusions.jsonl') as exclusions:
                for part in validation['results']:
                    if part['family']!=family:continue
                    if file_hash(part['path'])!=part['sha256']:raise ValueError('Validated part changed')
                    with open(part['path']) as handle:
                        for line in handle:
                            row=json.loads(line); reasons=list(row['overlap_exclusions'])
                            chats,texts=units(row)
                            if any(refs.execute("SELECT 1 FROM refs WHERE kind='chat' AND hash=?",(h,)).fetchone() for h in chats):reasons.append('registered_persian_chat')
                            if any(refs.execute("SELECT 1 FROM refs WHERE kind='text' AND hash=?",(h,)).fetchone() for h in texts):reasons.append('registered_persian_text')
                            from .dala_compact_finalize import text_key
                            if any(refs.execute("SELECT 1 FROM refs WHERE kind='dala_text' AND hash=?",(text_key(t),)).fetchone()
                                   for t in [row['source']['text'],*[e['text'] for e in row['source']['elements']]]):reasons.append('dala_heldout_text')
                            if row['normalized_fingerprint'] in normalized_seen:reasons.append('normalized_duplicate')
                            if reasons:
                                exclusions.write(json.dumps(dict(id=row['id'],reasons=sorted(set(reasons))))+'\n');counts['excluded']+=1;continue
                            normalized_seen.add(row['normalized_fingerprint']);source_ids.add(row['source']['id'])
                            provenance={k:v for k,v in row['source'].items() if k not in ('original_cache_path','text','elements')}
                            public=dict(id=row['id'],messages=row['messages'],tools=[],language='fa',family=family,
                                source=provenance,audit=dict(**row['audit'],quality_basis='automated independent full-source review; not certified gold'),
                                campaign_manifest_sha256=row['campaign_manifest_sha256'],rendered_training_tokens=row['rendered_training_tokens'])
                            out.write(json.dumps(public,ensure_ascii=False)+'\n')
                            evidence.write(json.dumps(dict(id=row['id'],audit_evidence=row['audit_evidence'],spec_sha256=row['spec_sha256']),ensure_ascii=False)+'\n')
                            counts['rows']+=1;counts['targets']+=sum(m['role']=='assistant' for m in row['messages'])
                            counts['rendered_tokens']+=row['rendered_training_tokens']
            card=(f'---\nlicense: cc-by-nc-sa-4.0\nlanguage:\n- fa\ntask_categories:\n- text-generation\n'
                'configs:\n- config_name: default\n  data_files:\n  - split: train\n    path: data/train.jsonl\n---\n\n'
                f'# {name.replace("_","-")}\n\n{counts["rows"]} source-grounded Persian conversations generated and independently '
                'reviewed with Gemma4 26B A4B. Automated audit is fallible, not certified gold.\n\n'
                f'Derived from [Targoman/TLPC](https://huggingface.co/datasets/{REPO}) at `{REVISION}`. '
                'CC-BY-NC-SA-4.0 source attribution and row URLs are retained. Generated outputs remain '
                'subject to applicable Gemma terms. Full selected source text is included in the first user turn. '
                'No source text is claimed independently verified.\n\n'
                'Train-only. Preserve native Gemma4 messages/history, thinking disabled, no regex fix or truncation. '
                'All assistant turns are training targets. Exact available-reference overlap checks and local normalized '
                'deduplication were performed; full inherited-corpus, evaluation-suite, fuzzy and semantic '
                'decontamination were NOT established. See overlap-policy.json.\n')
            with atomic(folder/'README.md') as out:out.write(card)
            write_json(folder/'overlap-policy.json',dict(**validation['policy'],supplemental=extra))
            access=load('data/dfm13/wave4/tlpc-usability-1791109046036714235/access.json')
            with atomic(folder/'SOURCE_README.md') as out:out.write(Path(access['card_path']).read_text())
            entry=dict(name=name,repo_id=REPO,revision=REVISION,license='cc-by-nc-sa-4.0',repeat=1,
                hf_repo_id='schneiderkamplab/'+folder.name,rows=counts['rows'],training_targets=counts['targets'],
                rendered_tokens=counts['rendered_tokens'],unique_source_documents=len(source_ids),
                expected_target=60000 if family=='grounded-qa' else 40000,excluded=counts['excluded'],
                output=str(output),output_sha256=file_hash(output),publication_contract=CONTRACT,
                target_policy='all_assistant_targets_native_gemma_full_history',
                selection=str(private),selection_sha256=file_hash(private),
                validation_receipt=str(root/'validation.json'),validation_receipt_sha256=file_hash(root/'validation.json'),
                files={str(p.relative_to(folder)):file_hash(p) for p in folder.rglob('*') if p.is_file()},
                automatic_admission=False,certified=False)
            write_json(folder/'manifest.json',entry);packages.append(entry)
    write_json(root/'packages.json',dict(packages=packages,complete=True,scoped_overlap_only=True))
    return packages


def tokenize(root,workers=16):
    from scripts.tokenize_dfm13_nonwave import command, statistics
    root=Path(root).resolve()
    for entry in load(root/'packages.json')['packages']:
        folder=root/'tokenization'/entry['name']; staging=folder/'input';output=folder/'tokens'
        marker=folder/'receipt.json'
        if marker.exists():continue
        staging.mkdir(parents=True,exist_ok=True)
        count=0;handle=None
        try:
            with open(entry['output']) as source:
                for line in source:
                    if count%2000==0:
                        if handle:handle.close()
                        handle=(staging/f'part-{count//2000:06d}.jsonl').open('w')
                    handle.write(line);count+=1
        finally:
            if handle:handle.close()
        with (folder/'tokenize.log').open('a') as log:
            subprocess.run(command(staging,output,workers),stdout=log,stderr=subprocess.STDOUT,check=True)
        completion=load(output/'completion.json');counts=statistics(output)
        if (count!=entry['rows'] or completion['rows']!=entry['training_targets']
                or counts['rows']!=entry['training_targets'] or counts['tokens']!=entry['rendered_tokens']
                or counts['sequences_over_4096'] or completion['skipped_rows_this_run']
                or completion['max_seq_len'] is not None):raise ValueError('Token counts/truncation/target parity failed')
        write_json(marker,dict(source_sha256=entry['output_sha256'],output=str(output),workers=workers,
            regex_fix=False,hard_truncation=False,**counts,
            files={str(p.resolve()):file_hash(p) for p in output.rglob('*') if p.is_file()}))
        print(entry['name'],counts,flush=True)


def publish(root,authorization,registry=Path('config/dfm13_sources.json')):
    from huggingface_hub import HfApi,hf_hub_download
    root=Path(root).resolve();authorization=Path(authorization).resolve();approval=load(authorization)
    if (approval.get('release_sha256')!=file_hash(root/'packages.json')
            or approval.get('allow_scoped_overlap_release') is not True
            or approval.get('upload_and_register') is not True):
        raise ValueError('Explicit hash-bound scoped-coverage release authorization required')
    api=HfApi(token=True)
    for entry in load(root/'packages.json')['packages']:
        name=entry['name'];folder=Path(entry['output']).parent.parent;marker=root/(name+'-published.json')
        tokens=root/'tokenization'/name/'receipt.json';receipt=load(tokens)
        if entry['rows']!=entry['expected_target']:raise ValueError('Post-screen deficit; needs replenishment authorization')
        if receipt['source_sha256']!=file_hash(entry['output']):raise ValueError('Token/source binding failed')
        for rel,sha in entry['files'].items():
            if file_hash(folder/rel)!=sha:raise ValueError('Publication payload drift')
        if marker.exists():
            published=load(marker)
        else:
            api.create_repo(entry['hf_repo_id'],repo_type='dataset',exist_ok=True)
            commit=api.upload_folder(repo_id=entry['hf_repo_id'],repo_type='dataset',folder_path=folder,
                commit_message='Publish user-authorized audited TLPC grounded Persian conversations')
            for relative in ('data/train.jsonl','manifest.json','README.md','SOURCE_README.md','overlap-policy.json'):
                remote=hf_hub_download(entry['hf_repo_id'],relative,repo_type='dataset',revision=commit.oid,token=True)
                if file_hash(remote)!=file_hash(folder/relative):raise ValueError('HF payload verification failed')
            published=dict(entry,hf_revision=commit.oid,uploaded=True,status='accepted_uploaded',publication_status='verified',
                export_manifest=str(folder/'manifest.json'),export_manifest_sha256=file_hash(folder/'manifest.json'),
                release_authorization=str(authorization),release_authorization_sha256=file_hash(authorization),
                tokenization_performed=True,tokenized_path=receipt['output'],tokenized_rows=receipt['rows'],
                tokenized_tokens=receipt['tokens'],tokenization_receipt=str(tokens),tokenization_receipt_sha256=file_hash(tokens))
            write_json(marker,published)
        with lock(registry.with_suffix('.lock')):
            data=load(registry);existing=[e for e in data['additions'] if e['name']==name]
            if existing and existing!=[published]:raise ValueError('Existing TLPC entry differs; no blind overwrite')
            if not existing:data['additions'].append(published);write_json(registry,data)
        print('REGISTERED',name,published['hf_revision'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['merge','tokenize','publish'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--authorization',type=Path)
    p.add_argument('--workers',type=int,default=16);a=p.parse_args()
    if a.command=='merge':print(merge(a.root))
    elif a.command=='tokenize':tokenize(a.root,a.workers)
    else:publish(a.root,a.authorization)
