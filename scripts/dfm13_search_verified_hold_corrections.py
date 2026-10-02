"""CPU-authored conservative correction ledger, not forced admission."""
import hashlib
import json
from pathlib import Path
import sqlite3
from scripts import dfm13_search_calibration as base
from scripts.dfm13_search_reviewer_controls import strong_test

TEXT={
 '032d2d0c': '不能据这些材料断言“至少需要 4 个底数”。缓存的资料列出了一个充分方案：底数 2、7、61 可覆盖 n < 4,759,123,141，因此也覆盖 10^9 范围。不过，这给出的是充分条件，不是底数数量的最小性证明。另一个说法“2、3、5、7 覆盖全部 32 位整数”是错误的：3215031751 = 151 × 751 × 28351 是合数、小于 2^32，却通过这四个底数的强伪素数检验。某一组三个底数失败，也不能证明所有三底数组合都会失败。要回答严格的“最少几个”，还需要明确底数选择的限制并提供相应的最小性依据。',
 '51c2360a': 'La question est datée du 5 mai 2025. Les passages utilisés ne justifient pas de présenter comme déjà disponibles à cette date des annonces du 14 mai, du 6 juin ou du 10 juin 2025. Une page de notes de publication consultée en 2026 doit être filtrée selon la date de chaque annonce. Je ne peux donc pas confirmer, à partir des passages retenus, quel était exactement le dernier modèle disponible le 5 mai 2025. Il faut aussi distinguer disponibilité dans ChatGPT et disponibilité via API.',
 '06cd049f': 'Your question is dated May 9, 2025. A February 2026 report based on December 2025 polling cannot establish what was current when you asked. The cached later reports therefore do not support a dated forecast of the next political or social "spark" in May 2025. I cannot reliably predict such an event or its timing from this evidence. Claims about inevitability, a specific trigger or imminent widespread violence would need stronger, contemporaneous support; they should not be inferred from later polling.',
}


def main():
    root=Path('data/dfm13/search-independent-hold-corrections-20261001')
    if root.exists():raise ValueError('new output required')
    source=Path('data/dfm13/search-supplement9-20261001/jobs.json')
    jobs=[j for j in json.loads(source.read_text()) if j['id'][:8] in TEXT]
    assert 151*751*28351==3215031751<2**32
    assert all(strong_test(3215031751,a) for a in (2,3,5,7))
    db=sqlite3.connect('file:'+str(base.CAMPAIGN/'cache.sqlite')+'?mode=ro',uri=True)
    rows=[]
    for job in jobs:
        prefix=job['id'][:8]; evidence=[]
        if prefix=='032d2d0c':
            raw=db.execute('SELECT raw FROM searches WHERE owner=? AND status="done" ORDER BY rowid LIMIT 1',(job['id'],)).fetchone()[0]
            for page in json.loads(raw)['data']:
                body=page.get('content') or ''
                if page.get('url')=='https://en.wikipedia.org/wiki/Miller%E2%80%93Rabin_primality_test':
                    position=body.find('4,759,123,141')
                    if position<0:raise ValueError('cached sufficient-bound evidence missing')
                    start=max(0,position-150);end=min(len(body),position+180)
                    evidence.append(dict(url=page['url'],start=start,end=end,text=body[start:end],
                        full_content_sha256=hashlib.sha256(body.encode()).hexdigest(),cache_sha256=hashlib.sha256(raw).hexdigest(),
                        supports='reported sufficient bound for 2,7,61; NOT minimality proof'))
            if not evidence:raise ValueError('insufficient math correction evidence')
        rows.append(dict(id=job['id'],prompt=job['sample']['prompt'],original_timestamp=job['sample']['original_timestamp'],
            proposed_correction=TEXT[prefix],authorship='agent-authored explicit correction, not model-generated independent success',
            verified_hint=job['verified_correction'],additional_cached_evidence=evidence,
            full_task_solved=False,independent_hold_retained=True,admission_authorized=False))
    db.close()
    base.atomic(root/'ledger.json',dict(rows=rows,model_calls=0,paid_calls=0,admission_authorized=False,
        source_sha256=base.file_hash(source),implementation_sha256=base.file_hash(Path(__file__)),
        math_cpu_verification=dict(number=3215031751,factors=[151,751,28351],passes_bases=[2,3,5,7],less_than_2pow32=True)))
    print(json.dumps(dict(corrections=len(rows),holds_retained=len(rows),new_paid_calls=0)))


if __name__=='__main__':main()
