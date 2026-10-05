"""Terminal CPU supplement: all verified LB recoveries, original quotas elsewhere."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
from pathlib import Path
import sqlite3
import time

from . import wave4_recovery_supplement as recovery
from .io import digest,file_hash,load,lock,write_json

POLICY='all-verified-lb-others-original-family-quotas-v1'


def allowance(group, eligible):
    if group['language']=='lb':return eligible
    return max(0,group['target']-group['accepted'])


def package(args):
    release, key, receipt = args
    proof=json.loads(receipt)
    for path,sha in proof['pins'].items():
        if file_hash(path)!=sha:raise ValueError('Saved evidence drift: '+path)
    candidate=load(proof['candidate_path'])
    if digest({k:candidate[k] for k in ('messages','tools')})!=proof['fingerprint']:
        raise ValueError('Candidate fingerprint drift')
    receipt_path=release/'receipts'/f'{key}.json'
    candidate_path=release/'accepted'/f'{key}.json'
    # New isolated artifacts only. Never rewrite original candidate or review.
    for path,value in ((receipt_path,proof),(candidate_path,candidate)):
        if path.exists():
            if load(path)!=value:raise ValueError('Existing release artifact drift')
        else:write_json(path,value)
    return key,proof['fingerprint'],proof['language'],proof['family'],file_hash(receipt_path),file_hash(candidate_path)


def finalize(bundle,preparation,release):
    bundle,preparation,release=map(lambda x:Path(x).resolve(),(bundle,preparation,release))
    initial=load(preparation/'initial.json');prepared=load(preparation/'prepared.json')
    if initial['bundle']!=str(bundle) or file_hash(preparation/'initial.json')!=prepared['initial_sha256']:
        raise ValueError('Preparation binding drift')
    for path,sha in {**initial['pins'],**prepared['result_pins']}.items():
        if file_hash(path)!=sha:raise ValueError('Proof/input drift: '+path)
    with ExitStack() as stack:
        stack.enter_context(lock(bundle/'supervisor.lock'))
        for i in range(8):stack.enter_context(lock(bundle/f'shard-{i}'/'controller.lock'))
        terminal=load(bundle/'terminal.json')
        if terminal.get('active')!=0:raise ValueError('Nonterminal campaign')
        binding=dict(policy=POLICY,bundle=str(bundle),preparation_sha256=file_hash(preparation/'prepared.json'),
            terminal_sha256=file_hash(bundle/'terminal.json'),implementation_sha256=file_hash(__file__))
        if release.exists():
            if load(release/'binding.json')!=binding:raise ValueError('Release resume binding drift')
            if (release/'manifest.json').exists():return load(release/'manifest.json')
        else:
            release.mkdir(parents=True);write_json(release/'binding.json',binding)
        groups=[]
        for i in range(8):
            with recovery.ro(bundle/f'shard-{i}'/'jobs.sqlite') as db:
                if db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]:raise ValueError('Running jobs')
                for r in db.execute('SELECT * FROM groups'):
                    if r['active']:raise ValueError('Active quota')
                    groups.append(dict(r,shard=i))
        if len(groups)!=66 or len({(g['language'],g['family']) for g in groups})!=66:
            raise ValueError('Expected66 distinct groups')
        with sqlite3.connect(release/'supplement.sqlite') as supplement, \
             recovery.ro(bundle/'fingerprints.sqlite') as registry,ThreadPoolExecutor(max_workers=64) as pool:
            supplement.execute('PRAGMA journal_mode=WAL');supplement.execute('PRAGMA synchronous=FULL')
            supplement.execute('CREATE TABLE IF NOT EXISTS accepted(id TEXT PRIMARY KEY,fingerprint TEXT UNIQUE,language TEXT,family TEXT,receipt_sha256 TEXT,candidate_sha256 TEXT)')
            supplement.commit();processed=0
            for g in sorted(groups,key=lambda r:(r['language'],r['family'])):
                i=g['shard'];added=0
                with recovery.ro(preparation/f'shard-{i}.sqlite') as results, \
                     recovery.ro(bundle/f'shard-{i}'/'jobs.sqlite') as jobs:
                    eligible=results.execute('SELECT count(*) FROM results WHERE eligible=1 AND language=? AND family=?',(g['language'],g['family'])).fetchone()[0]
                    limit=allowance(g,eligible)
                    rows=results.execute('SELECT id,receipt,fingerprint FROM results WHERE eligible=1 AND language=? AND family=? ORDER BY id LIMIT ?',
                        (g['language'],g['family'],limit))
                    while batch:=rows.fetchmany(256):
                        work=[]
                        for row in batch:
                            proof=json.loads(row['receipt'])
                            current=jobs.execute('SELECT status,outcome_json FROM jobs WHERE id=?',(row['id'],)).fetchone()
                            owner=registry.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',(row['fingerprint'],)).fetchone()
                            if (current is None or current[0]!='review_invalid_output' or
                                    digest(json.loads(current[1]))!=proof['original_outcome_sha256'] or
                                    owner is None or owner[0]!=row['id']):
                                raise ValueError('Original outcome/global owner drift')
                            work.append((release,row['id'],row['receipt']))
                        for value in pool.map(package,work):
                            prior=supplement.execute('SELECT * FROM accepted WHERE id=?',(value[0],)).fetchone()
                            if prior is not None:
                                if prior!=value:raise ValueError('Supplement row drift')
                            else:supplement.execute('INSERT INTO accepted VALUES(?,?,?,?,?,?)',value)
                            added+=1;processed+=1
                        supplement.commit()
                        write_json(release/'progress.json',dict(policy=POLICY,packaged=processed,
                            group=[g['language'],g['family']],time=time.time(),source_ledgers_unchanged=True))
                    g.update(eligible=eligible,recovered=added,combined_accepted=g['accepted']+added,
                        residual_shortfall=0 if g['language']=='lb' else max(0,g['target']-g['accepted']-added),
                        final_target=g['accepted']+added if g['language']=='lb' else g['target'])
            supplement.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        languages={}
        for g in groups:
            x=languages.setdefault(g['language'],dict(original=0,recovered=0,combined=0,shortfall=0))
            for key,field in [('original','accepted'),('recovered','recovered'),('combined','combined_accepted'),('shortfall','residual_shortfall')]:x[key]+=g[field]
        manifest=dict(version='wave4-terminal-recovery-release-v2',policy=POLICY,groups=groups,languages=languages,
            original=sum(g['accepted'] for g in groups),recovered=sum(g['recovered'] for g in groups),
            combined=sum(g['combined_accepted'] for g in groups),shortfall=sum(g['residual_shortfall'] for g in groups),
            supplement_sha256=file_hash(release/'supplement.sqlite'),binding_sha256=file_hash(release/'binding.json'),
            source_ledgers_unchanged=True,source_outcomes_unchanged=True,new_gpu_calls=0,human_reviewed=False,
            candidate_basis='original-complete-model-keep-with-CPU-proven-technical-schema-recovery',
            requires_combination_with_original_accepted=True)
        write_json(release/'manifest.json',manifest)
        return manifest


def supervise(bundle,preparation,release):
    while True:
        if (bundle/'terminal.json').exists() and (preparation/'prepared.json').exists():
            try:return finalize(bundle,preparation,release)
            except BlockingIOError:pass
        time.sleep(15)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--preparation',type=Path,required=True)
    p.add_argument('--release',type=Path,required=True);a=p.parse_args()
    print(json.dumps(supervise(a.bundle.resolve(),a.preparation.resolve(),a.release.resolve())))
