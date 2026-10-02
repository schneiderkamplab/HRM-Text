"""Bounded, separately sealed re-audit of 117 invalid responses and 12 controls."""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path

BASE_PATH = Path(__file__).with_name('dfm13_arena_audit.py')
VERSION = 'dfm13-arena-audit-followup-v3'
ADDENDUM = """
Before choosing a disposition, check each MATERIAL claim against the actual
request and visible evidence, not the answer's polish. In particular check:
- Claims about internal processing, training-data lookup, identity or performed
  actions: user assertions and earlier assistant assertions are NOT evidence.
- A correction must remove the original misconception throughout its answer;
  an apology followed by a new unsupported explanation is not a clean correction.
- Check whether a proposed puzzle rule explains ALL supplied examples. Ambiguity
  is not permission to assert one unsupported solution as established.
- Check code preconditions and object/API construction, not just conceptual prose.
- Essential dated prices, counts and obscure product/bibliographic claims need
  evidence. Lack of recall NEVER establishes nonexistence or falsity. Do not claim
  a search, execution or documentation check that you have not performed.
- Do not certify regulatory compliance from polished boilerplate. Check material
  omissions relative to the task, but do not invent extra user requirements.

Output a concise final audit, not deliberation or repeated self-correction.
For each issue, copy ONE SHORT EXACT substring, preferably 20-100 characters,
from the TARGET text (a shorter exact span is fine for a short target). Preserve
case, punctuation and whitespace. No paraphrases, ellipses, normalized markdown,
or joined excerpts. Set message_index to the supplied target_message_index,
NOT a one-based turn number. Discuss earlier context in evidence, but anchor the
issue to the target. Explain omissions using an exact relevant target span.

Use at most four issues, each with a short evidence explanation.
FINAL FIELD CHECK: include ALL six fields, including issues and repair_plan.
keep: issues=[] unless minor caveats; repair_plan=""; verification=none/empty.
repair: at least one exact issue, nonempty repair_plan, verification=none/empty.
reject: at least one exact issue, repair_plan="", verification=none/empty.
needs_verification: at least one exact issue with basis=unverified, repair_plan="",
and one essential bounded verification question plus required evidence.
If a verification question is essential to deciding quality, choose
needs_verification rather than confidently declaring its unverified premise false.
If a visible defect already justifies repair/reject, explain that defect and leave
verification empty. No disposition quotas; uncertainty is not automatically wrong.
Use category=language for language issues, never basis=language. Basis must be
conversation, logical_check, general_knowledge, or unverified.
"""


def engine(followup=True):
    spec = importlib.util.spec_from_file_location('_arena_followup_private', BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if followup:
        module.VERSION = VERSION
        module.RUBRIC += ADDENDUM
    return module


def select(base, source):
    manifest, items = base.verify(source)
    chosen, pins = [], {}
    failures = controls = 0
    for item in items:
        path = base.outcome_path(source, item)
        outcome = base.load(path)
        pins[str(path.resolve())] = base.file_hash(path)
        if outcome['status'] not in ('complete', 'invalid_response'):
            raise ValueError('Source must be terminal without infrastructure uncertainty')
        control = item['exposed_manual_control']
        failed = outcome['status'] == 'invalid_response'
        controls += control
        failures += failed
        if control or failed:
            chosen.append(dict(item, prior_status=outcome['status'],
                               prior_outcome_sha256=base.file_hash(path)))
    if (len(chosen), failures, controls) != (129, 117, 12):
        raise ValueError('Expected exactly 117 invalids plus 12 controls, no overlap')
    return manifest, chosen, pins


def prepare(root, source):
    base = engine(False)
    root, source = Path(root).resolve(), Path(source).resolve()
    with base.lock(root/'controller.lock'):
        if any(p.name != 'controller.lock' for p in root.iterdir()):
            raise ValueError('Fresh follow-up root required')
        old, items, outcome_pins = select(base, source)
        new = engine()
        items = new.measure_batch(items, old['tokenizer_dir'], old['context_limit'], 3072)
        if any(i['preflight'] != 'ready' for i in items):
            raise ValueError('Full follow-up prompt exceeds context; no silent exclusions')
        for index, item in enumerate(items):
            item['endpoint_index'] = index % 8
        with base.atomic(root/'samples.jsonl') as stream:
            for item in items:
                stream.write(json.dumps(item, ensure_ascii=False)+'\n')
        pins = dict(old['pins'])
        pins.update(outcome_pins)
        for path in [Path(__file__), Path(__file__).parents[1]/'tests/test_dfm13_arena_audit_followup.py',
                     source/'manifest.json', source/'seal.json', source/'samples.jsonl']:
            pins[str(path.resolve())] = base.file_hash(path)
        manifest = dict(old, version=VERSION, total=129, per_export=None, max_tokens=3072,
            source_root=str(source), selection='all 117 invalid responses plus all 12 exposed controls',
            pins=pins, samples_sha256=base.file_hash(root/'samples.jsonl'),
            preflight={'ready':129}, endpoints_initial_counts=[17]+[16]*7,
            exposed_controls=12, fresh_accuracy_estimate=False)
        base.write_json(root/'manifest.json', manifest)
        base.write_json(root/'seal.json', {'manifest_sha256':base.file_hash(root/'manifest.json')})
        new.verify(root)
        return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'verify', 'run'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--servers-ready', action='store_true')
    args = parser.parse_args()
    if args.command == 'prepare':
        if args.source is None:
            parser.error('--source required for prepare')
        result = prepare(args.root, args.source)
    elif args.command == 'verify':
        manifest, items = engine().verify(args.root)
        result = {'version':manifest['version'], 'total':len(items), 'seal':'verified'}
    else:
        result = asyncio.run(engine().run(args.root, concurrency=256, timeout=600,
                                         ready=args.servers_ready))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
