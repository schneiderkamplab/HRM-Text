"""Eight-case bounded contract/atomic-assertion revision; no bulk handoff."""
import argparse
import asyncio
import fcntl
from pathlib import Path

from scripts import dfm13_repochat_claim_controls as base

ROOT = Path('data/dfm13/repochat-claim-controls-20261001-v2')
ATOMIC_RULES = '''\nEach check must contain ONE atomic proposition. Split compound
claims connected by and/while/therefore into separate checks: evidence for one
clause cannot establish another. In source_fact preserve the relevant complete
declaration or exact operator relationship; do not elide list members with dots
when membership is the disputed fact. For a claimed named re-export, compare the
claimed identifier with each actual exported identifier, not merely the module
path or the fact that some export exists. For mathematical terms, transcribe the
shown expression and compare it literally with the answer before deciding that
the answer is an acceptable overview. Keep each claim and source fact concise,
normally one sentence; do not copy whole paragraphs or functions. Prioritize
material behavior, API relationships, mathematics, security and completeness over
an inventory of descriptive trivia, while still considering the whole answer.
Do not excuse a concrete false relation
because other portions of the answer are correct. If verification cannot be
established from the supplied source, record unsupported, not supported.'''
EMPTY_FINDINGS_RULES = '''\nOutput contract: findings is a list of ACTUAL material
defects. For a supported answer without defects, return "findings": [] exactly.
Never put "None", "N/A", "No issues", or praise in a finding. A finding must name
an actual incorrect/unsupported claim and explain its source conflict or evidence
gap. Use support="sufficient" when the source establishes the answer's material
claims; use "insufficient" for material evidence gaps. Supported correct answers
with minor nonmaterial omissions should have an empty findings list. Do not
manufacture defects to fill the JSON schema. Enumerate material contradictions
in findings instead of contradicting them in rationale. Verify each atomic
proposition independently; related symbol names do not prove claimed relations.'''
ORIGINAL_CHECKED_DOCUMENT = base.checked_document


def checked_document(raw, schema):
    result = ORIGINAL_CHECKED_DOCUMENT(raw, schema)
    if 'findings' in result:
        for finding in result['findings']:
            detail = finding['detail'].strip().lower()
            if not detail or detail in ('none', 'none.', 'n/a', 'no issues', 'no findings') or detail.startswith('none. '):
                raise ValueError('non_actionable_placeholder_finding; not a semantic rejection')
    return result


def prepare(root):
    plan = base.prepare(root)
    if plan.get('experiment') == 'atomic-claims-eight-pairs-v2':
        return plan
    base.b.save(root / 'preserved-full-control-catalog.json', plan)
    plan['controls'] = [c for c in plan['controls'] if any(
        c['id'].startswith('manual-' + prefix) or c['id'] == 'paired-positive-' + prefix for prefix in base.FOUR)]
    if len(plan['controls']) != 8:
        raise ValueError('focused selection drift')
    plan.update(count=8, required_count=8, experiment='atomic-claims-eight-pairs-v2',
                prior_root=str(base.ROOT), automatic_next_stage=False,
                limits='Exposed four defect/repair pairs only; success cannot establish population reliability.')
    plan['pins'].extend([base.old.pin(__file__), base.old.pin(root / 'preserved-full-control-catalog.json')])
    base.b.save(root / 'plan.json', plan)
    return plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--endpoint', default='http://127.0.0.1:8810/v1')
    parser.add_argument('--model', default='dfm13-gemma4')
    parser.add_argument('--concurrency', type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 3:
        parser.error('at most three whole cases')
    # Only this process's imported namespace changes; frozen source files do not.
    base.CLAIM_SYSTEM += ATOMIC_RULES
    base.VERDICT_SYSTEM += EMPTY_FINDINGS_RULES
    base.checked_document = checked_document
    args.root.mkdir(parents=True, exist_ok=True)
    with (args.root / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = prepare(args.root)
        if args.run:
            asyncio.run(base.run(args, plan))
        else:
            print('Prepared eight exposed diagnostic cases; no inference started.')


if __name__ == '__main__':
    main()
