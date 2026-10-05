"""CPU-only TLPC release: strict raw validation, scoped overlap, publication and tokens."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
import json
import multiprocessing
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

from .io import atomic, digest, file_hash, load, lock, write_json
from . import tlpc_grounded_campaign as campaign
from .tlpc_sources import normalize, REPO, REVISION
from .records import chat_fingerprint
from .scandi_overlap import text_hash

CONTRACT = 'tlpc-grounded-audited-v1'
REFERENCE = Path('data/dfm12/european-expansion-20260926/screened')
NAMES = {'grounded-qa':'dfm13_tlpc_grounded_qa_fa', 'grounded-chat':'dfm13_tlpc_grounded_chat_fa'}


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True, timeout=60)


def units(row):
    messages = row['messages']
    plain = [dict(m) for m in messages]
    # Also compare questions without the mechanically prepended source wrapper.
    plain[0]['content'] = plain[0]['content'].rsplit('\n\nپرسش:\n',1)[-1]
    chats = {chat_fingerprint(messages), chat_fingerprint(plain)}
    for i in range(0,len(plain),2):
        chats.add(chat_fingerprint(plain[i:i+2]))
    texts = [row['source']['text'], *[m['content'] for m in plain],
             *[e['text'] for e in row['source']['elements']]]
    return chats, {text_hash(t) for t in texts if len(' '.join(t.split())) >= 160}


def validate_part(args):
    item, destination, reference = args
    client = Path(item['root']); destination = Path(destination)
    marker = destination.with_suffix('.receipt.json')
    if marker.exists():
        receipt = load(marker)
        if receipt['sha256'] != file_hash(destination):
            raise ValueError('Validated part drift')
        return receipt
    manifest = load(client/'manifest.json')
    if file_hash(client/'manifest.json') != item['manifest_sha256']:
        raise ValueError('Client manifest binding failed')
    source_path = Path(manifest['seeds_root'])/'sources.sqlite'
    counts = Counter(); fingerprints = set()
    with readonly(client/'jobs.sqlite') as db, readonly(source_path) as sources, readonly(reference) as refs, atomic(destination) as out:
        for key,spec_json,outcome_json,workdir in db.execute(
                "SELECT id,spec_json,outcome_json,workdir FROM jobs WHERE status='accepted' ORDER BY slot"):
            spec, outcome = json.loads(spec_json), json.loads(outcome_json)
            if (outcome.get('terminal') is not True or outcome.get('effective_keep') is not True
                    or outcome.get('status') != 'valid' or outcome['id'] != key
                    or outcome['spec_sha256'] != digest(spec)):
                raise ValueError('Accepted ledger outcome identity failed')
            stored = sources.execute('SELECT record_json FROM sources WHERE id=?',(spec['source']['id'],)).fetchone()
            if stored is None or json.loads(stored[0]) != spec['source']:
                raise ValueError('Source/spec binding failed')
            row,_ = campaign.validate_saved_keep(Path(workdir),key,spec,outcome)
            owner = db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',(outcome['fingerprint'],)).fetchone()
            if owner != (key,):
                raise ValueError('Missing uniquely owned conversation')
            reasons=[]
            chats,texts=units(row)
            for kind in ('inherited_chat','heldout_chat'):
                if any(refs.execute('SELECT 1 FROM fingerprints WHERE kind=? AND hash=?',(kind,h)).fetchone() for h in chats):
                    reasons.append(kind)
            if any(refs.execute("SELECT 1 FROM fingerprints WHERE kind='heldout_text' AND hash=?",(h,)).fetchone() for h in texts):
                reasons.append('heldout_text')
            fp=digest([(m['role'],normalize(m['content'])) for m in row['messages']])
            if fp in fingerprints:
                reasons.append('normalized_duplicate_within_client')
            fingerprints.add(fp)
            evidence = {}
            for folder,names in [('candidates',[key]),('outcomes',[key]),
                    ('stages',[key+'-generate',key+'-review']),('requests',[key+'-generate',key+'-review'])]:
                for name in names:
                    p=Path(workdir)/folder/(name+'.json');evidence[str(p)]=file_hash(p)
            row.update(id=outcome['fingerprint'], normalized_fingerprint=fp,
                audit_evidence=dict(client=str(client),job=key,files=evidence),
                audit=outcome['audit'], overlap_exclusions=reasons,
                campaign_manifest_sha256=item['manifest_sha256'])
            out.write(json.dumps(row,ensure_ascii=False)+'\n')
            counts['validated']+=1
            counts['excluded' if reasons else 'eligible']+=1
    receipt=dict(client=str(client),family=manifest['family'],counts=dict(counts),
        path=str(destination),sha256=file_hash(destination),manifest_sha256=item['manifest_sha256'])
    write_json(marker,receipt)
    return receipt


def prepare(root, output, workers=16):
    root,output=Path(root).resolve(),Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    with lock(output/'.lock'), ExitStack() as locks:
        manifest=load(root/'campaign.json')
        for item in manifest['clients']:
            locks.enter_context(lock(Path(item['root'])/'controller.lock'))
        for item in manifest['clients']:
            m=campaign.verify(Path(item['root']))
            with readonly(Path(item['root'])/'jobs.sqlite') as db:
                if db.execute('SELECT sum(active),sum(accepted),sum(target) FROM groups').fetchone()!=(0,m['target'],m['target']):
                    raise ValueError('Unfinished task ledger')
        reference_manifest=load(REFERENCE/'reference-inputs.json')
        with readonly(REFERENCE/'overlap.sqlite') as db:
            indexed=dict(db.execute('SELECT path,sha256 FROM files'))
        missing=[r['path'] for r in reference_manifest['files'] if indexed.get(r['path'])!=r['sha256']]
        if missing:
            raise ValueError('Reference index incomplete: '+repr(missing[:3]))
        frozen=output/'reference.sqlite'
        if not frozen.exists():
            with readonly(REFERENCE/'overlap.sqlite') as src, sqlite3.connect(frozen) as dst:
                src.backup(dst)
        reference_hash=file_hash(frozen)
        policy=dict(campaign_sha256=file_hash(root/'campaign.json'),reference_sha256=reference_hash,
            code_sha256=file_hash(__file__),reference_manifest_sha256=file_hash(REFERENCE/'reference-inputs.json'),
            inherited_complete=False,heldout_complete=False,coverage='467 listed reference files; exact chat and long-text checks',
            limitations=reference_manifest['missing_coverage'])
        if (output/'policy.json').exists() and load(output/'policy.json')!=policy:
            raise ValueError('Release preparation inputs changed')
        write_json(output/'policy.json',policy)
        jobs=[(item,str(output/'validated'/(Path(item['root']).name+'.jsonl')),str(frozen)) for item in manifest['clients']]
        results=[]
        with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn')) as pool:
            for result in pool.map(validate_part,jobs):
                results.append(result)
                write_json(output/'progress.json',dict(phase='raw_validation',completed_clients=len(results),results=results,time=time.time()))
                print(result['client'],result['counts'],flush=True)
        write_json(output/'validation.json',dict(complete=True,results=results,policy=policy))
        return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=16)
    a=parser.parse_args()
    if not 1<=a.workers<=16: parser.error('CPU workers1..16')
    prepare(a.root,a.output,a.workers)
