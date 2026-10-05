"""Read-only proof of four exact prepublication exclusions and retained case45."""
import json
from pathlib import Path
import sqlite3

from dfm12 import sr_manual_exclusion as sr
from dfm12.io import digest, file_hash, load, lock, write_json


def main():
    root=Path('data/dfm13/wave4')
    folder=root/'release/wikipedia-sr'
    target=sr.REVIEW/'manual-exclusion-proof.json'
    assert not target.exists(), 'Preserve existing proof'
    events=[]
    with lock(folder/'.lock'):
        sr.shared.require_unpublished(root,'wikipedia-sr',Path('exports_dfm13'),Path('config/dfm13_sources.json'))
        db=sqlite3.connect((folder/'ledger.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
        db.execute('BEGIN')
        evidence=load(sr.REVIEW/'evidence.json')
        for item in evidence:
            raw,status,review=db.execute('SELECT record,status,review FROM rows WHERE id=?',(item['id'],)).fetchone()
            assert digest(json.loads(raw))==item['record_sha256']
            assert digest(json.loads(review))==digest(item['acceptance_review'])
            assert status==('excluded_manual_review' if item['id'] in sr.CASES.values() else 'accepted')
        for key,encoded in db.execute('SELECT id,decision FROM manual_review_decisions ORDER BY id'):
            assert key in sr.CASES.values()
            event=json.loads(encoded)
            raw,status,review=db.execute('SELECT record,status,review FROM rows WHERE id=?',(key,)).fetchone()
            assert event['original_record']==raw and event['original_model_review']==review
            assert event['prior_status']=='accepted' and event['status']==status=='excluded_manual_review'
            assert 'Main-agent' in event['authority'] and 'Explicit user authorization' not in event['authority']
            events.append(dict(id=key,decision_sha256=digest(event),decision=event))
        assert len(events)==4
        counts=dict(db.execute('SELECT status,count(*) FROM rows GROUP BY status'))
        status=load(folder/'status.json')
        assert counts==status['counts'] and counts['excluded_manual_review']==4
        db.rollback();db.close()
    write_json(target,dict(status='applied_prepublication',excluded_cases=sorted(sr.CASES),
        excluded_ids=list(sr.CASES.values()),retained_case45=sr.RETAINED_CASE45,
        all_16_original_records_and_model_reviews_unchanged=True,
        other_12_sample_statuses_accepted=True,publication_absent_at_verification=True,
        ledger_status=status,events=events,review_receipt_sha256=sr.RECEIPT_SHA,
        code_pins={str(p):file_hash(p) for p in (Path('dfm12/sr_manual_exclusion.py'),Path('dfm12/wave_manual_exclusion.py'))},
        prior_sl_sq_handoff_sha256=file_hash('exports_dfm13/sl-sq-exact4-subsets-20261003-v1/verified-handoff.json')))
    print(file_hash(target))


if __name__=='__main__': main()
