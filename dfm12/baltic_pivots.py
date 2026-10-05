"""Exact English-anchor joins with ambiguity rejection and both-leg provenance."""
from collections import Counter
import json
from pathlib import Path
import sqlite3

from .baltic_sources_cpu import ROOT
from .io import atomic, digest, file_hash, load, lock, rows, write_json


def texts(record):
    # An existing bidirectional OPUS record has each original text as a target.
    return {record['language']:record['messages'][-1]['content'],
            record['reverse_language']:record['reverse_messages'][-1]['content']}


def main(source_root=ROOT):
    source_root = Path(source_root)
    root=source_root/'pivots'
    cfg=load(source_root/'translations/config.json')
    with lock(root/'.lock'):
        db=sqlite3.connect(root/'anchors.sqlite')
        try:
            db.executescript('DROP TABLE IF EXISTS anchors; CREATE TABLE anchors '
                '(language TEXT, english TEXT, text TEXT, provenance TEXT, '
                'PRIMARY KEY(language,english,text));')
            inputs=[]
            for family in ('translations','institutional-translations'):
                for receipt in sorted((source_root/family/'candidates').glob('opus-*/receipt.json')):
                    if 'en' not in receipt.parent.name.removeprefix('opus-').split('-'):
                        continue
                    path=receipt.parent/'candidates.jsonl'
                    r=load(receipt)
                    if file_hash(path)!=r['sha256']:
                        raise ValueError('English leg changed')
                    inputs.append(dict(path=str(path),sha256=r['sha256']))
                    for row in rows(path):
                        mapping=texts(row)
                        if 'en' not in mapping or len(mapping)!=2:
                            raise ValueError('Not an English leg')
                        language=next(l for l in mapping if l!='en')
                        db.execute('INSERT OR IGNORE INTO anchors VALUES (?,?,?,?)',
                            (language,mapping['en'],mapping[language],json.dumps(row['provenance'])))
                    db.commit()
                    print('INDEXED',family,path.parent.name,flush=True)
            db.execute('CREATE INDEX anchor_join ON anchors(english,language)')
            db.execute('DROP TABLE IF EXISTS unique_anchors')
            db.execute('CREATE TABLE unique_anchors AS SELECT language,english,MIN(text) text, '
                'MIN(provenance) provenance FROM anchors GROUP BY language,english HAVING COUNT(*)=1')
            db.execute('CREATE INDEX unique_join ON unique_anchors(language,english)')
            db.commit()
            reports=[]
            for a,b in cfg['requested_pairs']:
                if 'en' in (a,b):
                    continue
                pair=a+'-'+b
                direct=source_root/'translations/candidates'/('opus-'+pair)/'candidates.jsonl'
                seen=set()
                if direct.exists():
                    seen={digest(texts(row)) for row in rows(direct)}
                # Tiny direct supply does not preclude useful, independently audited pivots.
                if len(seen)>=1000:
                    reports.append(dict(pair=pair,state='direct_supply_available',direct_pairs=len(seen)))
                    continue
                directory=root/'candidates'/('opus-'+pair)
                receipt=directory/'receipt.json'
                if receipt.exists():
                    previous=load(receipt)
                    if previous['input_pins']!=inputs or file_hash(directory/'candidates.jsonl')!=previous['sha256']:
                        raise ValueError('Sealed pivot inputs or output changed: '+pair)
                    reports.append(previous)
                    print('REUSED',pair,previous['counts'],flush=True)
                    continue
                counts=Counter()
                with atomic(directory/'candidates.jsonl') as out:
                    matches=db.execute('SELECT a.english,a.text,b.text,a.provenance,b.provenance '
                        'FROM unique_anchors a JOIN unique_anchors b ON a.english=b.english '
                        'WHERE a.language=? AND b.language=? ORDER BY a.english',(a,b))
                    for english,ta,tb,pa,pb in matches:
                        counts['matched']+=1
                        key=digest({a:ta,b:tb})
                        if key in seen:
                            counts['duplicate']+=1
                            continue
                        conversations=[]
                        for src,dst,x,y in ((a,b,ta,tb),(b,a,tb,ta)):
                            conversations.append([dict(role='user',content=f'Translate from {cfg["languages"][src]} into {cfg["languages"][dst]}. Output only the translation.\n\n{x}'),dict(role='assistant',content=y)])
                        seen.add(key)
                        record=dict(id=key,language=b,reverse_language=a,task='translation',pair=pair,
                            messages=conversations[0],reverse_messages=conversations[1],
                            admission_authorized=False,provenance=dict(method='exact_english_anchor_join',
                                english_anchor=english,legs=[json.loads(pa),json.loads(pb)],machine_translated=False),
                            audit_context=dict(english_anchor=english,instruction='Verify both directions and both '
                                'English alignments. Identical English strings do not establish sense equivalence. '
                                'Reject ambiguity or wrong language variants.'))
                        out.write(json.dumps(record,ensure_ascii=False)+'\n')
                        counts['candidate_pairs']+=1
                report=dict(pair=pair,counts=dict(counts),sha256=file_hash(directory/'candidates.jsonl'),
                    budget=cfg['pair_budgets'][pair],audit='pending',input_pins=inputs,
                    native_length_check='Required in parallel baltic_audit translations preflight before queueing',
                    state='pivot_candidates_ready' if counts['candidate_pairs'] else 'no_unambiguous_pivot_supply')
                write_json(directory/'receipt.json',report)
                reports.append(report)
                print('PIVOT',pair,dict(counts),flush=True)
            write_json(root/'manifest.json',dict(pairs=reports,inputs=inputs,
                policy='Exact English anchor joins; ambiguous anchors excluded; audit required; no fabricated translations'))
        finally:
            db.close()


if __name__=='__main__':
    main()
