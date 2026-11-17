"""Quarantine the old pilot; prepare full re-audit and a gated 2,000-row pilot."""
from collections import Counter
import json
from pathlib import Path
from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from scripts.prepare_dfm16_dyna import publish_audit_manifest
from scripts.prepare_dfm16_stories import ROOT
from scripts.dfm16_story_quality import CRITERIA, POLICY, specification


def chunks(out, records, task):
    manifest, pending = [], []
    def flush():
        if not pending:
            return
        path = out/'chunks'/f'{len(manifest):06}.jsonl'
        with atomic(path) as f:
            for row in pending:
                f.write(json.dumps(row, ensure_ascii=False)+'\n')
        manifest.append(dict(job_id=f'quality-{len(manifest):06}', input=str(path.relative_to(out)),
                             rows=len(pending), task=task, sha256=file_hash(path)))
        pending.clear()
    for row in records:
        pending.append(row)
        if len(pending) == 128:
            flush()
    flush()
    write_json(out/'tokenizer.json', load('data/dfm15/native-reasoning-v2/sampled_dfm15/metadata.json')['tokenizer_info'])
    write_json(out/'quality-policy.json', dict(policy=POLICY, criteria=CRITERIA, training_ready=False))
    publish_audit_manifest(out, manifest)


def prepare(root=ROOT):
    base = root/'stories/quality-v2'
    with lock(base/'.prepare.lock'):
        write_json(root/'stories/admission-hold.json', dict(policy=POLICY,
            reason='Old acceptance is insufficient: all 300K require new whole-conversation review.',
            old_corpus_admitted=False, pilot_production_authorized=False))
        old = root/'accepted/simplestories'
        held = root/'held/simplestories-v1'
        if old.exists():
            if held.exists():
                raise ValueError('Both old and quarantined story corpora exist')
            held.parent.mkdir(parents=True, exist_ok=True)
            old.rename(held)
        if not (held/'conversion.json').exists():
            raise ValueError('Missing old pilot')
        write_json(held/'admission.json', dict(training_ready=False, status='quarantined_pending_reaudit', policy=POLICY))
        audit = base/'reaudit'
        if not (audit/'readiness.json').exists():
            counts, seen, hashes = Counter(), set(), {}
            def records():
                for path in sorted((held/'input/direct').glob('*.jsonl')):
                    hashes[str(path.relative_to(held))] = file_hash(path)
                    for row in rows(path):
                        if row['id'] in seen:
                            raise ValueError('Duplicate old pilot ID')
                        seen.add(row['id'])
                        counts[f'{row["language"]}/{row["task"]}'] += 1
                        row.update(audit_id=row['id'], training_ready=False, admission_authorized=False,
                                   audit_context=dict(policy=POLICY, criteria=CRITERIA,
                                   mode='monolingual', previous_acceptance_is_not_evidence=True))
                        yield row
            chunks(audit, records(), 'story_strict_reaudit')
            if len(seen) != 300000:
                (audit/'readiness.json').unlink()
                raise ValueError(f'Expected exactly 300K old conversations, got {len(seen)}')
            write_json(audit/'source-receipt.json', dict(rows=len(seen), groups=dict(counts), files=hashes))
        pilot = base/'pilot'
        if not (pilot/'readiness.json').exists():
            pools = {lang: list(rows(root/'stories'/f'seeds-{lang}.jsonl')) for lang in ('en', 'da', 'ja', 'hi')}
            def candidates():
                for i in range(100):
                    for lang, pool in pools.items():
                        for task_index, task in enumerate(('creative', 'revision', 'summary', 'rewrite', 'qa')):
                            seed = pool[(7919+i*7+task_index*1009) % len(pool)]
                            spec = specification(task, i, lang)
                            key = digest([POLICY, lang, task, i, seed['provenance'], spec])
                            yield dict(id=key, audit_id=key, language=lang, task=task,
                                variant=i, seed=seed['text'], specification=spec,
                                revisions=len(spec.get('revision_operations', [])),
                                provenance=dict(seed['provenance'], policy=POLICY, language=lang, task=task))
            chunks(pilot, candidates(), 'story_generation_review')
            write_json(pilot/'targets.json', dict(candidates=2000, per_language_task=100,
                manual_review_required=100, production_authorized=False,
                proposed_production=dict(accepted_target=300000, initial_candidates=450000,
                                         maximum_candidate_budget=600000)))
    return base


if __name__ == '__main__':
    print(prepare(), flush=True)
