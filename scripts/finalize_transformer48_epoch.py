"""Bind final evaluation metrics to the actual exhausted epoch checkpoint step."""
import json
from pathlib import Path
import sqlite3
import sys

def finalize(db, checkpoint):
    db, checkpoint = Path(db), Path(checkpoint)
    state=json.loads((checkpoint/'checkpoint_state_epoch_1.json').read_text())
    step=int(state['step'])
    with sqlite3.connect(db,timeout=30) as c:
        c.execute('BEGIN IMMEDIATE')
        for jid,definition,status in c.execute('SELECT job_id,definition,status FROM jobs').fetchall():
            row=json.loads(definition);md=json.loads(row['metadata_json'])
            if not md.get('transformer_final_epoch'):continue
            if Path(md['ckpt_path']).resolve() != checkpoint.resolve():continue
            # Control-only rows can finish before training (e.g. unused server
            # teardown). They publish no metrics and must retain their receipts.
            if row['action'] in {'terminal_barrier', 'teardown_eval'}:
                continue
            desired = {'eval_step': step, 'eval_epoch': 1.0, 'xl_boundary': step}
            if all(md.get(k) == v for k, v in desired.items()):
                continue  # Idempotent after evaluations have begun.
            if status != 'pending':
                raise RuntimeError(f'Final evaluation already dispatched: {jid} ({status})')
            md.update(eval_step=step,eval_epoch=1.0,xl_boundary=step)
            row['metadata_json']=json.dumps(md)
            c.execute('UPDATE jobs SET definition=? WHERE job_id=?',(json.dumps(row),jid))
    print('Final epoch metrics bound to actual step',step)

def main():
    finalize(*sys.argv[1:])


if __name__=='__main__':main()
