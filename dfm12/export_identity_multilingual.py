"""Accepted-only completed identity21 export and explicitly authorized Hub update."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sqlite3
import time

from . import identity_multilingual_queue as queue
from .export_validator import training_rows
from .identity_extension import write_rows
from .io import digest, file_hash, load, lock, rows, write_json
from .jobs import audit_payload, validate_audit
from .records import chat_fingerprint, validate_messages


def preserve_license(folder,prior):
    import yaml
    def front(text):
        if not text.startswith('---\n'):return {},text
        _,header,body=text.split('---',2)
        return yaml.safe_load(header) or {},body
    previous,_=front(prior)
    licensing={k:v for k,v in previous.items() if k.startswith('license')}
    if licensing:
        path=folder/'README.md';current,body=front(path.read_text());current.update(licensing)
        path.write_text('---\n'+yaml.safe_dump(current,sort_keys=False,allow_unicode=True)+'---'+body)
        manifest=load(folder/'metadata/manifest.json')
        manifest['prior_hub_license']=licensing;manifest['files']['README.md']=file_hash(path)
        write_json(folder/'metadata/manifest.json',manifest)


def validate_records(records,language,expected=2000):
    if len(records)!=expected:raise ValueError('Conversation count mismatch')
    ids=set();fingerprints=set()
    for row in records:
        validate_messages(row['messages'])
        if set(row)!={'id','messages','language','task','parent_pair_id','direction'}:
            raise ValueError('Unexpected training fields')
        if row['language']!=language or row['task']!='identity' or row['direction']!='native' or row['parent_pair_id'] is not None:
            raise ValueError('Training language/task/schema mismatch')
        fp=chat_fingerprint(row['messages'])
        if row['id'] in ids or fp in fingerprints:raise ValueError('Duplicate training conversation')
        ids.add(row['id']);fingerprints.add(fp)


def accepted_record(job,recipe,owner):
    payload=json.loads(job['payload']);candidate=json.loads(job['candidate'])
    generation=json.loads(job['generation_result']);audit=json.loads(job['audit_result'])
    expected=queue.request(job['language'],job['slot'],recipe)
    if job['state']!='accepted' or payload!=expected or job['id']!=expected['record']['id']:
        raise ValueError('Accepted request provenance mismatch')
    if candidate!=dict(payload['record'],messages=generation['messages'],component='identity-xl-full-bp',rendered_tokens=candidate['rendered_tokens']):
        raise ValueError('Accepted generation mismatch')
    if type(candidate['rendered_tokens']) is not int or candidate['rendered_tokens']<=0:
        raise ValueError('Missing pinned native render validation')
    if json.loads(job['audit_payload'])!=audit_payload(candidate,queue.MODEL):
        raise ValueError('Audit record mismatch')
    validate_audit(audit)
    if audit['keep'] is not True or owner!=job['id']:raise ValueError('Unaccepted or unowned candidate')
    return candidate,dict(kind='new_automated_identity_audit',job_id=job['id'],audit=audit,
        candidate_sha256=digest(candidate),generation_payload_sha256=digest(payload),
        generation_result_sha256=digest(generation),audit_payload_sha256=digest(json.loads(job['audit_payload'])),
        audit_result_sha256=digest(audit),human_reviewed=False,native_gold=False)


def validate(folder):
    folder=Path(folder);manifest=load(folder/'metadata/manifest.json')
    for path,sha in manifest['files'].items():
        resolved=(folder/path).resolve()
        if not resolved.is_relative_to(folder.resolve()) or file_hash(resolved)!=sha:
            raise ValueError('Export file/hash mismatch')
    records=list(rows(folder/'data/train-00000.jsonl.gz'))
    validate_records(records,manifest['language'],manifest['rows'])
    provenance=list(rows(folder/'metadata/provenance.jsonl.gz'))
    if len(provenance)!=len(records):raise ValueError('Provenance coverage mismatch')
    for row,receipt in zip(records,provenance):
        if receipt['id']!=row['id'] or receipt['training_row_sha256']!=digest(row):raise ValueError('Row provenance mismatch')
        if receipt['kind']=='new_automated_identity_audit':
            validate_audit(receipt['audit'])
            if not receipt['audit']['keep']:raise ValueError('Rejected audit in export')
        elif receipt['kind'] not in ('corrected_v4_local_curated','retained_audited_original'):
            raise ValueError('Unknown retained admission kind')
    return dict(rows=len(records),language=manifest['language'],kinds=dict(Counter(p['kind'] for p in provenance)))


def build(root,output):
    root=Path(root).resolve();output=Path(output).resolve()
    if output.exists():raise FileExistsError(output)
    with lock(root/'queue.lock'):
        source=queue.verify(root)
        db=sqlite3.connect((root/'queue.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
        try:
            groups=[dict(r) for r in db.execute('SELECT * FROM targets')]
            if set(g['language'] for g in groups)!=set(queue.LANGUAGES) or any(g['target']!=2000 or g['retained']+g['accepted_new']!=2000 or g['active'] for g in groups):
                raise ValueError('All 21 accepted targets must be complete and idle')
            if db.execute("SELECT 1 FROM jobs WHERE state IN ('queued','generating','audit_pending','auditing') LIMIT 1").fetchone():
                raise ValueError('Nonterminal queue work')
            output.mkdir(parents=True);(output/'private').mkdir()
            snapshot=sqlite3.connect(output/'private/queue.sqlite')
            try:db.backup(snapshot)
            finally:snapshot.close()
            source_sha=file_hash(output/'private/queue.sqlite');recipe=load(root/'recipe.json');packages=[]
            for lang in queue.LANGUAGES:
                name=f'dfm12-identity-xl-full-bp-{lang}';folder=output/name
                (folder/'data').mkdir(parents=True);(folder/'metadata').mkdir()
                records=[];provenance=[]
                for row in rows(root/'retained'/f'{lang}.jsonl.gz'):
                    records.append(row)
                    provenance.append(dict(id=row['id'],training_row_sha256=digest(row),
                        kind='corrected_v4_local_curated' if lang in ('da','en') else 'retained_audited_original',
                        retained_file_sha256=source['files'][f'retained/{lang}.jsonl.gz'],
                        human_reviewed=False,native_gold=False))
                for job in db.execute("SELECT * FROM jobs WHERE language=? AND state='accepted' ORDER BY slot",(lang,)):
                    candidate=json.loads(job['candidate']);fp=chat_fingerprint(candidate['messages'])
                    owner=db.execute('SELECT owner FROM seen WHERE fingerprint=?',(fp,)).fetchone()
                    candidate,receipt=accepted_record(job,recipe,owner[0] if owner else None)
                    row=next(training_rows(candidate));records.append(row)
                    provenance.append(dict(receipt,id=row['id'],training_row_sha256=digest(row)))
                validate_records(records,lang)
                write_rows(folder/'data/train-00000.jsonl.gz',records)
                write_rows(folder/'metadata/provenance.jsonl.gz',provenance)
                write_json(folder/'metadata/source.json',dict(queue_manifest_sha256=file_hash(root/'manifest.json'),
                    completed_snapshot_sha256=source_sha,source_pins=source['source_pins'],
                    implementation_pins=source['implementation_pins'],exporter_sha256=file_hash(__file__),
                    training_only=True,heldout_included=False,failed_included=False))
                shutil.copyfile(queue.identity.FACTS,folder/'metadata/identity_facts.yaml')
                write_json(folder/'metadata/runtime-binding.json',recipe['grounding']['current_runtime'])
                kinds=dict(Counter(p['kind'] for p in provenance))
                card=f'''---
language:
- {"pt" if lang=="pt_pt" else lang}
task_categories:
- text-generation
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-*.jsonl.gz
---
# {name}

2,000 distinct Mimir XL full-backpropagation identity conversations. Only data/ is training input.
Language/standard: {queue.LANGUAGES[lang]} ({lang}). Full native messages; physical repetition one.

Admission categories: {json.dumps(kinds,sort_keys=True)}.
New conversations passed automated factual/language/coherence/usefulness identity audits.
Retained DA/EN uses the corrected v4 local corpus, including agent-authored curated additions;
these retained rows are NOT all teacher-audited. Other retained originals came from audited accepted exports.
Not human-reviewed or native-speaker certified. No heldouts, failed or rejected candidates are exported.
Per-row admission provenance, audit decisions and hashes are in metadata/.

User-authorized generated identity release; factual references are retained and no blanket relicensing
of those references is asserted. This preserves the prior identity release policy; no new license is invented.
Historical v1 claims remain qualified. Current tokenizer/template wording follows the corrected runtime binding.
'''
                (folder/'README.md').write_text(card)
                manifest=dict(schema='dfm12-identity21-accepted-export-v1',name=name,language=lang,rows=2000,
                    admission_kinds=kinds,physical_row_repetition=1,repeat=10,
                    files={str(p.relative_to(folder)):file_hash(p) for p in sorted(folder.rglob('*')) if p.is_file()},
                    hf_repo_id='schneiderkamplab/'+name,license_policy='User-authorized generated identity release; no blanket relicensing asserted')
                write_json(folder/'metadata/manifest.json',manifest)
                packages.append(dict(name=name,**validate(folder)))
                print('BUILT',name,2000,flush=True)
            write_json(output/'manifest.json',dict(packages=packages,rows=42000,source_snapshot_sha256=source_sha))
        finally:db.close()
    return output


def publish(output):
    from huggingface_hub import HfApi,CommitOperationAdd,CommitOperationDelete,hf_hub_download
    from huggingface_hub.errors import RepositoryNotFoundError
    output=Path(output);api=HfApi();api.whoami()
    with lock(output/'upload.lock'):
        receipt_path=output/'upload-receipts.json';receipts=load(receipt_path) if receipt_path.exists() else {}
        for package in load(output/'manifest.json')['packages']:
            folder=output/package['name'];validate(folder);manifest=load(folder/'metadata/manifest.json')
            repo=manifest['hf_repo_id'];sha=file_hash(folder/'metadata/manifest.json')
            if receipts.get(repo,{}).get('status')=='verified':
                if receipts[repo]['manifest_sha256']!=sha:raise ValueError('Published package drift')
                continue
            try:previous=api.repo_info(repo,repo_type='dataset')
            except RepositoryNotFoundError:previous=None
            old_files=set(api.list_repo_files(repo,repo_type='dataset',revision=previous.sha)) if previous else set()
            if previous:
                card=hf_hub_download(repo,'README.md',repo_type='dataset',revision=previous.sha)
                prior=Path(card).read_text()
                (output/'private'/f"{package['name']}-prior-README.md").write_text(prior)
                if 'no blanket relicensing' not in prior:
                    raise ValueError('Unexpected prior license/card policy: '+repo)
                preserve_license(folder,prior)
                validate(folder)
                sha=file_hash(folder/'metadata/manifest.json')
            api.create_repo(repo,repo_type='dataset',private=False,exist_ok=True)
            parent_revision=previous.sha if previous else api.repo_info(repo,repo_type='dataset').sha
            if previous is None and set(api.list_repo_files(repo,repo_type='dataset',revision=parent_revision))-{'.gitattributes'}:
                raise ValueError('New repository concurrently populated: '+repo)
            files={str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file()}
            operations=[CommitOperationAdd(path_in_repo=p,path_or_fileobj=str(folder/p)) for p in sorted(files)]
            operations.extend(CommitOperationDelete(path_in_repo=p) for p in sorted(old_files-files-{'.gitattributes'}))
            receipts[repo]=dict(status='publishing',manifest_sha256=sha,previous_revision=previous.sha if previous else None,rows=2000,started=time.time())
            write_json(receipt_path,receipts)
            commit=api.create_commit(repo,repo_type='dataset',operations=operations,
                parent_commit=parent_revision,commit_message='Update completed identity21 accepted-only corpus with truthful retained provenance')
            remote=set(api.list_repo_files(repo,repo_type='dataset',revision=commit.oid))
            if remote-{'.gitattributes'}!=files:raise ValueError('Remote inventory mismatch')
            for name in files:
                downloaded=hf_hub_download(repo,name,repo_type='dataset',revision=commit.oid)
                if file_hash(downloaded)!=file_hash(folder/name):raise ValueError('Remote content mismatch')
            data=hf_hub_download(repo,'data/train-00000.jsonl.gz',repo_type='dataset',revision=commit.oid)
            validate_records(list(rows(data)),manifest['language'])
            receipts[repo].update(status='verified',revision=commit.oid,completed=time.time(),remote_rows=2000)
            write_json(receipt_path,receipts);print('VERIFIED',repo,commit.oid,2000,flush=True)
        write_json(output/'upload-completion.json',dict(repositories=len(receipts),rows=sum(r['remote_rows'] for r in receipts.values()),completed=time.time()))


def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--upload',action='store_true')
    args=parser.parse_args();build(args.root,args.output)
    if args.upload:publish(args.output)


if __name__=='__main__':main()
