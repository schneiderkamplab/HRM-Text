"""Read-only raw audit inspection; write proposed index repairs to a new sidecar."""
import argparse
from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path
import re

BASE = Path(__file__).with_name('dfm13_arena_audit.py')
spec = importlib.util.spec_from_file_location('_arena_quote_base', BASE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def classify(issue, messages):
    quote, index = issue['quote'], issue['message_index']
    matches = [i for i, m in enumerate(messages) if quote and quote in m['content']]
    if index in matches:
        return 'exact_at_claimed_index', matches
    if len(matches) == 1:
        return 'exact_unique_elsewhere', matches
    if matches:
        return 'exact_ambiguous_elsewhere', matches
    compact = lambda s: re.sub(r'\s+', '', s)
    normalized = compact(quote)
    if normalized and any(normalized in compact(m['content']) for m in messages):
        return 'whitespace_only_match', []
    # Diagnostic heuristic ONLY: removing markdown/punctuation can create collisions.
    formatting = lambda s: re.sub(r'[\s*_`#~\\]', '', s)
    normalized = formatting(quote)
    if normalized and any(normalized in formatting(m['content']) for m in messages):
        return 'formatting_heuristic_match', []
    return 'absent_or_paraphrase', []


def diagnose(result, row):
    messages = audit.visible(row)['conversation']
    candidate = copy.deepcopy(result)
    evidence, changes = [], []
    for number, issue in enumerate(result['issues']):
        bucket, matches = classify(issue, messages)
        evidence.append(dict(issue=number, bucket=bucket, original_index=issue['message_index'],
                             exact_matching_indices=matches, quote=issue['quote']))
        if bucket == 'exact_unique_elsewhere':
            index = matches[0]
            content = messages[index]['content']
            start = content.index(issue['quote'])
            changes.append(dict(issue=number, old_index=issue['message_index'], new_index=index,
                quote=issue['quote'], message_role=messages[index]['role'],
                message_sha256=audit.digest(content), first_match_start=start,
                first_match_end=start+len(issue['quote']),
                reason='Unchanged quote occurs in exactly one visible message'))
            candidate['issues'][number]['message_index'] = index
    try:
        audit.validate_result(candidate, row)
        error = None
    except Exception as exc:
        error = repr(exc)
    proposed = candidate if changes else None
    return dict(issues=evidence, changes=changes, proposed_result=proposed,
                proposed_passes_original_validator=bool(changes) and error is None,
                remaining_validation_error=error, semantic_approval=False,
                warning='Index provenance repair only; not factual or semantic validation. '
                        'User-message evidence may not support a target-quality conclusion.')


def analyze(root):
    root = Path(root).resolve()
    samples = {x['id']:x for x in map(audit.strict_json,(root/'samples.jsonl').read_text().splitlines())}
    records, issues, combinations = [], Counter(), Counter()
    seen = set()
    for path in sorted((root/'raw').glob('*.request.json')):
        request = audit.load(path)
        sid = request['metadata']['id']
        outcome_path = root/'outcomes'/f'{sid}.json'
        outcome = audit.load(outcome_path)
        if 'Issue evidence is not an exact visible message span' not in outcome.get('error',''):
            continue
        if sid in seen:
            raise ValueError('Multiple raw attempts require explicit attempt selection')
        seen.add(sid)
        response_path = path.with_name(path.name.replace('.request.','.response.'))
        raw = audit.load(response_path)
        envelope = audit.strict_json(raw['raw_body_utf8'])
        result = audit.strict_json(envelope['choices'][0]['message']['content'])
        report = diagnose(result, samples[sid]['example'])
        buckets = [i['bucket'] for i in report['issues'] if i['bucket']!='exact_at_claimed_index']
        issues.update(buckets)
        combinations[' + '.join(sorted(set(buckets)))]+=1
        records.append(dict(id=sid, source_id=samples[sid]['source_id'],
            raw_request_path=str(path), raw_response_path=str(response_path),
            raw_response_sha256=audit.file_hash(response_path), outcome_sha256=audit.file_hash(outcome_path),
            original_result_sha256=audit.digest(result), **report))
    expected = sum('Issue evidence is not an exact visible message span' in audit.load(p).get('error','')
                   for p in (root/'outcomes').glob('*.json'))
    if len(records)!=expected:
        raise ValueError('Not all quote failures matched raw responses')
    return dict(root=str(root), manifest_sha256=audit.file_hash(root/'manifest.json'),
        samples_sha256=audit.file_hash(root/'samples.jsonl'),
        quote_failed_responses=len(records), issue_buckets=dict(issues),
        response_bucket_combinations=dict(combinations),
        responses_with_proposed_index_changes=sum(bool(r['changes']) for r in records),
        proposed_fully_valid_responses=sum(r['proposed_passes_original_validator'] for r in records),
        records=records)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roots',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with audit.lock(args.output.with_suffix('.lock')):
        if args.output.exists():
            raise ValueError('Refusing to overwrite an existing sidecar')
        reports=[analyze(p) for p in args.roots]
        audit.write_json(args.output,dict(version='arena-quote-proposals-v1',
            script_sha256=audit.file_hash(Path(__file__)),originals_unchanged=True,
            proposals_only=True,reports=reports))
    for report in reports:
        print(json.dumps({k:v for k,v in report.items() if k!='records'},indent=2))


if __name__=='__main__':
    main()
