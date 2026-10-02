"""CPU-authored exact Agnai export correction; separate whole-answer review."""
import argparse
import asyncio
from copy import deepcopy
import fcntl
from pathlib import Path
from types import SimpleNamespace
from scripts import dfm13_repochat_grounded_repairs as p

ROOT=p.ROOT/'agnai-export-cpu-v1'
OLD='Redis clients are constructed in `srv/api/ws/redis.ts` (lines 47-48) and exported through `srv/api/ws/index.ts` (line 2).'
NEW='Redis clients are constructed and exported in `srv/api/ws/redis.ts` (lines 46-49). `srv/api/ws/index.ts:2` re-exports the messaging helpers `sendAll`, `sendGuest`, `sendMany`, `sendOne`, `broadcast`, and `initMessageBus`, not the Redis clients.'


def corrected(answer):
    if answer.count(OLD)!=1:raise ValueError('expected unique exact export wording')
    return answer.replace(OLD,NEW,1)


def prepare():
    receipt_path=p.ROOT/'independent-terminal-review.json';receipt=p.b.load(receipt_path)
    if p.b.file_sha(receipt['packet'])!=receipt['packet_sha256']:raise ValueError('manual packet drift')
    record=next(r for r in receipt['reviews'] if r['task']['repository']=='agnaistic/agnai')
    path=Path(record['trajectory']);snapshot=Path(record['source_snapshot'])
    if p.b.file_sha(path)!=record['trajectory_sha256'] or p.b.file_sha(snapshot)!=record['source_snapshot_sha256']:raise ValueError('reviewed source drift')
    trajectory=p.b.load(path);old=p.answer_of(trajectory)
    if p.b.sha(old.encode())!=record['answer_sha256']:raise ValueError('reviewed answer drift')
    evidence=p.read_evidence(snapshot,[('srv/api/ws/redis.ts',40,16),('srv/api/ws/index.ts',1,8)])
    expected="export { sendAll, sendGuest, sendMany, sendOne, broadcast, initMessageBus } from './redis'"
    if expected not in evidence[1]['text']:raise ValueError('helper exports differ from correction')
    answer=corrected(old);messages=deepcopy(trajectory['messages']);messages[-1]['content']=answer
    key=record['task']['id'];out=ROOT/'trajectories'/key
    p.sealed(ROOT/'ready.json',{'pins':{str(f):p.b.file_sha(f) for f in [receipt_path,path,snapshot,Path(__file__)]},
             'original_answer_sha256':record['answer_sha256'],'draft_answer_sha256':p.b.sha(answer.encode()),'source_reads':evidence,
             'authorship':'CPU source-authored exact localized wording correction; not a fresh teacher generation',
             'original_holds_cleared':False,'mergepath_disposition':'needs_clarification_unchanged','admission':False})
    p.sealed(ROOT/'selection.json',{'tasks':[record['task']],'admission':False})
    p.sealed(out/'trajectory.json',{'task':record['task'],'messages':messages,'record_format':'CPU-authored derivative evidence packet, not native training trajectory','incomplete':False,'admission':False})
    p.sealed(out/'outcome.json',{'status':'cpu_draft_pending_whole_answer_review','answer_sha256':p.b.sha(answer.encode()),'admission':False})
    return key


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    ROOT.mkdir(parents=True,exist_ok=True)
    with (ROOT/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        key=prepare()
        if not args.prepare_only:
            asyncio.run(p.audit.run(SimpleNamespace(source=ROOT,root=ROOT/'whole-answer-review',ids=None,thinking=True)))
            p.b.save(ROOT/'manual-assignment-ready.json',{'trajectory':str(ROOT/'trajectories'/key/'trajectory.json'),'trajectory_sha256':p.b.file_sha(ROOT/'trajectories'/key/'trajectory.json'),'review_sha256':p.b.file_sha(ROOT/'whole-answer-review/summary.json'),'admission':False,'original_holds_cleared':False})
