"""Complete frozen-cohort packet, including rejected sources and failed attempts."""
import argparse
from pathlib import Path
from collections import Counter
from dfm12.io import rows,load,file_hash,lock,write_json
from scripts.dfm16_story_calibration import immutable,immutable_rows,sha
from scripts.dfm16_staged_validation import verify_freeze
from scripts.dfm16_staged_validation_campaign import ROOT
from scripts.queue_dfm16_stories_qwen import audited_records
from scripts.dfm16_staged_stories import StagedGenerate


def packet(root,language):
    verify_freeze(root,language)
    cohort=root/language/'validation'
    selected=list(rows(cohort/'families.jsonl'));results={};pins={}
    for stage in sorted((cohort/'generation').glob('*')):
        if not stage.is_dir():continue
        if load(stage/'state.json')['phase']!='complete':raise ValueError('generation incomplete')
        adapter=StagedGenerate(stage,stage/'audit','https://api.odincore.ai/v1');adapter.model='odin-2-large'
        for job in load(stage/'manifest.json')['chunks']:
            adapter.verify_receipt(job,stage/'audit'/job['job_id'])
        # Backfill wrapper completion metadata only after validating all immutable receipts.
        write_json(stage/'audit/pipeline/state.json',dict(phase='complete'))
        for r,v in audited_records(stage):
            if r['id'] in results:raise ValueError('duplicate generated source')
            results[r['id']]=(r,v)
        pins[str(stage/'source-receipt.json')]=file_hash(stage/'source-receipt.json')
    packets=[];private=[]
    for index,raw in enumerate(selected):
        review_path=cohort/'source-review'/f'{index:04d}.json';review=load(review_path)
        pins[str(review_path)]=file_hash(review_path)
        identifier=sha(['validation-blind',raw['family'],language])
        if 'generation_input' in review:
            r,v=results.pop(review['id'])
            if r!=review['generation_input']:raise ValueError('source input changed')
            value=dict(id=identifier,language=language,task=raw['task'],authoritative_source=raw['text'],
                messages=v.get('messages',v.get('candidate',{}).get('messages')),status=v['status'],
                deterministic=v.get('cpu'),first_attempt_contract_clear=v.get('first_attempt_contract_clear'),
                stages={name:dict(attempts=[dict(text=a.get('text'),findings=a.get('findings'),error=a.get('error')) for a in st.get('attempts',[])]) for name,st in v.get('stages',{}).items()})
        else:
            value=dict(id=identifier,language=language,task=raw['task'],authoritative_source=raw['text'],
                messages=None,status='source_rejected',source_review=review['assessment'],stages={})
        packets.append(value)
        private.append(dict(id=identifier,source_id=review['id'],index=index,family=raw['family'],task=raw['task']))
    if results:raise ValueError('unexpected generated sources')
    immutable_rows(cohort/'blind-packet.jsonl',packets)
    immutable_rows(cohort/'provenance-private.jsonl',private)
    immutable(cohort/'packet-receipt.json',dict(sample=file_hash(cohort/'families.jsonl'),packet=file_hash(cohort/'blind-packet.jsonl'),inputs=pins,reference='provisional assistant-manual',judge_votes_exposed=False))
    write_json(root/language/'status.json',dict(phase='awaiting_blind_conversation_labels',sampled=800,sources_reviewed=800,packet_statuses=dict(Counter(r['status'] for r in packets)),judged=0,qualified=False))
    return dict(Counter(r['status'] for r in packets))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--language',default='en');a=p.parse_args()
    with lock(a.root/'.controller.lock'):print(packet(a.root,a.language))
