"""Record explicit assistant-manual rubric reconciliation, before new votes.

These are reconciled prior complete manual assessments, with targeted rereads;
not a claim that all 200 were freshly reread in this turn. No model votes used.
"""
from collections import Counter
from fnmatch import fnmatchcase
from pathlib import Path

from dfm12.io import file_hash, load, rows
from scripts.dfm16_story_calibration import ROOT, immutable, immutable_rows, import_labels

ANNOTATIONS = Path('docs/reports/dfm16-multiview-manual-labels.json')
CLEAR = {48,51,52,53,55,56,57,59,61,62,63,64,66,67,68,69,70,71,72,73,76,78,80,81,
         84,85,86,87,88,89,91,92,93,95,96,97,99,100,118,134,152,162,163,166,168,169,
         175,184,187,189,191,192,193,196,198}
BORDERLINE = {2,8,45,54,58,60,65,77,82,94,98,111,121,144,151,153,157,158,159,160,
              164,165,167,173,180,181,182,183,194,199}
BAD = {1,3,4,5,6,7,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,
       29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,46,47,49,50,74,75,79,83,
       90,101,102,103,104,105,106,107,108,109,110,112,113,114,115,116,117,119,120,
       122,123,124,125,126,127,128,129,130,131,132,133,135,136,137,138,139,140,141,
       142,143,145,146,147,148,149,150,154,155,156,161,170,171,172,174,176,177,178,
       179,185,186,188,190,195,197,200}
OVERRIDES = {
    4: 'Definite compound spelling error: fusionreaktor should be fusionsreaktor. Small clear language errors remain in scope.',
    9: 'Definite misspelling sirusen for siruppen in the assistant story; not merely a literary-style preference.',
    13: 'The user source contains the definite Danish misspelling urgamal (urgammel). It is not an intentionally flawed correction input.',
    38: 'The rewrite changes the source feeling lost into vildledte (misled), violating the explicit request to preserve feelings.',
    41: 'The user source contains clear accidental misspellings cirler and skatetboardet; the task requests summarization, not spelling correction.',
    52: 'Prior seed-size concern is ordinary imaginative fiction, not a definite defect; the independently requested library story need not preserve that plot.',
    73: 'The v3 initial length range applies to the initial answer. Later opening revision does not explicitly retain it; final shortening explicitly supersedes it. Local preservation is met.',
    78: 'The initial length range is initial-only under the trusted contract; later local edits and selective undo are performed correctly. Withdraw prior inherited-length-only rejection.',
    86: 'Naming the unnamed first-person narrator Alice in a third-person rewrite does not contradict an existing identity or event; source seed also names Alice. No definite defect.',
    130: 'User requests conversion to third person although the source is already third person; source also duplicates a whole sentence. This is accidental task/source corruption, not deliberate correction material.',
}
REREAD = [4,8,9,13,38,41,52,54,58,60,65,73,77,78,82,86,94,98,125,126,130,155,176,200]


def main():
    assert not (CLEAR & BAD or CLEAR & BORDERLINE or BAD & BORDERLINE)
    assert CLEAR | BAD | BORDERLINE == set(range(1,201))
    stage = ROOT/'development'
    annotations = load(ANNOTATIONS)['parents']
    parents = {p['id']:p for p in rows(stage/'inputs.jsonl')}
    links = {c['study_id']:c['parent_id'] for c in rows(stage/'prior-checks.jsonl')}
    result = []
    for i in range(1,201):
        study = f'H{i:03}'
        prior = annotations[study]['overrides']
        label = 'clear' if i in CLEAR else 'bad' if i in BAD else 'borderline'
        notes = sorted({v[1] for v in prior.values()})
        defects = sorted({v[1] for v in prior.values() if v[0]=='bad'})
        # These particular length objections were not explicit retained limits.
        if i in (172,174,179):
            defects = [d for d in defects if 'maximum' not in d and 'exceed' not in d]
        if i in OVERRIDES:
            note = OVERRIDES[i]
            if label == 'bad': defects = [note]
        else:
            note = ('Reconciled prior complete manual assessment under context-aware rubric. '
                    + ('; '.join(notes) if notes else 'No definite or borderline issue recorded in the prior complete seed/conversation assessment.'))
        parent = parents[links[study]]
        affected = set()
        allow_seed = False
        for pattern, (severity, _) in prior.items():
            if severity != 'bad' and i not in (4,9,13,38,41,130):
                continue
            if pattern.startswith('seed/'):
                allow_seed = True
            elif pattern.startswith('message/'):
                affected.update(j for j in range(len(parent['messages'])) if fnmatchcase(f'message/{j}/'+pattern.rsplit('/',1)[1], pattern))
            elif pattern.startswith(('conversation/', 'exchange_pair/', 'message_pair/')):
                affected.update(j for j,m in enumerate(parent['messages']) if m['role']=='assistant')
        result.append(dict(id=links[study], study_id=study, label=label, note=note,
            defects=defects if label=='bad' else [], allowed_turns=sorted(affected) if label=='bad' else [],
            allow_seed=allow_seed if label=='bad' else False, reviewer='assistant-manual', blind=True,
            method='manual reconciliation of prior complete assessments; targeted context rereads',
            targeted_reread_this_turn=i in REREAD, prior_annotations_sha256=file_hash(ANNOTATIONS)))
    immutable_rows(stage/'reconciled-manual-labels.jsonl',result)
    immutable(stage/'reconciliation.json',dict(method=__doc__, prior_sha256=file_hash(ANNOTATIONS),
        labels_sha256=file_hash(stage/'reconciled-manual-labels.jsonl'),
        targeted_rereads=REREAD, counts=dict(Counter(r['label'] for r in result)),
        provisional=True, independent_human_certification=False))
    # The detached driver holds the campaign lock while waiting for this receipt.
    # Import atomically through the same function; do not run a second driver.
    import_labels(stage,stage/'reconciled-manual-labels.jsonl')
    print(dict(Counter(r['label'] for r in result)))


if __name__ == '__main__':
    main()
