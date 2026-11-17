"""Detached stage driver; credential crosses an anonymous pipe, never a file."""
import argparse
import asyncio
import getpass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import httpx

from audit_pipeline.runtime import run, EndpointUnavailable
from scripts.dfm16_story_calibration import FocusedAudit
from scripts.run_dfm16_odin_judge import RateLimitedClient
from scripts.queue_dfm16_stories_qwen import prepare_stage

from dfm12.io import file_hash, load, lock, rows, write_json
from scripts.dfm16_story_calibration import (
    ROOT, MODELS, execute, report, verify, immutable, prepare_repair,
    repaired_checks, repair_report, freeze, validation,
)
from scripts.queue_dfm16_stories_qwen import audited_records


def reuse_votes(root, previous):
    """Reuse only identical focused checks, models, prompts and verdict contract."""
    for key in ('rubric', 'criteria', 'models', 'retries'):
        if load(root/'design.json')[key] != load(previous/'design.json')[key]:
            raise ValueError('Cannot reuse changed judging contract')
    target, source = root/'development', previous/'development'
    if file_hash(target/'checks.jsonl') != file_hash(source/'checks.jsonl'):
        raise ValueError('Cannot reuse changed checks')
    for name in ('qwen27b','flash'):
        old = source/'votes'/name
        complete = (old/'audit/pipeline/state.json').exists() and load(old/'audit/pipeline/state.json').get('phase')=='complete'
        if complete: list(audited_records(old))
        elif load(previous/'campaign.json').get('phase')!='failed':
            raise ValueError('Never copy a live journal')
        new = target/'votes'/name
        pin = dict(sha256=file_hash(target/'checks.jsonl'), design_sha256=file_hash(root/'design.json'))
        if (new/'reuse.json').exists() and load(new/'reuse.json').get('source') != str(old):
            if (new/'upstream-reuse.json').exists():
                raise ValueError('Conflicting imported lineage')
            (new/'reuse.json').rename(new/'upstream-reuse.json')
        if not (new/'reuse.json').exists():
            # Keep original immutable artifacts at their original paths; import
            # complete receipts only, not a running journal or a partial copy.
            new.mkdir(parents=True, exist_ok=True)
            for path in old.iterdir():
                if path.name in ('input-pin.json','reuse.json','upstream-reuse.json'):
                    continue
                dest = new/path.name
                if path.is_dir(): shutil.copytree(path,dest,dirs_exist_ok=True)
                else: shutil.copy2(path,dest)
            immutable(new/'input-pin.json',pin)
            immutable(new/'reuse.json',dict(source=str(old), source_design_sha256=file_hash(previous/'design.json'),
                original_checks_sha256=file_hash(source/'checks.jsonl'), complete=complete, reason='Local Qwen/Flash judging payloads unchanged. Remote Odin protocol corrected and rerun separately.'))
        if complete: list(audited_records(new))


class BoundedOdin(FocusedAudit):
    @staticmethod
    def parse_review(body):
        result=FocusedAudit.parse_review(body)
        usage=body.get('usage',{})
        if usage.get('completion_tokens',0)>32 or usage.get('completion_tokens_details',{}).get('reasoning_tokens',0)>1:
            raise ValueError('Provider completion/one-token reasoning-metadata bound exceeded')
        return result


async def capped_odin(root, repaired=False):
    """Same adapter/runtime, lower API request budget after provider TPM exhaustion."""
    verify(root)
    stage=root/'development'
    output=stage/('repaired' if repaired else 'votes')/'odin'
    state=output/'audit/pipeline/state.json'
    if state.exists() and load(state).get('phase')=='complete':
        list(audited_records(output));return
    source=stage/('repaired-checks.jsonl' if repaired else 'checks.jsonl')
    immutable(output/'input-pin.json',dict(sha256=file_hash(source),design_sha256=file_hash(root/'design.json')))
    prepare_stage(output,rows(source),'context_calibration_v1')
    immutable(output/'transport-budget.json',dict(concurrency=64,requests_per_rolling_minute=100,
        ceiling=100,reason='User hard cap 100/minute. Correct provider reasoning_effort=none and max_completion_tokens=32; old Odin votes are not reused.'))
    model,endpoint=MODELS['odin']
    started=time.monotonic()
    for session in range(4):
        adapter=BoundedOdin(output,output/'audit',endpoint);adapter.model=model
        async with RateLimitedClient(64,100,60,headers={'Authorization':'Bearer '+os.environ['ODIN_API_KEY']},
                timeout=180,trust_env=False,limits=httpx.Limits(max_connections=64)) as client:
            await asyncio.sleep(60)  # new session clears prior dispatch window
            if not (output/'preflight.json').exists():
                first=next(rows(source))
                response=await client.post(endpoint+'/chat/completions',json=adapter.prepare(first))
                response.raise_for_status()
                body=response.json()
                write_json(output/'preflight-response.json',body)
                verdict=adapter.parse_review(body)
                usage=body.get('usage',{})
                if usage.get('completion_tokens_details',{}).get('reasoning_tokens',0)>1 or usage.get('completion_tokens',0)>32:
                    raise ValueError('Provider did not honor non-thinking completion bound')
                write_json(output/'preflight.json',dict(response=body,verdict=verdict,protocol='reasoning_effort_none_max_completion_tokens_32'))
            try:
                await run(adapter,endpoint,64,client=client,prefetch=1)
            except EndpointUnavailable:
                if session==3: raise
                continue  # preserve journals; only uncommitted rows resume
        for chunk in load(output/'manifest.json')['chunks']:
            adapter.verify_receipt(chunk,output/'audit'/chunk['job_id'])
        write_json(state,dict(phase='complete'))
        write_json(output/'timing.json',dict(seconds=time.monotonic()-started,
            note='Resumed-session wall time only; original partial-stage elapsed retained in imported live telemetry.'))
        return


