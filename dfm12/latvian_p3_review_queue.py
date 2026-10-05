"""Fuse independent content candidates without certifying positional hypotheses."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import unicodedata

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .io import digest, file_hash, load, rows, write_json
from .jobs import Queue
from .latvian_p3_alignment import MODEL, question_key
from .latvian_p3_content_alignment import REVIEW, STAGE, wilson
from .latvian_p3_export import check


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(c))


def lexical_candidates(english, latvian, k=5):
    """Character overlap is a second retrieval signal, not bilingual equivalence."""
    vectorizer=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),preprocessor=fold,
        min_df=1,max_features=200000,dtype=np.float32)
    matrix=vectorizer.fit_transform(english+latvian)
    reference=matrix[:len(english)]
    for start in range(0,len(latvian),128):
        score=(matrix[len(english)+start:len(english)+start+128] @ reference.T).toarray()
        for value in score:
            # English inventory is content-ID sorted before this call.
            indices=np.argsort(-value,kind='stable')[:k]
            yield [(int(i),float(value[i])) for i in indices if value[i]>0]


def fuse(catalog, semantic, lexical, positional, verified):
    origin=defaultdict(list)
    for kind,ids in [('semantic_content',semantic),('lexical_content',lexical),
                     ('positional_unverified',positional),('manual_bridge', [verified] if verified else [])]:
        for key in ids:
            check(key in catalog, 'Unknown reference content ID')
            origin[key].append(kind)
    return [dict(catalog[key],retrieval_origins=sorted(set(origin[key])),
                 pairing_verified=(key==verified)) for key in sorted(origin)]


def semantic_scores(record):
    check(len(record['english_candidates'])==len(record['retrieval_scores']), 'Score/reference mismatch')
    return {candidate['candidate_id']:score for candidate,score in
            zip(record['english_candidates'],record['retrieval_scores'])}


def prepare(root, content_root, previous_packet, english_cache):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);content_root=Path(content_root)
    source=content_root/'content-proposals.jsonl';manifest=load(content_root/'manifest.json')
    check(file_hash(source)==manifest['files']['content-proposals.jsonl'],'Semantic proposals changed')
    pins={str(p):file_hash(p) for p in [source,previous_packet,english_cache,Path(__file__)]}
    if (root/'input-pins.json').exists():check(load(root/'input-pins.json')==pins,'Resumed inputs changed')
    else:write_json(root/'input-pins.json',pins)
    old={r['id']:r for r in rows(previous_packet)};grouped=defaultdict(list);catalog=defaultdict(dict)
    for record in rows(source):grouped[record['provenance']['file'].split('/')[0]].append(record)
    for item in load(english_cache)['files']:
        check(file_hash(item['path'])==item['sha256'],'Raw English snapshot changed')
        config=item['config']
        for record in rows(item['path']):
            text=question_key(config,record['inputs_pretokenized'])[1];key=digest([config,text])
            group=catalog[config].setdefault(key,dict(candidate_id=key,config=config,question=text,
                source_answers=[],source_snapshot=item))
            if record['targets_pretokenized'] not in group['source_answers']:
                group['source_answers'].append(record['targets_pretokenized'])
    counts=Counter();diagnostic=Counter();inventory=[];queue=Queue(root/'review.sqlite')
    try:
        with (root/'requests.jsonl').open('w') as out:
            for config,records in sorted(grouped.items()):
                ids=sorted(catalog[config]);refs=[catalog[config][i] for i in ids]
                lexical=lexical_candidates([r['question'] for r in refs],[r['messages'][0]['content'] for r in records])
                for record,ranked in zip(records,lexical):
                    current=old[record['id']];check(current['record_sha256']==record['record_sha256'],'Record drift')
                    semantic=[r['candidate_id'] for r in record['english_candidates'][:5]]
                    lex=[ids[i] for i,score in ranked]
                    position={digest([config,question_key(config,r['question'])[1]]) for r in current['english_question_matches']}
                    verified=record['verified_manual_candidate_id']
                    if verified:
                        diagnostic['rows']+=1;diagnostic['lexical_top1']+=bool(lex) and lex[0]==verified
                        diagnostic['lexical_top5']+=verified in lex
                        diagnostic['content_union']+=verified in set(semantic+lex)
                        diagnostic['content_plus_positional']+=verified in set(semantic+lex+list(position))
                    candidates=fuse(catalog[config],semantic,lex,position,verified)
                    packet=dict(record,english_candidates=candidates,
                        candidate_order='content_ID_not_confidence',
                        semantic_rank=semantic,lexical_rank=lex,
                        semantic_scores_by_candidate=semantic_scores(record),
                        positional_proposals=sorted(position),
                        source_alignment_status='manual_bridge_retained' if verified else 'multiple_proposals_unverified',
                        uncertainty=dict(semantic_diagnostics=record['uncertainty'],semantic_lexical_top1_agree=bool(lex) and semantic[0]==lex[0],
                            content_channels_recover_positional=bool(position & set(semantic+lex)),
                            pairing_probability_interval=[0,1] if not verified else None),
                        automatic_admission=False)
                    packet.pop('retrieval_scores')
                    request=dict(model=MODEL,temperature=0,max_tokens=8192,
                        chat_template_kwargs={'enable_thinking':False},response_format={'type':'json_object'},
                        messages=[dict(role='system',content=REVIEW+'\nCandidates are ordered by content ID, not rank. '
                            'Positional alternatives are explicitly unverified and receive no priority. '
                            'If neither content candidates nor positional alternatives support identity, select null. '
                            'Do not treat agreement between retrieval methods as certification.'),
                            dict(role='user',content=json.dumps(packet,ensure_ascii=False))])
                    payload=dict(schema='p3-source-fidelity-fused-v1',record=packet,request=request,automatic_admission=False)
                    key=queue.add(STAGE,payload);inventory.append(dict(job_id=key,id=record['id'],record_sha256=record['record_sha256']))
                    out.write(json.dumps(dict(job_id=key,**payload),ensure_ascii=False)+'\n')
                    counts['rows']+=1;counts['manual_bridges']+=bool(verified)
                    counts['content_positional_disagreement']+=not bool(position & set(semantic+lex))
                    counts['semantic_lexical_top1_agree']+=packet['uncertainty']['semantic_lexical_top1_agree']
                    counts['max_reference_groups']=max(counts['max_reference_groups'],len(candidates))
                print('Fused',config,len(records),flush=True)
        write_json(root/'inventory.json',inventory)
        for path,sha in pins.items():check(file_hash(path)==sha,'Input changed')
        result=dict(schema='p3-fused-content-review-queue-v1',counts=dict(counts),manual_diagnostic=dict(diagnostic),
            manual_content_union_wilson95=wilson(diagnostic['content_union'],diagnostic['rows']),
            diagnostic_scope='Existing stratified manual20; not population calibration; no per-row probability estimate',
            inputs=pins,queue_status=queue.status(),stage=STAGE,model=MODEL,requests_sent_by_builder=0,
            automatic_admission=False,source_hold_cleared=False,
            files={p:file_hash(root/p) for p in ['requests.jsonl','inventory.json']})
        write_json(root/'manifest.json',result);return result
    finally:queue.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in ['root','content-root','previous-packet','english-cache']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.root,a.content_root,a.previous_packet,a.english_cache),indent=2))
