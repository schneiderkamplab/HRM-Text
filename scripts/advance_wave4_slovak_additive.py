"""Separate additive lifecycle through audit, combined selection and publication."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import time

from dfm12.io import atomic,digest,file_hash,load,lock,write_json


def route_pair(component):
    name=component.removeprefix('sk-additive-v1-')
    route,pair=name.split('-',1)
    return route,pair.split('-part',1)[0]


def publication_guard(root,base,pair):
    """Main and additive locks differ: prove main cannot publish this pair."""
    main=base/'audit/translation-manifest.json'
    manifest=load(main)  # Missing main freeze is a publication blocker.
    if manifest['preparation_sha256']!=file_hash(base/'parallel-preparation.json'):
        raise ValueError('Main preparation freeze changed')
    for entry in manifest['components']:
        name=entry['component']
        if name.startswith('sk-additive-v1-'):
            raise ValueError('Main manifest incorrectly includes additive components')
        if not name.startswith(('direct-','institutional-','pivot-')):continue
        if route_pair(name)[1]!=pair:continue
        sealed=load(base/'audit-ready'/name/'receipt.json')
        if sealed['sha256']!=entry['sha256'] or sealed['counts']['ready']!=0:
            raise ValueError('Main publisher has potential nonzero pair supply')
    receipt=base/'translation-release'/pair/'receipt.json'
    if receipt.exists() and load(receipt).get('selected_pairs',0):
        raise ValueError('Main pair selection is nonzero; explicit replacement coordination required')
    if (base/'translation-release'/pair/'publication.json').exists():
        raise ValueError('Main pair publication exists; preserve it')
    folder=Path('exports_dfm13')/('dfm13-wave4-opus-'+pair)
    if folder.exists():
        raise ValueError('Canonical export already exists; no automatic replacement')
    registry=Path('config/dfm13_sources.json')
    name=('dfm13-wave4-opus-'+pair).replace('-','_')
    if registry.exists() and any(r.get('name')==name for r in load(registry)['additions']):
        raise ValueError('Canonical registry entry exists; no automatic replacement')
    write_json(root/'translation-release'/pair/'publication-ownership.json',dict(
        main_manifest_sha256=file_hash(main),main_publishable_rows=0,
        canonical_export_absent=True,canonical_registry_entry_absent=True,
        policy='new pair only; any replacement requires explicit coordinated successor'))


def select_pair(root,base,pair,entries,manifest):
    from dfm12.wave_repair import process
    from dfm12.wave_translation_selection import PairSelection
    budget=load(root/'translations/token-budgets.json')
    if file_hash(budget['source_report'])!=budget['source_report_sha256']:raise ValueError('Budget provenance changed')
    cap=budget['english_pair_cap' if 'en' in pair.split('-') else 'other_pair_cap']
    folder=root/'translation-release'/pair;folder.mkdir(parents=True,exist_ok=True)
    with lock(folder/'.lock'):
        selection=PairSelection(folder/'selection.sqlite',pair.split('-'),cap)
        pending=[];pins={}
        try:
            for entry in entries:
                name=entry['component']
                if load(base/'audit-ready'/name/'receipt.json')['sha256']!=entry['sha256']:
                    raise ValueError('Combined component pin changed')
                process(base,name)
                ledger=base/'release'/name;state=load(ledger/'status.json');pins[name]=state['input_sha256']
                if not state['export_ready']:pending.append(name);continue
                with closing(sqlite3.connect((ledger/'ledger.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as db:
                    for raw,review in db.execute("SELECT record,review FROM rows WHERE status='accepted' ORDER BY id"):
                        selection.add(json.loads(raw),json.loads(review),name,entry['route'])
                selection.db.commit()
            receipt=dict(pair=pair,token_cap=cap,component_pins=pins,pending_components=pending,
                ready=not pending,uploaded=False,admission_authorized=False,
                audit_manifest_sha256=file_hash(manifest),budget_receipt_sha256=file_hash(root/'translations/token-budgets.json'))
            if not pending:
                count=tokens=0;path=folder/'accepted-pairs.jsonl'
                with atomic(path) as output:
                    for row in selection.selected():
                        output.write(json.dumps(row,ensure_ascii=False)+'\n');count+=1;tokens=row['cumulative_tokens']
                receipt.update(selected_pairs=count,conversation_rows=2*count,combined_rendered_tokens=tokens,
                    shortfall_tokens=cap-tokens,path=str(path.resolve()),sha256=file_hash(path))
            write_json(folder/'receipt.json',receipt)
            return receipt
        finally:selection.close()


def deferred_upload(root,pair,result):
    write_json(root/'translation-release'/pair/'upload-deferred.json',dict(
        reason='repository_creation_daily_quota',uploaded=False,
        selection_sha256=result['sha256'],selected_pairs=result['selected_pairs'],
        requires_explicit_publication_resume=True))
    return 'upload_deferred'


def recovery_first(base,combined,state):
    """Feed bounded audit recovery before rebuilding accepted pair selections."""
    from dfm12.wave_repair import process
    work=[]
    for entry in combined['components']:
        path=base/'release'/entry['component']/'status.json'
        if path.exists():
            status=load(path)
            if status['input_sha256']!=entry['sha256']:raise ValueError('Recovery component seal changed')
            if status.get('terminal'):continue
        work.append((path.exists(),entry['component']))
    for index,(_,name) in enumerate(sorted(work),1):
        process(base,name)
        state('recovery_first',recovery_components=len(work),recovery_completed=index,last_component=name)


def drain_recovery(root,base,combined,state):
    while True:
        recovery_first(base,combined,state)
        evidence=[];pending=[]
        for entry in combined['components']:
            path=base/'release'/entry['component']/'status.json'
            status=load(path)
            if status['input_sha256']!=entry['sha256']:raise ValueError('Drain input changed')
            if not status['terminal']:pending.append(entry['component'])
            evidence.append(dict(component=entry['component'],input_sha256=entry['sha256'],
                status_sha256=file_hash(path),terminal=status['terminal'],counts=status['counts'],
                export_ready=status['export_ready']))
        if not pending:
            write_json(root/'recovery-drain.json',dict(time=time.time(),components=evidence,
                component_count=len(evidence),all_component_ledgers_terminal=True,
                publication_complete=False,admission_authorized=False,
                scope='these component ledgers only; recheck shared queues before GPU handoff'))
            state('recovery_ledgers_terminal',component_count=len(evidence))
            return
        state('waiting_recovery_results',nonterminal_components=pending)
        time.sleep(5)


def run(root,base,enqueue_wait_seconds=43200,defer_uploads=False,prioritize_recovery=False):
    from dfm12.wave4_cpu import enqueue
    from dfm12.wave_translation_release import release
    handoff=base/'slovak-additive-handoff.json'
    def state(phase,**kwargs):
        receipt=dict(time=time.time(),pid=os.getpid(),phase=phase,root=str(root),
            separate_from_main_completion=True,databases=[str(base/'audit/jobs.sqlite'),str(base/'repair/jobs.sqlite')],
            cpu_preparation_complete=False,all_audits_terminal=False,**kwargs)
        write_json(handoff,receipt);print(phase,kwargs,flush=True)
    with lock(root/'advance.lock'):
        state('waiting_cpu_integration')
        while not (root/'integration.json').exists():time.sleep(30)
        integration=load(root/'integration.json');integration_sha=file_hash(root/'integration.json')
        for path,sha in integration['evidence_pins'].items():
            if file_hash(path)!=sha:raise ValueError('License evidence drift')
        completed=root/'enqueue-complete.json'
        if completed.exists():
            receipt=load(completed);queued=receipt['components']
            if receipt['integration_sha256']!=integration_sha or not receipt['cpu_preparation_complete']:
                raise ValueError('Completed enqueue provenance changed')
            with closing(sqlite3.connect((base/'audit/jobs.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as db:
                registered=dict(db.execute('SELECT name,sha FROM components'))
            if len(queued)!=len(set(queued)):raise ValueError('Duplicate completed component')
            for name in queued:
                if registered.get(name)!=load(base/'audit-ready'/name/'receipt.json')['sha256']:
                    raise ValueError('Completed component registration changed')
            state('resuming_finalization',queued_count=len(queued))
        else:
            from scripts.slovak_chunked_preflight import prepare_enqueue
            state('parallel_preflight_enqueue',workers=16,queued_components=[])
            queued=prepare_enqueue(root,base,integration['components'],state,workers=16,
                enqueue_wait_seconds=enqueue_wait_seconds)
            write_json(completed,dict(integration_sha256=integration_sha,components=queued,
                cpu_preparation_complete=True,audits_complete=False,main_completion_is_insufficient=True))
        if defer_uploads:
            write_json(root/'upload-deferred.json',dict(reason='repository_creation_daily_quota',
                time=time.time(),requires_explicit_publication_resume=True))
        state('waiting_main_component_freeze',queued_components=queued)
        while not ((base/'parallel-preparation.json').exists()
                   and (base/'audit/translation-manifest.json').exists()):time.sleep(30)
        manifest=root/'combined-audit-manifest.json'
        if not manifest.exists():
            pairs={'-'.join(p) for p in integration['requested_pairs']};components=[]
            with closing(sqlite3.connect((base/'audit/jobs.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as db:
                for name,sha in db.execute('SELECT name,sha FROM components ORDER BY name'):
                    if not name.startswith(('direct-','institutional-','pivot-','sk-additive-v1-')):continue
                    route,pair=route_pair(name)
                    if pair in pairs:components.append(dict(component=name,sha256=sha,route=route,pair=pair))
            if not set(queued)<=set(e['component'] for e in components):raise ValueError('Missing additive registration')
            write_json(manifest,dict(components=components,integration_sha256=integration_sha,
                main_preparation_sha256=file_hash(base/'parallel-preparation.json'),one_combined_budget=True))
        budget_path=Path('data/dfm13/baltic/translations/token-budgets.json')
        if not (root/'translations/token-budgets.json').exists():write_json(root/'translations/token-budgets.json',load(budget_path))
        combined=load(manifest)
        if combined['integration_sha256']!=integration_sha:raise ValueError('Integration changed')
        while True:
            if prioritize_recovery:drain_recovery(root,base,combined,state)
            outcomes={}
            for pair in sorted('-'.join(p) for p in integration['requested_pairs']):
                entries=[e for e in combined['components'] if e['pair']==pair]
                if not entries:outcomes[pair]='no_candidate_supply';continue
                publication=root/'translation-release'/pair/'publication.json'
                if publication.exists() and load(publication).get('uploaded'):
                    outcomes[pair]='uploaded_and_integrated';continue
                result=select_pair(root,base,pair,entries,manifest)
                if not result['ready']:outcomes[pair]='awaiting_reviews';continue
                if not result['selected_pairs']:outcomes[pair]='no_accepted_supply';continue
                if (root/'upload-deferred.json').exists():
                    outcomes[pair]=deferred_upload(root,pair,result);continue
                publication_guard(root,base,pair)
                try:release(root,pair,upload=True)
                except Exception as exc:
                    if (getattr(getattr(exc,'response',None),'status_code',None)==429
                            and 'rate limit for repository creation' in str(exc)):
                        write_json(root/'upload-deferred.json',dict(reason='repository_creation_daily_quota',
                            time=time.time(),requires_explicit_publication_resume=True))
                        outcomes[pair]=deferred_upload(root,pair,result);continue
                    raise
                outcomes[pair]='uploaded_and_integrated'
            reviews_complete=all(v!='awaiting_reviews' for v in outcomes.values())
            complete=reviews_complete and 'upload_deferred' not in outcomes.values()
            state('complete' if complete else 'uploads_deferred' if reviews_complete else 'audit_selection_release',pairs=outcomes)
            if reviews_complete:
                final=load(handoff);final.update(cpu_preparation_complete=True,all_audits_terminal=True)
                final['publication_complete']=complete
                write_json(handoff,final);write_json(root/'audit-finalization.json',final)
                if complete:write_json(root/'completion.json',final)
                return
            time.sleep(300)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--base',type=Path,default=Path('data/dfm13/wave4'))
    p.add_argument('--enqueue-wait-seconds',type=float,default=43200)
    p.add_argument('--defer-uploads',action='store_true',help='Continue reviews; record explicit quota-held uploads')
    p.add_argument('--recovery-first',action='store_true',help='Materialize missing/nonterminal ledgers before accepted selection')
    a=p.parse_args()
    if a.enqueue_wait_seconds<1800:p.error('--enqueue-wait-seconds must be at least1800')
    run(a.root,a.base,a.enqueue_wait_seconds,a.defer_uploads,a.recovery_first)
