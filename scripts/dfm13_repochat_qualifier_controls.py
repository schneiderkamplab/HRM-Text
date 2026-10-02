"""Targeted qualifier diagnostics followed by preserved full regression controls."""
import argparse
import asyncio
from copy import deepcopy
import fcntl
from pathlib import Path

from scripts import dfm13_repochat_answer_verdict_probe as prior

base = prior.base
ROOT = Path('data/dfm13/repochat-qualifier-controls-20261001-v1')
RULES = '''
Perform a counterexample check for each material behavioral claim. Identify the
actor, trigger, timing, preconditions and guarantees claimed by the answer, then
compare those with the complete supplied source, including subsequent caveats.
If the source permits even one documented delay, refusal, priority dependency,
validation failure or exception, an unconditional immediate/always/guaranteed
claim is false. "As soon as possible" is not "immediately": a request can be
queued or deferred. Intended schema conformance is not guaranteed valid data.
Do not excuse these differences as ordinary paraphrase when they change what a
caller can rely on. Conversely, an answer explicitly preserving the relevant
condition or limitation is not defective merely because it is concise. Do not
demand irrelevant qualifications. Record the specific answer assertion and the
source exception in an incorrect finding when they materially conflict. Treat
minor overview omissions and genuinely ambiguous questions separately from false
operational guarantees. Apply this check to every repository without assumptions
about its identity. Never infer that absence of evidence proves impossibility.
'''
ORIGINAL_REQUEST = base.request


def records():
    saved = base.b.load(base.ROOT / 'plan.json')
    for pin in saved['pins']:
        base.old.checked_hash(pin)
    full = deepcopy(saved['controls'])
    positive = next(c for c in full if c['id'] == 'paired-positive-fcc0a2368c6e')
    negative = next(c for c in full if c['id'].startswith('manual-fcc0a2368c6e'))
    targeted = [deepcopy(negative), deepcopy(positive)]
    for label, answer in [
        (False, 'An action request always executes immediately, even while the AI is speaking; priority cannot delay execution.'),
        (True, 'An action request asks for execution as soon as possible, but execution can wait while the AI is speaking, depending on priority.')]:
        item = deepcopy(positive)
        item.update(id='explicit-timing-' + str(label), expected_pass=label,
                    control_provenance='Exposed CPU-authored timing pair; not independent heldout')
        item['package']['original_request'] = 'Does an action request guarantee immediate execution, including while the AI is speaking?'
        item['package']['final_answer'] = answer
        targeted.append(item)
    return targeted, full


async def request(client, payload, path):
    if path.stem == 'verdict':
        payload = prior.verdict_payload(payload)
        payload['messages'][0]['content'] += RULES
    return await ORIGINAL_REQUEST(client, payload, path)


def prepare(root, controls, phase):
    path = root / 'plan.json'
    if path.exists():
        plan = base.b.load(path)
        for pin in plan['pins']:
            base.old.checked_hash(pin)
        if plan['controls'] != controls:
            raise ValueError('control catalog drift')
        return plan
    plan = dict(controls=controls, count=len(controls),
                required_count=sum(c['gate_required'] for c in controls),
                phase=phase, automatic_pilot=False, admission=False,
                pins=[base.old.pin(p) for p in [Path(__file__), Path(prior.__file__),
                    Path(base.__file__), Path(prior.previous.__file__), base.ROOT / 'plan.json']])
    root.mkdir(parents=True, exist_ok=True)
    base.b.save(path, plan)
    return plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--endpoint', default='http://127.0.0.1:8810/v1')
    parser.add_argument('--model', default='dfm13-gemma4')
    parser.add_argument('--concurrency', type=int, default=3)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 3:
        parser.error('maximum three whole cases')
    base.CLAIM_SYSTEM += prior.previous.ATOMIC_RULES + RULES
    base.checked_document = prior.previous.checked_document
    base.request = request
    args.root.mkdir(parents=True, exist_ok=True)
    with (args.root / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        targeted, full = records()
        for phase, cases in [('targeted', targeted), ('regression', full)]:
            phase_args = deepcopy(args)
            phase_args.root = args.root / phase
            plan = prepare(phase_args.root, cases, phase)
            if args.run:
                asyncio.run(base.run(phase_args, plan))
                completion = base.b.load(phase_args.root / 'completion.json')
                if completion['completed'] != completion['total']:
                    return  # Graceful drain must not start another phase.


if __name__ == '__main__':
    main()
