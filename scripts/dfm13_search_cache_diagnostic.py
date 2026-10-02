"""Read-only targeted full-cache inspection; no network, model calls or admission."""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from scripts.dfm13_search_calibration import atomic, now

PATTERNS = {
    '64b59': r'GSM8K|89\.3|Table 3',
    '99fe1': r'200MP|200.megapixel|Android 14',
    '93ba4': r'Kehilat|Eden.{0,40}27|65608',
    'b528d': r'200|150|價格|價錢',
    'e19e0': r'1667',
    '247e1': r'135.ФЗ|135.FZ',
}
FINDINGS = {
    '64b59': dict(classification='confirmed_excerpt_omission',note='Full technical report Table 3 contains 89.3 GSM8K EM, 8-shot, DeepSeek-V3-Base; preserve base/model variant and evaluation setting. This does not prove latest chat-model performance.'),
    '99fe1': dict(classification='confirmed_excerpt_omission_and_overcaution',note='Android Headlines specification text is beyond the prefix excerpt. 200MP appears in both title and later article body; general purchasing tradeoffs need not each be quoted empirical claims. Price/current support still require care.'),
    '31dbd': dict(classification='reviewer_overcaution',note='User requested a constructed metacognitive intervention example. Lack of an identical published programmer-specific example is not itself a factual defect. Avoid asserting measured efficacy for the invented example.'),
    'f966d': dict(classification='repair_model_overrefusal',note='Underlying request is benign text-to-speech with pauses. Jailbreak framing does not itself justify refusing the benign task. Unlimited/free/no-trial claims still require supporting evidence.'),
    '93ba4': dict(classification='genuine_gap_in_inspected_cache',note='Full cached results do not establish the code for Kehilat Eden 27; evidence about number 1 must not be substituted. Interactive locator text is not a completed address lookup.'),
    'b528d': dict(classification='not_yet_resolved',note='Price-number occurrences alone do not establish restaurants satisfying all requirements: under TWD200, former Bib listing, excluded in 2024, exact entry years. Requires joined entity/date/price evidence, not blind rewriting.'),
}


def main():
    db=sqlite3.connect('file:data/dfm13/search-jina-paid-campaign-20261001/cache.sqlite?mode=ro',uri=True)
    ledger=[]
    for prefix,pattern in PATTERNS.items():
        row=db.execute('SELECT owner,query,raw FROM searches WHERE owner LIKE ? AND status=?',(prefix+'%','done')).fetchone()
        if row is None:
            continue
        owner,query,raw=row
        documents=[]
        for index,item in enumerate(json.loads(raw)['data']):
            body=item.get('content') or ''
            matches=[]
            for hit in list(re.finditer(pattern,body,re.I))[:8]:
                start=max(0,hit.start()-900)
                end=min(len(body),hit.end()+900)
                matches.append(dict(match_offset=hit.start(),start=start,end=end,text=body[start:end]))
            documents.append(dict(rank=index+1,url=item.get('url'),title=item.get('title'),
                full_chars=len(body),full_content_sha256=hashlib.sha256(body.encode()).hexdigest(),matches=matches))
        ledger.append(dict(id=owner,query=query,raw_cache_sha256=hashlib.sha256(raw).hexdigest(),documents=documents))
    root=Path('data/dfm13/search-full-cache-diagnostic-20261001')
    atomic(root/'evidence.json',dict(at=now(),read_only=True,paid_calls=0,findings=FINDINGS,evidence=ledger,
        admission_authorized=False,note='New excerpts were not shown in the original calibration; no retrospective evidence claim. No new correction/review loop launched.'))
    print(root/'evidence.json')


if __name__=='__main__':
    main()
