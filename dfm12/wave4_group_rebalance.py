"""Offline, lossless group-level rebalance of a drained W4 language bundle."""
from contextlib import ExitStack
import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3

from .io import file_hash, load, lock, write_json
from .wave4_shard_prepare import copy_table


def runnable(row):
    return row['accepted'] < row['target'] and row['attempts'] < 6*row['target'] and not row['blocked']


def assign(groups):
    bins = [dict(worker=i, endpoint=f'http://127.0.0.1:{8800+i}/v1',
                 groups=[], runnable_groups=[], estimated_attempts=0) for i in range(8)]
    def cost(row):
        budget = 6*row['target']-row['attempts']
        yield_rate = row['accepted']/max(1,row['attempts'])
        return min(budget, (row['target']-row['accepted'])/max(yield_rate, .0001))
    active = sorted((r for r in groups if runnable(r)), key=lambda r:(-cost(r),r['language'],r['family']))
    if len(active)<8:
        raise ValueError('Fewer than eight runnable groups')
    for row in active:
        shard=min(bins,key=lambda s:(s['estimated_attempts'],s['worker']))
        key=[row['language'],row['family']]
        shard['groups'].append(key);shard['runnable_groups'].append(key)
        shard['estimated_attempts']+=cost(row)
    for row in sorted((r for r in groups if not runnable(r)),key=lambda r:(r['language'],r['family'])):
        shard=min(bins,key=lambda s:(len(s['groups']),s['worker']))
        shard['groups'].append([row['language'],row['family']])
    for shard in bins:
        shard['groups'].sort();shard['runnable_groups'].sort()
        shard['languages']=sorted({k[0] for k in shard['groups']})
    return bins


def scope_group(scope):
    parts=scope.split('/')
    if len(parts)==2 and parts[1]=='openhermes':
        return parts[0],'openhermes'
    if len(parts)==3 and parts[0]==parts[1]:
        return parts[0],parts[2]
    raise ValueError('Unknown source scope: '+scope)


def append_rows(source,dest,table,where,args):
    cursor=source.execute('SELECT * FROM '+table+where,args)
    marks=','.join('?' for _ in cursor.description)
    while rows:=cursor.fetchmany(1000):
        dest.executemany('INSERT INTO '+table+' VALUES ('+marks+')',rows)


def partition(predecessor,output):
    predecessor,output=Path(predecessor).resolve(),Path(output).resolve()
    old=load(predecessor/'prepared.json');source=Path(old['source_root'])
    if output.exists() or output.with_name(output.name+'.preparing').exists():
        raise ValueError('Fresh output required; partial output never auto-reused')
    with ExitStack() as stack:
        stack.enter_context(lock(source/'controller.lock'))
        stack.enter_context(lock(predecessor/'supervisor.lock'))
        for i in range(8):
            stack.enter_context(lock(predecessor/f'shard-{i}'/'controller.lock'))
        return partition_locked(predecessor,output)


