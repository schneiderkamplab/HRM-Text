"""Local full-history W4 export/tokenization of originals plus verified supplement."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import FunctionType

from . import baltic_finished_release as retained
from . import wave4_recovery_supplement as recovery
from .wave4_synthetic_specs import audit_record
from .io import atomic,digest,file_hash,load,lock,write_json

CONTRACT='wave4-compact-recovered-full-history-v1'
validate_original=FunctionType(retained.validate.__code__,
    dict(retained.validate.__globals__,audit_record=audit_record),retained.validate.__name__,
    retained.validate.__defaults__,retained.validate.__closure__)


def original_row(item):
    key,fp,outcome,directory=item
    row,pins=validate_original(key,fp,json.loads(outcome),Path(directory))
    return key,fp,row,pins,'original_accepted'


def recovered_row(item):
    root,key,fp,receipt_sha,candidate_sha=item
    receipt=root/'receipts'/f'{key}.json';candidate=root/'accepted'/f'{key}.json'
    if file_hash(receipt)!=receipt_sha or file_hash(candidate)!=candidate_sha:
        raise ValueError('Supplement package drift')
    proof=load(receipt);row=load(candidate)
    if proof['fingerprint']!=fp or digest({k:row[k] for k in ('messages','tools')})!=fp:
        raise ValueError('Supplement fingerprint drift')
    return key,fp,row,{str(receipt):receipt_sha,str(candidate):candidate_sha},'technical_recovery'


def card(folder,name,language,family,count,targets,sources,licenses):
    write_json(folder/'SOURCE_INVENTORY.json',dict(sources=dict(sources),license_labels=dict(licenses),
        source_terms_not_relicensed=True,unknown_license_labels_not_permission=True))
    with atomic(folder/'README.md') as out:
        out.write('---\nlanguage: ['+language+']\ntask_categories: [text-generation]\nconfigs:\n'
            '- config_name: default\n  data_files:\n  - split: train\n    path: data/train.jsonl\n---\n\n# '+name+'\n\n'
            +str(count)+' complete conversations; '+str(targets)+' native assistant targets. '
            'All user/tool history and tool definitions are preserved. Gemma native student rendering, '
            'thinking disabled. Generated and separately model-reviewed by Gemma4 26B A4B; '
            'automated judgments are fallible, not human or native-speaker certification.\n\n'
            'Includes unchanged original accepted conversations and narrowly recovered complete keep '
            'reviews rejected solely for an empty rationale. Recovery revalidated saved raw calls, '
            'sources, untruncated renders and unique fingerprint ownership; no rationale was invented. '
            'No reject, repair, needs-verification or interrupted verdict was promoted.\n\n'
            'See SOURCE_INVENTORY.json and row provenance. Source-specific attribution and terms '
            'remain applicable; this card makes no blanket license grant. HF upload is pending.\n')


def run(bundle,supplement,root):
    from scripts.assemble_dfm13_additions import verify_arrays
    from scripts.tokenize_chat_template import examples_from_messages
    bundle,supplement,root=map(lambda p:Path(p).resolve(),(bundle,supplement,root))
    release=load(supplement/'manifest.json')
    if release['shortfall']!=0 or release['combined']!=790843 or release['languages']['lb']['combined']!=90843:
        raise ValueError('Explicit all-LB completed release required')
    if file_hash(supplement/'supplement.sqlite')!=release['supplement_sha256']:
        raise ValueError('Supplement database drift')
    root.mkdir(parents=True,exist_ok=False)
    manifest=load(bundle/'shard-0/manifest.json')
    source_pins={str(supplement/'manifest.json'):file_hash(supplement/'manifest.json'),
        str(bundle/'terminal.json'):file_hash(bundle/'terminal.json'),
        str(bundle/'prepared.json'):file_hash(bundle/'prepared.json'),
        str(bundle/'shard-runtime.json'):file_hash(bundle/'shard-runtime.json')}
    entries=[];seen=set();exported=0
    with ExitStack() as owners:
        owners.enter_context(lock(root/'.lock'));owners.enter_context(lock(bundle/'supervisor.lock'))
        for i in range(8):owners.enter_context(lock(bundle/f'shard-{i}'/'controller.lock'))
        for i in range(8):
            path=bundle/f'shard-{i}'/'jobs.sqlite';source_pins[str(path)]=file_hash(path)
        write_json(root/'source-proof.json',dict(contract=CONTRACT,pins=source_pins,
            conversations=release['combined'],original=release['original'],recovered=release['recovered'],
            source_ledgers_modified=False,supplement=str(supplement),bundle=str(bundle)))
        with recovery.ro(supplement/'supplement.sqlite') as additions,ThreadPoolExecutor(max_workers=64) as pool:
            for group in sorted(release['groups'],key=lambda g:(g['language'],g['family'])):
                language,family=group['language'],group['family'];count=0;sources=Counter();licenses=Counter()
                expected_targets=expected_tokens=0
                name='dfm13_wave4_synthetic_'+language+'_'+family.replace('-','_')
                folder=root/'packages'/name;(folder/'data').mkdir(parents=True);(folder/'input').mkdir()
                path=folder/'data/train.jsonl';evidence=folder/'accepted-evidence.jsonl';part=None
                with atomic(path) as rows,atomic(evidence) as proofs:
                    def emit(results):
                        nonlocal count,exported,part,expected_targets,expected_tokens
                        for key,fp,row,pins,basis in results:
                            if fp in seen:raise ValueError('Combined duplicate fingerprint')
                            if row['language']!=language or row['family']!=family:raise ValueError('Group mismatch')
                            seen.add(fp);row=dict(row);row.pop('target_message_index',None)
                            expected_targets+=len(list(examples_from_messages(row['messages'],row['tools'])))
                            expected_tokens+=row['rendered_training_tokens']
                            row['id']=digest(dict(campaign=manifest['campaign'],fingerprint=fp))
                            if count%2000==0:
                                if part is not None:part.close()
                                part=(folder/'input'/f'part-{count//2000:06d}.jsonl').open('x')
                            line=json.dumps(row,ensure_ascii=False)+'\n';rows.write(line);part.write(line)
                            proofs.write(json.dumps(dict(id=key,name=name,fingerprint=fp,pins=pins,basis=basis),ensure_ascii=False)+'\n')
                            source=row.get('provenance',{}).get('source') or {}
                            sources[str(source.get('repo',source.get('source','synthetic_reference_or_scenario' if not source else 'unidentified_source')))]+=1
                            licenses[str(source.get('license','not_declared_per_row'))]+=1
                            count+=1;exported+=1
                    try:
                        with recovery.ro(bundle/f"shard-{group['shard']}"/'jobs.sqlite') as jobs:
                            cursor=jobs.execute("SELECT j.id,j.fingerprint,j.outcome_json,j.workdir,f.owner FROM jobs j LEFT JOIN fingerprints f ON j.fingerprint=f.fingerprint WHERE j.status='accepted' AND j.language=? AND j.family=? ORDER BY j.id",(language,family))
                            while batch:=cursor.fetchmany(256):
                                if any(r[0]!=r[4] for r in batch):raise ValueError('Original fingerprint ownership')
                                emit(pool.map(original_row,[tuple(r[:4]) for r in batch]))
                                write_json(root/'progress.json',dict(phase='exporting',conversations=exported,package=name))
                        cursor=additions.execute('SELECT id,fingerprint,receipt_sha256,candidate_sha256 FROM accepted WHERE language=? AND family=? ORDER BY id',(language,family))
                        while batch:=cursor.fetchmany(256):emit(pool.map(recovered_row,[(supplement,*tuple(r)) for r in batch]))
                    finally:
                        if part is not None:part.close()
                if count!=group['combined_accepted']:raise ValueError('Conversation count drift')
                write_json(root/'progress.json',dict(phase='tokenizing',conversations=exported,package=name,workers=16))
                tokens=folder/'tokens'
                subprocess.run([sys.executable,'scripts/tokenize_chat_template.py',str(folder/'input'),'-o',str(tokens),
                    '--tokenizer-path','data/dfm11_tokenizer/tokenizer.json','--chat-template','data/dfm11_tokenizer/chat_template.jinja',
                    '--workers','16'],check=True)
                completion=load(tokens/'completion.json')
                if completion['skipped_rows_this_run'] or completion['max_seq_len'] is not None:raise ValueError('Targets dropped/truncated')
                pins={};parts=[verify_arrays(p,262144,pins) for p in sorted(tokens.iterdir()) if p.is_dir()]
                targets=sum(p['rows'] for p in parts);total=sum(p['tokens'] for p in parts)
                if targets!=expected_targets or total!=expected_tokens:
                    raise ValueError('Full native target/render parity mismatch')
                entry=dict(name=name,language=language,family=family,publication_contract=CONTRACT,
                    status='accepted_local_tokenized',uploaded=False,hf_revision=None,repeat=1,rows=count,
                    training_targets=targets,tokenized_rows=targets,tokenized_tokens=total,
                    output=str(path),output_sha256=file_hash(path),tokenized_path=str(tokens),tokenization_performed=True,
                    evidence=str(evidence),evidence_sha256=file_hash(evidence),source_proof=str(root/'source-proof.json'),
                    source_proof_sha256=file_hash(root/'source-proof.json'),array_pins=pins,
                    target_policy='all_assistant_targets_native_gemma_full_history',publication_pending=True,
                    hf_repo_id=f'schneiderkamplab/dfm13-multilingual-{family}-{language}')
                card(folder,name,language,family,count,targets,sources,licenses)
                write_json(folder/'manifest.json',entry)
                entry.update(export_manifest=str(folder/'manifest.json'),export_manifest_sha256=file_hash(folder/'manifest.json'))
                entries.append(entry);write_json(root/'registry.json',dict(inherits='dfm12',additions=entries))
                print('TOKENIZED',name,count,targets,total,flush=True)
    if exported!=release['combined']:raise ValueError('Combined export count mismatch')
    write_json(root/'complete.json',dict(success=True,conversations=exported,packages=len(entries),
        training_targets=sum(e['training_targets'] for e in entries),tokens=sum(e['tokenized_tokens'] for e in entries),
        registry_sha256=file_hash(root/'registry.json'),uploaded=False,assembly_pending=True))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--supplement',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.bundle,a.supplement,a.output)
