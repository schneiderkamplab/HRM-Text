"""CPU-only frozen accepted Baltic conversations, full-history native target arrays."""
import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

from .io import atomic, digest, file_hash, load, lock, write_json
from . import compact_keep_rationale as review
from .baltic_synthetic_specs import audit_record

CONTRACT = 'baltic-compact-accepted-full-history-v1'


def validate(key, fingerprint, outcome, directory):
    from .multilingual_calibration_v6 import strict_json
    if outcome.get('effective_keep') is not True or outcome.get('terminal') is not True:
        raise ValueError('Nonaccepted outcome')
    candidate_path = directory/'candidates'/f'{key}.json'
    candidate = load(candidate_path)
    if digest({k:candidate[k] for k in ('messages','tools')}) != fingerprint or outcome['fingerprint'] != fingerprint:
        raise ValueError('Candidate fingerprint mismatch')
    stage_path = directory/'stages'/f'{key}-review.json'
    stage = load(stage_path)
    if stage['raw']['finish_reason'] != 'stop' or strict_json(stage['raw']['content']) != stage['output']:
        raise ValueError('Incomplete/inconsistent raw review')
    pins = {str(p.resolve()):file_hash(p) for p in (candidate_path,stage_path)}
    if stage['status'] != 'complete':
        recovery = Path(outcome['technical_recovery_receipt'])
        if file_hash(recovery) != outcome['technical_recovery_sha256']:
            raise ValueError('Recovery receipt mismatch')
        proof = load(recovery)
        if proof['fingerprint'] != fingerprint: raise ValueError('Recovery candidate mismatch')
        for path,sha in proof['pins'].items():
            if file_hash(path) != sha: raise ValueError('Recovered evidence changed')
        pins[str(recovery.resolve())] = file_hash(recovery)
    if not review.keeps(stage['output'], audit_record(candidate)):
        raise ValueError('Compact/deterministic review fails')
    accepted = load(directory/'accepted'/f'{key}.json')
    if any(accepted[k] != candidate[k] for k in ('messages','tools','provenance')):
        raise ValueError('Materialized conversation differs')
    return accepted,pins


def run(source, root):
    from scripts.assemble_dfm13_additions import verify_arrays
    root.mkdir(parents=True,exist_ok=False)
    with lock(root/'.lock'), lock(source/'controller.lock'):
        snapshot = root/'accepted-snapshot.sqlite'
        with closing(sqlite3.connect((source/'jobs.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as src:
            if src.execute('SELECT sum(active),sum(accepted),sum(target) FROM groups').fetchone() != (0,140000,140000):
                raise ValueError('Baltic campaign not complete')
            with closing(sqlite3.connect(snapshot)) as dst: src.backup(dst)
        write_json(root/'source-proof.json',dict(database_sha256=file_hash(snapshot),
            source_root=str(source.resolve()), manifest_sha256=file_hash(source/'manifest.json'),
            source_ledger_modified=False, expected_conversations=140000))
    handles={};counts=Counter();seen=set();evidence_path=root/'accepted-evidence.jsonl'
    try:
        with closing(sqlite3.connect(snapshot.resolve().as_uri()+'?mode=ro',uri=True)) as db, atomic(evidence_path) as evidence:
            for key,language,family,fingerprint,encoded,directory in db.execute(
                    "SELECT id,language,family,fingerprint,outcome_json,workdir FROM jobs WHERE status='accepted' ORDER BY language,family,id"):
                if fingerprint in seen: raise ValueError('Duplicate accepted fingerprint')
                seen.add(fingerprint)
                row,pins=validate(key,fingerprint,json.loads(encoded),Path(directory))
                name='dfm13_baltic_synthetic_'+language+'_'+family.replace('-','_')
                folder=root/'packages'/name
                if name not in handles:
                    (folder/'data').mkdir(parents=True)
                    handles[name]=(folder/'data/train.jsonl').open('w')
                # Native tokenizer expands every assistant target; original conversation remains intact.
                row.pop('target_message_index',None)
                handles[name].write(json.dumps(row,ensure_ascii=False)+'\n')
                evidence.write(json.dumps(dict(id=key,name=name,fingerprint=fingerprint,pins=pins),ensure_ascii=False)+'\n')
                counts[name]+=1
                if sum(counts.values())%1000==0:
                    write_json(root/'progress.json',dict(phase='exporting',conversations=sum(counts.values())))
                    print('EXPORTED',sum(counts.values()),flush=True)
    finally:
        for handle in handles.values():handle.close()
    if sum(counts.values())!=140000: raise ValueError('Accepted quota mismatch')
    entries=[]
    for name,count in sorted(counts.items()):
        folder=root/'packages'/name;path=folder/'data/train.jsonl';stage=folder/'input';stage.mkdir()
        with path.open() as stream:
            part=0
            while True:
                lines=[]
                for _ in range(2000):
                    line=stream.readline()
                    if not line:break
                    lines.append(line)
                if not lines:break
                with atomic(stage/f'part-{part:06d}.jsonl') as out:out.writelines(lines)
                part+=1
        tokens=folder/'tokens'
        subprocess.run([sys.executable,'scripts/tokenize_chat_template.py',str(stage),'-o',str(tokens),
            '--tokenizer-path','data/dfm11_tokenizer/tokenizer.json','--chat-template','data/dfm11_tokenizer/chat_template.jinja',
            '--workers','16'],check=True)
        completion=load(tokens/'completion.json')
        if completion['skipped_rows_this_run'] or completion['max_seq_len'] is not None:
            raise ValueError('Native targets dropped/truncated')
        pins={};parts=[verify_arrays(p,262144,pins) for p in sorted(tokens.iterdir()) if p.is_dir()]
        target_count=sum(p['rows'] for p in parts);total=sum(p['tokens'] for p in parts)
        entry=dict(name=name,publication_contract=CONTRACT,status='accepted_local_tokenized',uploaded=False,
            hf_revision=None,repeat=1,rows=count,training_targets=target_count,tokenized_rows=target_count,
            tokenized_tokens=total,output=str(path.resolve()),output_sha256=file_hash(path),
            tokenized_path=str(tokens.resolve()),tokenization_performed=True,
            evidence=str(evidence_path.resolve()),evidence_sha256=file_hash(evidence_path),
            source_proof=str((root/'source-proof.json').resolve()),source_proof_sha256=file_hash(root/'source-proof.json'),
            target_policy='all_assistant_targets_native_gemma_full_history',publication_pending=True)
        write_json(folder/'manifest.json',entry);entry['export_manifest']=str((folder/'manifest.json').resolve())
        entry['export_manifest_sha256']=file_hash(folder/'manifest.json');entries.append(entry)
        write_json(root/'registry.json',dict(inherits='dfm12',additions=entries))
        print('TOKENIZED',name,count,target_count,total,flush=True)
    write_json(root/'complete.json',dict(success=True,conversations=140000,packages=len(entries),
        training_targets=sum(e['training_targets'] for e in entries),tokens=sum(e['tokenized_tokens'] for e in entries),
        uploaded=False,assembly_pending=True))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.source,a.output)