def partition_locked(predecessor,output):
    old=load(predecessor/'prepared.json');source=Path(old['source_root'])
    from .wave4_shard_runtime import verify_partition
    for i in range(8):verify_partition(predecessor/f'shard-{i}')
    staging=output.with_name(output.name+'.preparing')
    groups=[]; owners={}; before=dict(jobs=0,selections=0,cursors=0,used_sources=0)
    with ExitStack() as stack:
        ledgers=[];providers=[]
        for i in range(8):
            folder=predecessor/f'shard-{i}'
            db=stack.enter_context(sqlite3.connect((folder/'jobs.sqlite').as_uri()+'?mode=ro',uri=True))
            db.row_factory=sqlite3.Row
            rows=[dict(r) for r in db.execute('SELECT * FROM groups')]
            if any(r['active'] for r in rows) or db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]:
                raise ValueError('Predecessor not fully drained')
            for row in rows:
                key=(row['language'],row['family'])
                if key in owners:raise ValueError('Overlapping predecessor groups')
                owners[key]=i
            groups.extend(rows);ledgers.append(db)
            before['jobs']+=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
            provider=stack.enter_context(sqlite3.connect((folder/'spec-selections.sqlite').as_uri()+'?mode=ro',uri=True))
            providers.append(provider)
            for table in ('selections','cursors','used_sources'):
                before[table]+=provider.execute('SELECT count(*) FROM '+table).fetchone()[0]
        if sum(r['target'] for r in groups)!=770000:raise ValueError('Target drift')
        shards=assign(groups)
        staging.mkdir(parents=True,exist_ok=False)
        write_json(staging/'journal.json',dict(state='preparing',predecessor_root=str(predecessor)))
        with sqlite3.connect((predecessor/'fingerprints.sqlite').as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(staging/'fingerprints.sqlite') as dst:
            src.backup(dst)
            fingerprint_count=src.execute('SELECT count(*) FROM fingerprints').fetchone()[0]
        manifest=load(source/'manifest.json')
        after=dict(jobs=0,selections=0,cursors=0,used_sources=0)
        for shard in shards:
            folder=staging/f"shard-{shard['worker']}";folder.mkdir()
            for name in {'manifest.json','seal.json',*manifest['input_pins']}:
                relative=Path(name)
                if relative.is_absolute() or '..' in relative.parts:raise ValueError('Unsafe input path')
                (folder/relative).parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source/relative,folder/relative)
            with sqlite3.connect(folder/'jobs.sqlite') as db,sqlite3.connect(folder/'spec-selections.sqlite') as provider:
                for table in ('groups','jobs','fingerprints'):copy_table(ledgers[0],db,table,' WHERE 0')
                copy_table(ledgers[0],db,'metadata')
                for table in ('selections','cursors','used_sources'):copy_table(providers[0],provider,table,' WHERE 0')
                copy_table(providers[0],provider,'metadata')
                for language,family in shard['groups']:
                    index=owners[(language,family)];src=ledgers[index];seeds=providers[index]
                    for table in ('groups','jobs'):
                        append_rows(src,db,table,' WHERE language=? AND family=?',(language,family))
                    append_rows(src,db,'fingerprints',' WHERE owner IN (SELECT id FROM jobs WHERE language=? AND family=?)',(language,family))
                    append_rows(seeds,provider,'selections'," WHERE json_extract(spec,'$.language_code')=? AND json_extract(spec,'$.family')=?",(language,family))
                    scopes=[r[0] for r in seeds.execute('SELECT scope FROM cursors') if scope_group(r[0])==(language,family)]
                    for scope in scopes:
                        for table in ('cursors','used_sources'):append_rows(seeds,provider,table,' WHERE scope=?',(scope,))
                db.execute('CREATE INDEX jobs_status ON jobs(status)')
                after['jobs']+=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
                for table in ('selections','cursors','used_sources'):after[table]+=provider.execute('SELECT count(*) FROM '+table).fetchone()[0]
            write_json(folder/'ownership.json',dict(**shard,campaign_root=str(source),registry='../fingerprints.sqlite',launch_authorized=False))
        if before!=after:raise ValueError('Rebalance lost or duplicated rows')
        files={str(p.relative_to(staging)):file_hash(p) for p in staging.rglob('*') if p.is_file() and p.name!='journal.json'}
        totals={k:sum(r[k] for r in groups) for k in ('accepted','target','attempts','active')}
        receipt=dict(version=2,source_root=str(source),predecessor_root=str(predecessor),
            source_manifest_sha256=file_hash(source/'manifest.json'),shards=shards,files=files,
            accepted=totals['accepted'],target=770000,expected_target=770000,preserved_totals=totals,
            preserved_rows=after,global_fingerprints=fingerprint_count,launch_authorized=False,
            automatic_resume=False,snapshot_verification_only=True,
            predecessor_runtime_sha256=file_hash(predecessor/'shard-runtime.json'))
        write_json(staging/'prepared.json',receipt)
        write_json(staging/'journal.json',dict(state='complete',launch_authorized=False))
        os.rename(staging,output)
        return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predecessor',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(partition(args.predecessor,args.output),indent=2))