def stage(root, phase, **extra):
    write_json(root/'campaign.json',dict(phase=phase,pid=os.getpid(),production_authorized=False,**extra))


def work(root, previous, do_repairs):
    key = sys.stdin.readline().rstrip('\n')
    if not key:
        raise ValueError('Missing credential')
    os.environ['ODIN_API_KEY'] = key
    verify(root)
    stage(root,'waiting_for_blind_labels')
    while not (root/'development/labels-receipt.json').exists():
        time.sleep(2)
    if previous:
        stage(root,'waiting_for_previous_vote_receipts')
        for name in ('qwen27b','flash'):
            path=previous/'development/votes'/name/'audit/pipeline/state.json'
            while not path.exists() or load(path).get('phase')!='complete':
                if load(previous/'campaign.json').get('phase')=='failed': break
                time.sleep(5)
    with lock(root/'.controller.lock'):
        if previous:
            reuse_votes(root,previous)
        for name in ('qwen27b','flash','odin'):
            stage(root,'judging',judge=name)
            asyncio.run(capped_odin(root) if name=='odin' else execute(root,'development',name))
        value=report(root,'development')
        selected=value['selected_development_policy']
        stage(root,'development_complete',selected_policy=selected)
        if do_repairs:
            prepare_repair(root,'development')
            stage(root,'repair_generation',selected_policy=selected)
            asyncio.run(execute(root,'development','flash',repair=True))
            repaired_checks(root,'development')
            for name in ('qwen27b','odin'):
                stage(root,'repair_audit',judge=name,selected_policy=selected)
                asyncio.run(capped_odin(root,repaired=True) if name=='odin' else execute(root,'development',name,repaired=True))
            stage(root,'awaiting_blind_repair_labels',selected_policy=selected)
            label_path=root/'development/repair-reviewed.jsonl'
            while not label_path.exists():
                time.sleep(2)
            repair_report(root,'development',label_path)
        if selected:
            freeze(root)
            validation(root)
            stage(root,'awaiting_blind_validation_labels',selected_policy=selected)
        else:
            stage(root,'development_failed_targets',selected_policy=None,repairs_complete=do_repairs)
    os.environ.pop('ODIN_API_KEY',None)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--reuse-votes-from',type=Path)
    parser.add_argument('--repairs',action='store_true')
    args=parser.parse_args()
    if args.worker:
        try:
            work(args.root,args.reuse_votes_from,args.repairs)
        except BaseException as exc:
            write_json(args.root/'campaign.json',dict(phase='failed',error_type=type(exc).__name__,reason=str(exc) if isinstance(exc,ValueError) else 'See stage receipts; provider exception bodies omitted.',production_authorized=False))
            raise SystemExit(type(exc).__name__)
        return
    key=getpass.getpass('Odin credential (hidden): ')
    command=[sys.executable,'-m','scripts.run_dfm16_context_calibration','--worker','--root',str(args.root)]
    if args.reuse_votes_from: command += ['--reuse-votes-from',str(args.reuse_votes_from)]
    if args.repairs: command += ['--repairs']
    with (args.root/'campaign.log').open('a') as log:
        p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,text=True)
        p.stdin.write(key+'\n');p.stdin.close()
    print('Detached campaign PID',p.pid)


if __name__=='__main__':
    main()
