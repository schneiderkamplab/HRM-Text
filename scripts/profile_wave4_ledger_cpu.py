"""Profile reservations on SQLite backups only; never dispatch or recover jobs."""
import argparse
import cProfile
import importlib
import io
from pathlib import Path
import pstats
import sqlite3
import time
from dfm12.io import load,write_json
from dfm12.wave4_batched_runtime import Owner,controller
from dfm12.wave4_ledger_batch import execute_batch


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    m=load(a.root/'manifest.json')
    for name in ('jobs.sqlite','spec-selections.sqlite'):
        with sqlite3.connect((a.root/name).resolve().as_uri()+'?mode=ro',uri=True) as source:
            source.execute('BEGIN')
            source.execute('SELECT name FROM sqlite_master').fetchall()
            with sqlite3.connect(a.output/name) as dest:source.backup(dest,pages=4096,sleep=.01)
        print('backed up',name,flush=True)
    config=load(a.root/'config.json')
    owner=Owner();c=controller(owner)
    ledger=c.Ledger(a.output/'jobs.sqlite')
    ledger.allocated_groups={row['id']:(row['language'],row['family']) for row in
        ledger.db.execute("SELECT id,language,family FROM jobs WHERE status='running'")}
    provider_module=importlib.import_module(m['provider'])
    provider=provider_module.SourceProvider(Path(m['seeds_root']),a.output,config)
    operations=[lambda:ledger.reserve(provider,provider_module.SeedUnavailable,a.output) for _ in range(16)]
    profile=cProfile.Profile();times=[]
    try:
        initial_allocated=len(ledger.allocated_groups)
        for i in range(16):
            start=time.perf_counter();values=execute_batch(ledger,provider,operations)
            times.append(dict(seconds=time.perf_counter()-start,allocated=sum(v is not None for v in values)))
        profile.enable()
        for i in range(8):execute_batch(ledger,provider,operations)
        profile.disable()
        output=io.StringIO();pstats.Stats(profile,stream=output).sort_stats('cumtime').print_stats(35)
        result=dict(original_root=str(a.root.resolve()),clone_root=str(a.output.resolve()),
            original_unchanged=True,requests_sent=0,initial_allocated=initial_allocated,
            unprofiled_batches=times,profile=output.getvalue())
        write_json(a.output/'report.json',result)
        print(output.getvalue(),flush=True)
    finally:provider.close();ledger.close();owner.close()


if __name__=='__main__':main()
