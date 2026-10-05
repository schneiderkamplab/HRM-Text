import sqlite3
from dfm12.io import write_json,file_hash,load
from scripts import advance_wave4_slovak_additive as m


def test_recovery_first_prioritizes_missing_and_skips_terminal(tmp_path,monkeypatch):
    from dfm12 import wave_repair
    names=['a-pending','b-done','z-missing']
    write_json(tmp_path/'release/a-pending/status.json',dict(input_sha256='sha',terminal=False))
    write_json(tmp_path/'release/b-done/status.json',dict(input_sha256='sha',terminal=True))
    seen=[];states=[]
    monkeypatch.setattr(wave_repair,'process',lambda base,name:seen.append(name))
    m.recovery_first(tmp_path,{'components':[dict(component=n,sha256='sha') for n in names]},
        lambda phase,**kwargs:states.append(kwargs))
    assert seen==['z-missing','a-pending']
    assert states[-1]['recovery_completed']==states[-1]['recovery_components']==2


def test_drain_reconciles_real_status_before_proof(tmp_path,monkeypatch):
    root=tmp_path/'additive';base=tmp_path/'base';path=base/'release/component/status.json'
    write_json(path,dict(input_sha256='sha',terminal=False,export_ready=False,counts={'audit_retry_pending':1}))
    calls=[]
    def process(base,combined,state):
        calls.append(1)
        assert not (root/'recovery-drain.json').exists()
        if len(calls)==2:
            write_json(path,dict(input_sha256='sha',terminal=True,export_ready=False,counts={'audit_retry_failed':1}))
    monkeypatch.setattr(m,'recovery_first',process)
    monkeypatch.setattr(m.time,'sleep',lambda seconds:None)
    m.drain_recovery(root,base,{'components':[dict(component='component',sha256='sha')]},lambda *a,**k:None)
    assert len(calls)==2
    proof=load(root/'recovery-drain.json')
    assert proof['all_component_ledgers_terminal'] and not proof['admission_authorized']
    assert not proof['publication_complete'] and proof['components'][0]['counts']=={'audit_retry_failed':1}


def test_upload_hold_does_not_block_remaining_pairs_or_claim_publication(tmp_path,monkeypatch):
    from dfm12 import wave_translation_release
    from scripts import slovak_chunked_preflight
    root=tmp_path/'additive';base=tmp_path/'base'
    entries=[dict(component='sk-additive-v1-pivot-'+p,sha256='sha',route='pivot',pair=p)
             for p in ['be-sk','en-sk']]
    write_json(root/'integration.json',dict(evidence_pins={},requested_pairs=[['be','sk'],['en','sk']],components=[]))
    sha=file_hash(root/'integration.json')
    write_json(root/'enqueue-complete.json',dict(integration_sha256=sha,cpu_preparation_complete=True,
        components=[e['component'] for e in entries]))
    (base/'audit').mkdir(parents=True)
    with sqlite3.connect(base/'audit/jobs.sqlite') as db:
        db.execute('CREATE TABLE components(name TEXT,sha TEXT)')
        for e in entries:
            db.execute('INSERT INTO components VALUES(?,?)',(e['component'],e['sha256']))
            write_json(base/'audit-ready'/e['component']/'receipt.json',{'sha256':'sha'})
    write_json(base/'parallel-preparation.json',{})
    write_json(base/'audit/translation-manifest.json',{})
    write_json(root/'combined-audit-manifest.json',dict(integration_sha256=sha,components=entries))
    write_json(root/'translations/token-budgets.json',{})
    seen=[]
    def selected(root,base,pair,*args):
        seen.append(pair)
        return dict(ready=True,selected_pairs=1,sha256=pair)
    monkeypatch.setattr(m,'select_pair',selected)
    def forbidden(*args,**kwargs):raise AssertionError('No preparation, guard or upload under deferral')
    monkeypatch.setattr(m,'publication_guard',forbidden)
    monkeypatch.setattr(wave_translation_release,'release',forbidden)
    monkeypatch.setattr(slovak_chunked_preflight,'prepare_enqueue',forbidden)
    m.run(root,base,defer_uploads=True)
    assert seen==['be-sk','en-sk']
    assert not (root/'completion.json').exists()
    final=load(root/'audit-finalization.json')
    assert final['all_audits_terminal'] and not final['publication_complete']
    assert set(final['pairs'].values())=={'upload_deferred'}
    assert load(root/'translation-release/en-sk/upload-deferred.json')['selection_sha256']=='en-sk'
