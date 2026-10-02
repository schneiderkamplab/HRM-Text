"""CPU-only terminal accounting and fresh stratified manual-review handoff."""
from collections import Counter
import argparse
import fcntl
from pathlib import Path
import re
import time
from scripts import dfm13_repochat_qa_filtered as f

b = f.n.b
ROOT = f.n.ROOT


def distribution(values):
    values = sorted(values)
    if not values:
        return {'count': 0}
    return {'count': len(values), 'sum': sum(values), 'min': values[0],
            'median': values[len(values)//2],
            'p90': values[min(len(values)-1, int(len(values)*.9))], 'max': values[-1]}


def scope(query):
    if re.search(r'\b(which|what files?|what is the function|what is the file)\b', query, re.I):
        return 'navigation'
    if re.search(r'\b(how|algorithm|implemented|mechanism)\b', query, re.I):
        return 'implementation_explanation'
    return 'overview'


def report():
    # Do not publish a readiness receipt from a partial campaign.
    required = [f.ROOT/'completion.json', ROOT/'first-wave-followup/completion.json', ROOT/'failed-nine-finalization/completion.json']
    for path in required:
        if not path.exists():
            raise ValueError('not terminal: '+str(path))
    tasks = b.load(f.ROOT/'selection.json')['tasks']
    records = []
    for task in tasks:
        directory = f.ROOT/'trajectories'/task['id']
        trajectory_path = directory/'trajectory.json'
        trajectory = b.load(trajectory_path)
        outcome = b.load(directory/'outcome.json')
        review_path = f.ROOT/'independent-review/reviews'/task['id']/'outcome.json'
        review = b.load(review_path)
        messages = trajectory['messages']
        answers = [m.get('content') for m in messages if m['role']=='assistant' and not m.get('tool_calls') and m.get('content')]
        answer = answers[-1] if answers and not trajectory.get('incomplete') else ''
        tools = [m for m in messages if m['role']=='tool']
        errors = 0
        import json
        for message in tools:
            try:
                result = json.loads(message['content'])
                errors += isinstance(result, dict) and 'error' in result
            except (TypeError, ValueError):
                errors += 1
        records.append({'task': task, 'stratum': scope(task['query']),
            'tool_turns': sum(m['role']=='assistant' and bool(m.get('tool_calls')) for m in messages),
            'tool_calls': sum(len(m.get('tool_calls') or []) for m in messages if m['role']=='assistant'),
            'tool_results': len(tools), 'tool_errors': errors,
            'answer_characters': len(answer), 'answer_words': len(answer.split()),
            'generation_status': outcome['status'], 'generation_error': outcome.get('error'),
            'review_status': review['status'], 'review_pass': review.get('quality_pass', False),
            'review_error': review.get('error'), 'trajectory': str(trajectory_path),
            'trajectory_sha256': b.file_sha(trajectory_path), 'review': str(review_path),
            'review_sha256': b.file_sha(review_path), 'admission': False})
    passing = [r for r in records if r['review_pass']]
    selected = []
    for category, quota in [('overview',4), ('navigation',4), ('implementation_explanation',4)]:
        pool = sorted([r for r in passing if r['stratum']==category],
                      key=lambda r:b.sha(('20261002:'+r['task']['id']).encode()))
        selected.extend(pool[:quota])
    remaining = sorted([r for r in passing if r not in selected], key=lambda r:b.sha(('20261002:'+r['task']['id']).encode()))
    selected.extend(remaining[:max(0,12-len(selected))])
    packet = []
    for record in selected:
        task = record['task']
        snapshot = ROOT/'repositories'/task['repository'].replace('/', '--')/'snapshot.json'
        packet.append({'task':task, 'stratum':record['stratum'], 'trajectory':record['trajectory'],
            'trajectory_sha256':record['trajectory_sha256'], 'snapshot':str(snapshot),
            'snapshot_sha256':b.file_sha(snapshot),
            'answer_and_evidence':f.n.previous.audit.probe.package(b.load(record['trajectory'])['messages'])})
    out = ROOT/'readiness'
    b.save(out/'fresh-manual-sample.json', {'seed':20261002, 'cases':packet,
        'automated_verdicts_omitted':True, 'non_english_gap':'This selected cohort contains English prompts; no fresh non-English stratum is available. Repository language is not prompt language.',
        'admission':False})
    counts = {'selected':len(records), 'review_passes':len(passing),
        'review_rejections':sum(r['review_status']=='reviewed' and not r['review_pass'] for r in records),
        'review_statuses':dict(Counter(r['review_status'] for r in records)),
        'generation_statuses':dict(Counter(r['generation_status'] for r in records))}
    summary = {'counts':counts, 'distributions':{k:distribution([r[k] for r in records]) for k in
        ['tool_turns','tool_calls','tool_results','tool_errors','answer_characters','answer_words']},
        'answer_distribution_population':'all74; incomplete answers counted as zero',
        'source_failures':b.load(ROOT/'preparation.json')['failures'],
        'scope_holds':[r for r in b.load(f.ASSESSMENT)['records'] if r['status']!='eligible'],
        'known_manual_holds': ['No automatic admission for any cohort.',
            'First-wave scrcpy OTG exception requires separately reviewed repair.',
            'First-wave Wacom empty answer remains failed; retry is additive.',
            'Earlier XMOS external algorithm-source qualification remains unresolved.',
            'Earlier non_empty_continuous conversion assurances require correction.',
            'Earlier SillyTavern static-model-list false acceptance remains a hold.'],
        'followups':{name:b.load(ROOT/'first-wave-followup'/name/'independent-review/summary.json') for name in ['scrcpy','wacom']},
        'failed_nine_finalization':b.load(ROOT/'failed-nine-finalization/independent-review/summary.json'),
        'records':records, 'admission':False}
    holds_path=ROOT/'manual-claim-repairs/holds.json'
    if holds_path.exists():
        holds=b.load(holds_path)
        summary['hash_bound_manual_holds']=holds['holds']
        summary['manual_holds_sha256']=b.file_sha(holds_path)
        summary['further_scale_allowed']=False
    b.save(out/'summary.json', summary)
    b.save(out/'parent-assignment-ready.json', {'status':'ready_for_parent_to_assign_Boole',
        'packet':str(out/'fresh-manual-sample.json'), 'packet_sha256':b.file_sha(out/'fresh-manual-sample.json'),
        'summary_sha256':b.file_sha(out/'summary.json'), 'sample_count':len(packet),
        'request':'Assign independent source-grounded assessment of this fresh stratified sample; do not infer admission from reviewer passes.',
        'admission':False})
    print(counts, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait-seconds', type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.wait_seconds <= 10800:
        parser.error('wait must be between zero and three hours')
    out = ROOT/'readiness'
    out.mkdir(parents=True, exist_ok=True)
    with (out/'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        deadline = time.monotonic()+args.wait_seconds
        while not all(p.exists() for p in [f.ROOT/'completion.json', ROOT/'first-wave-followup/completion.json', ROOT/'failed-nine-finalization/completion.json']):
            if time.monotonic() >= deadline:
                raise TimeoutError('terminal receipts unavailable; no readiness claim written')
            time.sleep(10)
        report()
