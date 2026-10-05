"""Bind the manual review to unchanged inputs and mechanically replayed rows."""
from pathlib import Path
from collections import Counter

from dfm12.io import digest, file_hash, load, write_json

ROOT = Path(__file__).resolve().parent


def main():
    evidence = load(ROOT / 'evidence.json')
    findings = load(ROOT / 'findings.json')
    checks = load(ROOT / 'mechanical-checks.json')
    pins = load(ROOT / 'input-pins.json')
    assert len(evidence) == len(findings) == len(checks) == 16
    assert [f['case'] for f in findings] == list(range(16))
    assert Counter(e['record']['task'] for e in evidence) == {
        'denoising': 4, 'paragraph-reordering': 4, 'prefix-continuation': 4, 'span-filling': 4}
    bound = []
    for evidence_row, finding, check in zip(evidence, findings, checks):
        assert evidence_row['case'] == finding['case'] == check['case']
        assert digest(evidence_row['record']) == evidence_row['record_sha256']
        assert check == evidence_row['replay']
        assert all(value for value in check.values() if type(value) is bool)
        assert evidence_row['record']['quality_status'] == 'accepted'
        bound.append(dict(finding, id=evidence_row['record']['id'],
            task=evidence_row['record']['task'], record_sha256=evidence_row['record_sha256'],
            source_text_sha256=evidence_row['source_text_sha256'],
            window_sha256=evidence_row['window_sha256'],
            hf_revision=evidence_row['publication']['hf_revision'],
            published_path=evidence_row['publication']['output'], ordinal=evidence_row['ordinal']))
    assert all(file_hash(path) == sha for path, sha in pins.items())
    summary = dict(cases=16, per_task=4, source_replay_exact=16, category_only=0,
                   heading_only=0, paragraph_reordering_with_nonprose_blocks=4,
                   paragraph_reordering_below_two_prose=1, list_only_denoising_not_category_only=1,
                   internal_date_contradictions_confirmed=1, population_rate_claim=False)
    assert sum(r['category_only'] for r in bound) == summary['category_only']
    assert sum(r['heading_only'] for r in bound) == summary['heading_only']
    assert sum(r['definite_task_mismatch'] for r in bound) == 1
    write_json(ROOT / 'review.json', dict(scope='manual_bounded_sample_not_population_rate',
        semantic_method='independent full selected prompt/answer/window reading, not judge or anchor pass',
        summary=summary, cases=bound))
    write_json(ROOT / 'receipt.json', dict(status='independent_read_only_review_complete',
        summary=summary, input_pins=pins, all_source_and_publication_files_unchanged=True,
        files={p.name:file_hash(p) for p in sorted(ROOT.iterdir()) if p.is_file() and p.name != 'receipt.json'},
        code_pins={p:file_hash(p) for p in ('dfm12/transform.py', 'dfm12/wave4_transforms.py')},
        gpu_calls=0, eligibility_changes=False, filters_applied=False))
    print(summary)
    print('receipt_sha256', file_hash(ROOT / 'receipt.json'))


if __name__ == '__main__':
    main()
