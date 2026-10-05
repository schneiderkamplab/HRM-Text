"""Main-reviewed exact four Serbian exclusions; case 45 deliberately retained."""
import argparse
import json
from pathlib import Path

from . import wave_manual_exclusion as shared
from .io import digest, file_hash, load, write_json

REVIEW = shared.REVIEW / 'sr-followup'
RECEIPT_SHA = 'd6a3f6b728d484ead750ff67c0af51b845c1d4752359ddaafeafbfacb7fb9d51'
CASES = {
    32: '000032d181b17d3afc56ee57f553a903c0d1cadfe8f399370b3f577bea51d686',
    36: '0005826fcf472897e267254a9f1186e9a3ca242e6723da282917ebe937ec3079',
    37: '00072e477233c2a7415c7caf467b27371a35ce1fab6101fe174a95da00baccd4',
    47: '0008ef735ff6b8114ba9788234d026ad4b2bacd3a224b3f1ce5fa419d1a0a9dc',
}
RETAINED_CASE45 = '000070fcd8d840af7759e5117eeac3a43ebcd0a50fee9be968450d55440461f8'


def reviewed_decisions():
    if file_hash(REVIEW/'receipt.json') != RECEIPT_SHA:
        raise ValueError('Serbian review receipt changed')
    pins = load(REVIEW/'receipt.json')['pins']
    for name, sha in pins.items():
        if file_hash(REVIEW/name) != sha:
            raise ValueError('Serbian review artifact changed: ' + name)
    evidence = {x['id']: x for x in load(REVIEW/'evidence.json')}
    decisions = []
    for row in load(REVIEW/'review.json'):
        if row['case'] not in CASES:
            continue
        if row['id'] != CASES[row['case']] or row['observation_category'] != 'source_window_defect':
            raise ValueError('Serbian exact-case scope changed')
        item = evidence[row['id']]
        if digest(item['record']) != row['record_sha256']:
            raise ValueError('Frozen candidate mismatch')
        decisions.append(dict(id=row['id'], component='wikipedia-sr',
            record_sha256=row['record_sha256'], review_sha256=digest(item['acceptance_review']),
            reason=row['observation'], review_pins=dict(pins, **{'receipt.json': RECEIPT_SHA}),
            scope_judgment='Main-agent review selects cases 32,36,37,47; case45 retained: meaningful Serbian intro, cast table and coherent gap answer; markers/empty heading alone insufficient'))
    if len(decisions) != 4 or RETAINED_CASE45 in {d['id'] for d in decisions}:
        raise ValueError('Wrong Serbian selection')
    return decisions


def apply(root, exports=Path('exports_dfm13'), registry=Path('config/dfm13_sources.json')):
    return shared.apply(root, exports, registry, component='wikipedia-sr', decision_loader=reviewed_decisions)


def publication_evidence(db, folder):
    """Export verified manual decisions under the caller's component lock."""
    expected = {d['id']: d for d in reviewed_decisions()}
    events = []
    for key, raw in db.execute('SELECT id,decision FROM manual_review_decisions ORDER BY id'):
        if key not in expected:
            raise ValueError('Unexpected Serbian manual exclusion')
        event = json.loads(raw)
        record, status, review = db.execute('SELECT record,status,review FROM rows WHERE id=?', (key,)).fetchone()
        if (event['authorization'] != expected[key] or status != shared.STATUS
                or event['original_record'] != record or event['original_model_review'] != review
                or event['prior_status'] != 'accepted'):
            raise ValueError('Serbian manual decision/ledger mismatch')
        events.append(event)
    if len(events) != 4:
        raise ValueError('Incomplete Serbian manual evidence')
    retained = db.execute('SELECT record,status FROM rows WHERE id=?', (RETAINED_CASE45,)).fetchone()
    frozen = next(x for x in load(REVIEW/'evidence.json') if x['case'] == 45)
    if retained is None or retained[1] != 'accepted' or digest(json.loads(retained[0])) != frozen['record_sha256']:
        raise ValueError('Case45 retention changed')
    payload = dict(scope='component_level_exact_four_ids', decisions=events,
        retained_case45=RETAINED_CASE45, retained_case45_record_sha256=frozen['record_sha256'],
        retained_case45_reason='Meaningful Serbian introduction, cast table and coherent gap answer; wiki markers/empty heading alone insufficient',
        authority='Main-agent case adjudication under user broad quality-review task',
        review_receipt_sha256=RECEIPT_SHA)
    path = Path(folder)/'manual-review-decisions.json'
    write_json(path, payload)
    return {file_hash(path): path.name}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/dfm13/wave4'))
    args = parser.parse_args()
    print(json.dumps(apply(args.root), indent=2))
