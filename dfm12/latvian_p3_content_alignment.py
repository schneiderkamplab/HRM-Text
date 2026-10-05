"""CPU multilingual content retrieval and an unsent resumable 31B review queue."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
import sqlite3

import numpy as np

from .io import digest, file_hash, load, rows, write_json
from .jobs import Queue
from .latvian_p3_alignment import AUDIT, MODEL, question_key
from .latvian_p3_export import check

STAGE = 'p3_source_fidelity_31b'
POLICY = 'e5-symmetric-query-chunk480-mean-v1'
REVIEW = AUDIT + """
Several English candidates are provided, ranked only by heuristic CPU similarity.
Scores and rank are NOT confidence or verified identity. Select candidate_id or
null if none is a defensible source. Compare alternatives rather than accepting
the first one. Report missing/changed premises even when the Latvian answer looks
plausible. English source answers are noisy references, never mandatory gold.
Do not generate a correction in this audit: return separate dimensions and
literal evidence from the full supplied texts. Any future repair must preserve
the complete question and target, documenting source-context changes explicitly.
No review response automatically changes source holds or training admission."""


def chunks(values, size=480):
    return [values[i:i+size] for i in range(0, len(values), size)] or [[]]


def wrap_xlmr(tokenizer, ids):
    # Verify the pinned encoder's single-sequence framing across tokenizer API versions.
    probe=tokenizer.encode('test',add_special_tokens=False)
    check(tokenizer.encode('test',add_special_tokens=True)==[tokenizer.bos_token_id]+probe+[tokenizer.eos_token_id],
          'Unexpected encoder special-token framing')
    return [tokenizer.bos_token_id]+ids+[tokenizer.eos_token_id]


def rank(vectors, query, ids, k=5):
    scores = vectors @ query
    # Content IDs break ties; neither source nor candidate row ordinal is used.
    return sorted(range(len(ids)), key=lambda i: (-float(scores[i]), ids[i]))[:k], scores


def uncertainty(question, candidates, scores):
    gap = float(scores[0]-scores[1]) if len(scores)>1 else None
    numbers = lambda text: sorted(set(re.findall(r'\b\d+(?:[.,]\d+)?\b', text)))
    return dict(top1_top2_margin=gap, near_tie=gap is not None and gap < .02,
        numeric_anchor_mismatch=numbers(question) != numbers(candidates[0]['question']),
        probability_interval=[0.0, 1.0],
        probability_basis='No calibrated correctness bound; cosine and margin are retrieval diagnostics only',
        verified=False)


def wilson(successes, total):
    if not total: return [0.0, 1.0]
    z=1.96; p=successes/total; d=1+z*z/total
    center=(p+z*z/(2*total))/d
    radius=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return [max(0,center-radius), min(1,center+radius)]


class CPUEncoder:
    def __init__(self, model_receipt, database, threads=4):
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.torch = torch
        torch.set_num_threads(threads)
        self.receipt = load(model_receipt)
        for path, sha in self.receipt['files'].items(): check(file_hash(path)==sha, 'Embedding model changed')
        self.contract = digest([self.receipt['files'], POLICY])
        self.db = sqlite3.connect(database)
        self.db.execute('CREATE TABLE IF NOT EXISTS embeddings (key TEXT PRIMARY KEY, vector BLOB)')
        self.tokenizer = AutoTokenizer.from_pretrained(self.receipt['path'], local_files_only=True)
        self.model = AutoModel.from_pretrained(self.receipt['path'], local_files_only=True,
            use_safetensors=True).to('cpu').eval()
        self.prefix = self.tokenizer.encode('query: ', add_special_tokens=False)

    def encode(self, texts, batch=16):
        result = []
        for start in range(0, len(texts), batch):
            batch_texts = texts[start:start+batch]; pending = []; vectors = {}
            for i,text in enumerate(batch_texts):
                key = digest([self.contract, text]); cached = self.db.execute('SELECT vector FROM embeddings WHERE key=?',(key,)).fetchone()
                if cached: vectors[i] = np.frombuffer(cached[0], dtype=np.float32).copy()
                else: pending.append((i,key,text))
            pieces = []; owners = []; weights = []
            for i,key,text in pending:
                ids = self.tokenizer.encode(text, add_special_tokens=False)
                for part in chunks(ids):
                    pieces.append(dict(input_ids=wrap_xlmr(self.tokenizer,self.prefix+part)))
                    owners.append(i); weights.append(max(1,len(part)))
            sums = {}; totals = Counter()
            for lo in range(0,len(pieces),batch):
                inputs = self.tokenizer.pad(pieces[lo:lo+batch], padding=True, return_tensors='pt')
                with self.torch.inference_mode():
                    hidden = self.model(**inputs).last_hidden_state
                    mask = inputs['attention_mask'].unsqueeze(-1)
                    pooled = (hidden*mask).sum(1)/mask.sum(1)
                for offset, vec in enumerate(pooled.numpy()):
                    owner=owners[lo+offset]; weight=weights[lo+offset]
                    sums[owner]=sums.get(owner,0)+vec*weight; totals[owner]+=weight
            for i,key,text in pending:
                vec=sums[i]/totals[i]; vec=(vec/max(float(np.linalg.norm(vec)),1e-12)).astype(np.float32)
                vectors[i]=vec
                self.db.execute('INSERT OR REPLACE INTO embeddings VALUES (?,?)',(key,vec.tobytes()))
            self.db.commit()
            result.extend(vectors[i] for i in range(len(batch_texts)))
            if start % 256 == 0: print('CPU encoded', start+len(batch_texts), '/',len(texts),flush=True)
        return np.stack(result)

    def close(self): self.db.close()


def queue_record(queue, packet):
    payload = dict(schema='p3-source-fidelity-content-review-v1', record=packet,
        automatic_admission=False, request=dict(model=MODEL, temperature=0, max_tokens=8192,
            chat_template_kwargs={'enable_thinking':False}, response_format={'type':'json_object'},
            messages=[dict(role='system',content=REVIEW),
                dict(role='user',content=json.dumps(packet,ensure_ascii=False))]))
    return queue.add(STAGE, payload), payload


def prepare(root, source_packet, cache_manifest, model_receipt, threads=4):
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    pins={str(p):file_hash(p) for p in (source_packet,cache_manifest,model_receipt)}
    pins[str(Path(__file__))]=file_hash(__file__)
    if (root/'input-pins.json').exists(): check(load(root/'input-pins.json')==pins,'Resumed inputs changed')
    else: write_json(root/'input-pins.json',pins)
    source_rows=list(rows(source_packet)); by_config=defaultdict(list)
    for row in source_rows: by_config[row['provenance']['file'].split('/')[0]].append(row)
    catalog=defaultdict(dict)
    for item in load(cache_manifest)['files']:
        check(file_hash(item['path'])==item['sha256'],'English cache changed')
        for raw in rows(item['path']):
            config=item['config']; text=question_key(config,raw['inputs_pretokenized'])[1]
            key=digest([config,text]); group=catalog[config].setdefault(key,dict(candidate_id=key,config=config,
                question=text, source_answers=[],source_snapshot=item))
            if raw['targets_pretokenized'] not in group['source_answers']: group['source_answers'].append(raw['targets_pretokenized'])
    encoder=CPUEncoder(model_receipt,root/'embeddings.sqlite',threads)
    queue=Queue(root/'review.sqlite'); counts=Counter(); manual=Counter(); inventory=[]
    try:
        with (root/'content-proposals.jsonl').open('w') as output, (root/'requests.jsonl').open('w') as requests:
            for config, inputs in sorted(by_config.items()):
                references=sorted(catalog[config].values(),key=lambda r:r['candidate_id'])
                ids=[r['candidate_id'] for r in references]
                english=encoder.encode([r['question'] for r in references])
                latvian=encoder.encode([r['messages'][0]['content'] for r in inputs])
                # This matrix is bounded to one small P3 constituent, not the whole corpus.
                reverse=(latvian @ english.T).argmax(axis=0)
                for i,row in enumerate(inputs):
                    indices,scores=rank(english,latvian[i],ids)
                    candidates=[references[j] for j in indices]
                    ordered_scores=[float(scores[j]) for j in indices]
                    uncertain=uncertainty(row['messages'][0]['content'],candidates,ordered_scores)
                    uncertain['mutual_nearest']=bool(reverse[indices[0]]==i)
                    counts['near_tie']+=uncertain['near_tie'];counts['numeric_mismatch']+=uncertain['numeric_anchor_mismatch']
                    is_manual=row['source_alignment_status']=='manual_bilingual_bridge_exact_english_question'
                    verified = None
                    if is_manual:
                        verified=digest([config,question_key(config,row['english_reference']['question'])[1]])
                        manual['rows']+=1;manual['top1']+=ids[indices[0]]==verified
                        manual['top5']+=verified in [ids[j] for j in indices]
                        if verified not in [ids[j] for j in indices]:
                            candidates.append(catalog[config][verified])
                            ordered_scores.append(float(scores[ids.index(verified)]))
                    packet=dict(id=row['id'],record_sha256=row['record_sha256'],messages=row['messages'],
                        provenance=row['provenance'],source_path=row['source_path'],source_sha256=row['source_sha256'],
                        translated_source=row['translated_source'],source_alignment_status=(
                            'manual_bridge_retained' if is_manual else 'content_ranked_proposals_unverified'),
                        verified_manual_candidate_id=verified,english_candidates=candidates,
                        retrieval_scores=ordered_scores,uncertainty=uncertain,
                        prior_ordinal_candidate_excluded_from_scoring=True,
                        full_target_preserved=True,admission_authorized=False)
                    key,payload=queue_record(queue,packet)
                    output.write(json.dumps(packet,ensure_ascii=False)+'\n')
                    requests.write(json.dumps(dict(job_id=key,**payload),ensure_ascii=False)+'\n')
                    inventory.append(dict(job_id=key,id=row['id'],record_sha256=row['record_sha256']))
                    counts['rows']+=1
                print(config, 'queued',len(inputs),flush=True)
        write_json(root/'inventory.json',inventory)
        for path,sha in pins.items():check(file_hash(path)==sha,'Input changed during preparation')
        result=dict(schema='p3-content-retrieval-queue-v1',counts=dict(counts),manual_diagnostic=dict(manual),
            manual_top1_wilson95=wilson(manual['top1'],manual['rows']),
            manual_top5_wilson95=wilson(manual['top5'],manual['rows']),
            diagnostic_scope='Existing stratified manual20, not fresh heldout or representative population; intervals are descriptive binomial calculations only',
            uncertainty_policy='Heuristic similarities, ties, numeric mismatches and mutual neighbors are NOT calibrated identity probabilities; unverified rows keep probability bounds [0,1].',
            inputs=pins,encoder_policy=POLICY,device='cpu',cpu_threads=threads,model=MODEL,
            stage=STAGE,queue_status=queue.status(),requests_sent=0,automatic_admission=False,
            source_hold_cleared=False,code_sha256=file_hash(__file__),
            files={p:file_hash(root/p) for p in ['content-proposals.jsonl','requests.jsonl','inventory.json']})
        write_json(root/'manifest.json',result)
        return result
    finally:
        encoder.close();queue.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ['root','source-packet','cache-manifest','model-receipt']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--threads',type=int,default=4)
    a=p.parse_args();print(json.dumps(prepare(a.root,a.source_packet,a.cache_manifest,a.model_receipt,a.threads),indent=2))
