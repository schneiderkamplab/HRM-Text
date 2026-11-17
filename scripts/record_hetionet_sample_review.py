"""Serialize the manual 2026-10-23 review; this is not an automated auditor."""
import json
from collections import Counter
from pathlib import Path


ROOT = Path('logs/analysis/dfm16_hetionet_review_20261023')
GROUPS = [
    ([46, 48, 50, 53], 'repair', 'unscoped_negative',
     'A corrupted graph edge does not establish absence of biomedical evidence. Supply evidence context and answer not supported by that context.'),
    ([21, 28, 29], 'repair', 'unsupported_superlative',
     'A resembles edge supports similarity, not most similar among candidates. Remove superlative and verify option uniqueness.'),
    ([41], 'repair', 'gene_protein_confusion',
     'Compound-binds-Gene denotes binding the protein product, not binding the gene. Correct prompt.'),
    ([75], 'repair', 'expression_activity_conflation',
     'Upregulation of gene expression does not establish increased protein activity. Use expression wording.'),
    ([1, 9, 12], 'repair', 'implied_unique_answer',
     'The gene implies uniqueness unsupported by one membership edge. Ask for one example and qualify answer.'),
    ([15, 20, 23, 32, 64, 71], 'repair', 'disease_expression_causality',
     'Disease up/downregulates wording suggests causation; describe observed expression in disease samples.'),
    ([4, 16, 22, 35, 59, 70, 82, 96], 'polish', 'language_or_ontology_wording',
     'Understandable but awkward grammar, capitalization or ontology labels; optional natural-language polish.'),
]


def main():
    rows = [json.loads(line) for line in (ROOT / 'sample.jsonl').open()]
    sampling = json.loads((ROOT / 'sampling.json').read_text())
    assert sampling['seed'] == 20261023 and len(rows) == 100
    assert [r['source_row'] for r in rows] == sampling['indices']
    annotations = {}
    for indices, verdict, issue, note in GROUPS:
        for i in indices:
            assert i not in annotations
            annotations[i] = (verdict, issue, note)
    results = []
    for i, row in enumerate(rows):
        verdict, issue, note = annotations.get(i, (
            'provisionally_usable', None,
            'No material wording or graph-fidelity defect identified in manual inspection; not independently fact-checked.'))
        results.append(dict(
            sample_index=i, source_row=row['source_row'], example_id=row['example_id'],
            task_type=row['task_type'], reviewer='assistant_manual_review',
            verdict=verdict, issue=issue, note=note,
            clinical_truth_verified=False,
            full_graph_answer_uniqueness_verified=False))
    with (ROOT / 'review.jsonl').open('w') as out:
        for result in results:
            out.write(json.dumps(result) + '\n')
    summary = dict(
        verdicts=dict(Counter(r['verdict'] for r in results)),
        issues=dict(Counter(r['issue'] for r in results if r['issue'])),
        tasks=dict(Counter(r['task_type'] for r in rows)),
        scope='All 100 sampled messages and supplied triples read; no GPU judge or independent clinical verification.',
        caveats=[
            'No sampled prompt provides the source triples as evidence; multi-hop items test graph recall rather than reasoning over supplied context.',
            'Single-edge MCQ provenance does not prove other options false; full graph and source checks remain needed.',
            'All 100 use user/assistant messages; no observed role corruption or literal think markup.',
            'Repair counts are manual screening judgments, not a measured biomedical falsehood rate.'])
    (ROOT / 'review_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
