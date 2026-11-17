"""Freeze single-criterion judge requests for the already manually labelled 200."""
from pathlib import Path
from dfm12.io import file_hash, rows, write_json
from scripts.dfm16_judge_ensemble_study import ROOT as PREVIOUS, save_rows
from scripts.queue_dfm16_stories_qwen import prepare_stage

ROOT = PREVIOUS.parent/'atomic-judge-study'
QUESTIONS = {
    'grammar': 'Is the grammar of this text correct?',
    'clarity': 'Is the meaning of this text clear?',
    'consistency': 'Is this text internally consistent?',
}


def main():
    samples = [r for r in rows(PREVIOUS/'samples.jsonl') if r['cohort'] == 'holdout']
    assert len(samples) == 200
    save_rows(ROOT/'samples.jsonl', samples)
    checks = []
    for row in samples:
        for aspect, question in QUESTIONS.items():
            identifier = row['study_id']+'/'+aspect
            checks.append(dict(row, id=identifier, audit_id=identifier, aspect=aspect,
                comparison_cohort='holdout', prompt=f'Text:\n{row["text"]}\n\n{question} Answer only yes or no.'))
    for model in ('odin', 'qwen27b', 'flash', 'mimir/probe'):
        prepare_stage(ROOT/model, checks, 'atomic_prose_judge_v1')
    write_json(ROOT/'design.json', dict(samples=200, checks_per_model=600,
        questions=QUESTIONS, source_sha256=file_hash(PREVIOUS/'samples.jsonl'),
        manual_labels_sha256=file_hash(Path('docs/reports/odin-ensemble-manual-200-20261028.md')),
        production_authorized=False, note='Same frozen texts and manual labels, no conversation context.'))
    print(ROOT)


if __name__ == '__main__':
    main()
