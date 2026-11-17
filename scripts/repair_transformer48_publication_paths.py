"""Restore cloned artifact paths without changing a running trainer or rerunning inference."""
import json, sqlite3, time
from pathlib import Path
from prepare_transformer48_eval_plan import ROOT, DB, PLAN, replace, ARTIFACT_NAMESPACE_PAIRS


def link_artifacts(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = destination / item.name
        if target.exists() or target.is_symlink():
            if target.resolve() == item.resolve():
                continue
            if item.is_dir() and target.is_dir():
                # Never add another shard's files through a symlink into its peer.
                if target.is_symlink():
                    previous = target.resolve()
                    target.unlink()
                    target.mkdir()
                    link_artifacts(previous, target)
                link_artifacts(item, target)
            elif item.name.endswith('.log'):
                # Shared logs are not merge inputs; retain original receipt logs.
                continue
            else:
                raise RuntimeError(f'Artifact collision: {target}')
        else:
            target.symlink_to(item.resolve(), target_is_directory=item.is_dir())


def main():
    source=sqlite3.connect('file:/tmp/dfm15-B-production/jobs.sqlite?mode=ro',uri=True)
    originals={jid:log for jid,log in source.execute("select job_id,log_dir from jobs where job_id like 'b-dfm15-1500000-%'")}
    c=sqlite3.connect(DB,timeout=60)
    backup=sqlite3.connect(str(DB)+f'.before-publication-repair-{int(time.time())}')
    c.backup(backup);backup.close()
    c.execute('begin immediate')
    assert c.execute('select locked from administration where singleton=1').fetchone()[0]==0
    c.execute('update administration set locked=1 where singleton=1');c.commit()
    changes=[]
    try:
        rows=c.execute('select job_id,definition,log_dir,status from jobs').fetchall()
        for jid,raw,old,status in rows:
            if jid.endswith('-train'):continue
            d=json.loads(raw);tag=jid.split('-eval-',1)[0].removeprefix('transformer48-')
            prefix=f'transformer48-{tag}'
            original=jid.replace(prefix,'b-dfm15-1500000',1)
            assert original in originals,original
            new=replace(originals[original],[('b-dfm15-1500000',prefix),('B_dfm15_gemma4','transformer48_dfm11_causal'),('step_1500000',tag),('logs/scheduler/transformer48_dfm11_causal_epoch1_20261103',str(PLAN.relative_to(ROOT)))])
            new=replace(new,ARTIFACT_NAMESPACE_PAIRS)
            assert 'B_dfm15' not in new and '1500000' not in new
            assert status!='running',jid
            # Preserve completed artifacts and historical logs. Symlink individual
            # entries so many standard shards can share their canonical directory.
            oldpath=Path(old);newpath=Path(new)
            if oldpath.exists() and any(oldpath.iterdir()):
                link_artifacts(oldpath,newpath)
            changes.append((new,jid,json.dumps({**d,"metadata_json":json.dumps(replace(json.loads(d["metadata_json"]),ARTIFACT_NAMESPACE_PAIRS))})))
        c.execute('begin immediate')
        for new,jid,definition in changes:
            result=c.execute("update jobs set log_dir=?,definition=? where job_id=? and status!='running'",(new,definition,jid))
            assert result.rowcount==1
        c.execute("update jobs set status='pending',attempt=0,token=null where status='failed' and job_id like 'transformer48-step_50000-%'")
        c.commit()
        print(f'Repaired {len(changes)} artifact paths; retried failed 50K publication rows.')
    finally:
        c.rollback();c.execute('update administration set locked=0 where singleton=1');c.commit()

if __name__=='__main__':main()
