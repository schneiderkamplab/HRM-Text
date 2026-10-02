"""Explicit generation -> screened candidates -> independent audit handoff."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from .european_expansion import ROOT
from .io import atomic, digest, file_hash, load, lock, write_json
from .jobs import AUDIT_PROMPT, Queue, run_clients
from .prepare import Renderer
from .trustllm import validate_generation


def cpu_ready(root):
    if not load(root / 'text-replenishment/completion.json')['complete']:
        raise ValueError('Transformation preparation incomplete')
    status = load(root / 'screened/status.json')
    if status['stage'] != 'cpu_screening_finished' or status.get('missing'):
        raise ValueError('CPU screening/queueing not finished')
    manifest = load(root / 'screened/audit-manifest.json')
    present = {s['component'] for s in manifest['sources']}
    required = set(load(root / 'english-anchors/manifest.json')['components'])
    cfg = load(root / 'config.json')
    required.update(n for n,s in cfg['sources'].items() if s['kind'] != 'prompts')
    local = root / 'local-integrations.json'
    if local.exists():
        additions = load(local)
        if additions.get('pending'):
            raise ValueError('Local integrations still preparing: ' + str(additions['pending']))
        required.update(additions['components'])
    inventory = load(root / 'opus/inventory.json')['pairs']
    required.update('opus-' + p for p,s in inventory.items() if any(e.get('status') == 'approved' for e in s['corpora']))
    if required - present:
        raise ValueError('Missing screened components: ' + str(sorted(required-present)))
    return manifest


def materialize(root):
    """Freeze terminal generations as ordinary candidates, never raw audit jobs."""
    cfg = load(root / 'config.json')
    queue = Queue(root / 'trustllm.sqlite')
    try:
        status = queue.status()
        if any(s['stage'] == 'generate' and s['status'] not in ('done','failed') for s in status):
            raise ValueError('Generation still pending/running')
        signature = digest(list(queue.db.execute("SELECT id,status,result FROM jobs WHERE stage='generate' ORDER BY id")))
        marker = root / 'trustllm-candidates.json'
        with lock(root / '.trustllm-materialize.lock'):
            if marker.exists():
                if load(marker)['generation_signature'] != signature:
                    raise ValueError('Frozen generations changed')
                return
            renderer = Renderer(load('data/sampled_dfm11/metadata.json')['tokenizer_info'], cfg['max_seq_len'])
            groups = defaultdict(list)
            rejected = Counter()
            for key,payload,result in queue.completed('generate'):
                record = dict(payload['record'])
                try:
                    record['messages'] = validate_generation(record,result)
                    record['rendered_tokens'] = renderer.count(record['messages'])
                except ValueError as exc:
                    rejected[str(exc)] += 1
                    write_json(root/'trustllm-rejected'/(key+'.json'),dict(reason=str(exc),record=record,result=result))
                    continue
                groups[record['component']].append(record)
            for component,records in groups.items():
                folder = root/'candidates'/component
                with lock(folder/'.lock'):
                    with atomic(folder/'candidates.jsonl') as output:
                        for record in records:
                            output.write(json.dumps(record,ensure_ascii=False)+'\n')
                    write_json(folder/'receipt.json',dict(component=component,sha256=file_hash(folder/'candidates.jsonl'),
                        generation_signature=signature,counts=dict(candidates=len(records)),accepted=False))
            write_json(marker,dict(components=sorted(groups),generation_signature=signature,rejected=dict(rejected),queue_status=status))
    finally:
        queue.close()


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('stage',choices=['check','generate','materialize','audit'])
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--endpoint',action='append',default=[])
    p.add_argument('--concurrency',type=int,default=64)
    p.add_argument('--reviewer-approval',type=Path)
    args = p.parse_args()
    if args.stage == 'check':
        print(json.dumps(dict(ready=True,components=len(cpu_ready(args.root)['sources']))))
    elif args.stage == 'generate':
        cpu_ready(args.root)
        run_clients(args.root/'trustllm.sqlite','generate',args.endpoint,args.concurrency)
    elif args.stage == 'materialize':
        materialize(args.root)
        from .european_screen import run
        run(args.root)
    else:
        cpu_ready(args.root)
        generated = load(args.root/'trustllm-candidates.json')
        manifest = load(args.root/'screened/audit-manifest.json')
        if set(generated['components']) - {s['component'] for s in manifest['sources']}:
            raise ValueError('Generated conversations have not passed CPU screening')
        cfg = load(args.root/'config.json')
        if not args.reviewer_approval:
            raise ValueError('Reviewer calibration approval required; no GPU requests sent')
        approval = load(args.reviewer_approval)
        if (approval.get('approved') is not True or approval.get('model') != cfg['model']
                or approval.get('audit_prompt_sha256') != digest(AUDIT_PROMPT)
                or set(cfg['languages']) - set(approval.get('languages',[]))):
            raise ValueError('Reviewer approval does not cover the model, prompt and all languages')
        evidence = Path(approval['evidence_path'])
        if file_hash(evidence) != approval['evidence_sha256']:
            raise ValueError('Reviewer evidence changed')
        run_clients(args.root/'screened/jobs.sqlite','audit',args.endpoint,args.concurrency)


if __name__ == '__main__':
    main()
