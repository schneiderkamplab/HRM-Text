"""Accepted-only local Baltic native all-target assembly adapter."""
import json
from pathlib import Path
import numpy as np
from .baltic_finished_release import CONTRACT


def unready(e):
    if e.get('publication_contract')!=CONTRACT or e.get('status')!='accepted_local_tokenized' or e.get('uploaded') is not False:
        return 'invalid_baltic_local_contract'
    if not e.get('tokenization_performed') or not e.get('export_manifest_sha256'):
        return 'baltic_tokenization_not_ready'
    return None


def verify(e,contract,pins,api):
    api.require(unready(e) is None,'Baltic not ready')
    export=api.read_json(e['export_manifest'],pins,e['export_manifest_sha256'])
    api.require(all(e.get(k)==v for k,v in export.items()),'Baltic export drift')
    source=api.pin(e['output'],pins,e['output_sha256'])
    proof=api.read_json(e['source_proof'],pins,e['source_proof_sha256'])
    api.pin(Path(e['source_proof']).parent/'accepted-snapshot.sqlite',pins,proof['database_sha256'])
    evidence=api.pin(e['evidence'],pins,e['evidence_sha256'])
    fingerprints=set();evidence_count=0
    with evidence.open() as stream:
        for line in stream:
            item=json.loads(line)
            if item['name']!=e['name']:continue
            api.require(item['fingerprint'] not in fingerprints,'Duplicate Baltic fingerprint')
            fingerprints.add(item['fingerprint']);evidence_count+=1
            for path,sha in item['pins'].items():api.pin(path,pins,sha)
    root=Path(e['tokenized_path']).resolve();info=api.read_json(root/'tokenizer_info.json',pins)
    api.require(api.token_contract(info,pins)==contract,'Baltic tokenizer differs')
    completion=api.read_json(root/'completion.json',pins)
    api.require(not completion['skipped_rows_this_run'] and completion['max_seq_len'] is None,'Baltic truncation/drop')
    parts=[dict(api.verify_arrays(p,contract['vocab_size'],pins),path=str(p),link_name=e['name']+'__'+p.name)
        for p in sorted(root.iterdir()) if p.is_dir()]
    n=sum(p['rows'] for p in parts);tokens=sum(p['tokens'] for p in parts)
    api.require(n==e['training_targets']==completion['rows'] and tokens==e['tokenized_tokens'],'Baltic token totals')
    from .io import digest
    count=targets=0;sample=[]
    with source.open() as stream:
        for line in stream:
            row=json.loads(line);fingerprint=digest({k:row[k] for k in ('messages','tools')})
            api.require(fingerprint in fingerprints,'Unbound Baltic row');fingerprints.remove(fingerprint)
            count+=1;targets+=sum(m['role']=='assistant' for m in row['messages'])
            if len(sample)<3:sample.append(row)
    api.require(not fingerprints and count==e['rows']==evidence_count and targets==n,'Baltic row/target mismatch')
    encode=api.native_encoder(info);part=Path(parts[0]['path'])
    arrays={k:np.load(part/(k+'.npy'),mmap_mode='r') for k in api.FIELDS};ordinal=0
    for row in sample:
        for prompt,response in encode(row,final_only=False):
            for kind,want in [('inst',prompt),('resp',response)]:
                start=int(arrays[kind+'_start'][ordinal]);length=int(arrays[kind+'_len'][ordinal])
                api.require(length==len(want) and arrays['tokens'][start:start+length].tolist()==list(want),'Baltic native mismatch')
            ordinal+=1
    return dict(name=e['name'],source=str(source),repeat=1,rows=n,conversations=count,tokens=tokens,parts=parts,
        tokenized_root=str(root),uploaded=False,hf_revision=None,publication_pending=True,publication_contract=CONTRACT,
        native_token_parity=dict(targets_checked=ordinal,all_assistant_targets=True))
