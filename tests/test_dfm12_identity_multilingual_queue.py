import json
import sqlite3

import pytest

from dfm12 import identity_multilingual_queue as m
from dfm12.io import digest, file_hash, write_json


def messages(text='A new natural question'):
    return [{'role':'user','content':text},{'role':'assistant','content':'I am Mimir.'}]


@pytest.fixture
def root(tmp_path):
    recipe=m.recipe();write_json(tmp_path/'recipe.json',recipe)
    db=sqlite3.connect(tmp_path/'queue.sqlite',isolation_level=None)
    retained={lang:([{}] if lang!='da' else []) for lang in m.LANGUAGES}
    m.initialize(db,retained,1,recipe,heldouts={m.heldout_hash('Sealed question')})
    db.close()
    manifest=dict(version=m.VERSION,files={'recipe.json':file_hash(tmp_path/'recipe.json')},source_pins={},implementation_pins={})
    write_json(tmp_path/'manifest.json',manifest)
    write_json(tmp_path/'seal.json',{'manifest_sha256':file_hash(tmp_path/'manifest.json')})
    with sqlite3.connect(tmp_path/'queue.sqlite') as db:
        db.execute('INSERT INTO metadata VALUES (?,?)',('manifest_sha256',file_hash(tmp_path/'manifest.json')))
    return tmp_path


def authorization(root):
    return dict(manifest_sha256=file_hash(root/'manifest.json'),scope='identity_extension_generation_and_audit',
                coordination_complete=True,authorized_by='test fixture only',endpoints=['http://127.0.0.1:9999/v1'],concurrency_per_endpoint=1)


def enabled(root):
    q=m.Queue(root);q.activate(authorization(root));return q


def render(messages):
    return {'rendered_tokens':50,'max_rendered_length':50}


def audit(keep=True):
    return dict(keep=keep,reason='fixture',language_quality=5,coherence=5,usefulness=5)


def test_exact_language_set_variants_and_facts():
    assert len(m.LANGUAGES)==21
    r=m.recipe()
    assert 'current_runtime' in r['grounding']
    assert 'checkpoint_continuation' in r['grounding']
    serialized=json.dumps(r)
    assert 'heldout' not in serialized
    assert 'Peter Schneider-Kamp' in serialized
    for lang in m.LANGUAGES:
        p=m.request(lang,100000,r)
        spec=json.loads(p['request']['messages'][1]['content'])
        assert spec['language_code']==lang and spec['user_turns']==1
    assert 'Portugal' in m.LANGUAGES['pt_pt']
    assert m.LANGUAGES['nb']!=m.LANGUAGES['nn']
    assert m.request('da',100000,r)!=m.request('en',100000,r)


def test_blocked_until_explicit_pinned_coordination(root):
    q=m.Queue(root)
    assert q.claim('worker') is None
    bad=authorization(root);bad['coordination_complete']=False
    with pytest.raises(ValueError,match='coordination'):q.activate(bad)
    assert not q.status()['activated']
    q.activate(authorization(root));q.activate(authorization(root))
    assert q.claim('worker')['stage']=='generate'
    q.close()


def test_two_brokers_no_quota_overshoot_and_audit_priority(root):
    q=enabled(root);other=m.Queue(root)
    job=q.claim('one');assert other.claim('two') is None
    assert q.submit(job['id'],'one','generate',{'messages':messages()},render)=='audit_pending'
    work=other.claim('two');assert work['stage']=='audit'
    assert q.claim('one') is None
    assert other.submit(work['id'],'two','audit',audit(),None)=='accepted'
    assert other.submit(work['id'],'two','audit',audit(),None)=='accepted'
    assert q.claim('one') is None
    group=q.db.execute("SELECT * FROM targets WHERE language='da'").fetchone()
    assert (group['accepted_new'],group['attempts'],group['active'])==(1,1,0)
    q.close();other.close()


def test_rejection_replenishes_new_id_not_failed_row(root):
    q=enabled(root);first=q.claim('one')
    q.submit(first['id'],'one','generate',{'messages':messages()},render)
    review=q.claim('two');q.submit(review['id'],'two','audit',audit(False),None)
    second=q.claim('one')
    assert second['id']!=first['id']
    assert q.db.execute('SELECT state FROM jobs WHERE id=?',(first['id'],)).fetchone()[0]=='rejected'
    assert second['payload']['record']['provenance']['slot']==100001
    q.close()


@pytest.mark.parametrize('text',['Sealed question','SEALED QUESTION!!!'])
def test_heldout_hashes_fail_closed_and_survive_resume(root,text):
    q=enabled(root);job=q.claim('one')
    assert q.submit(job['id'],'one','generate',{'messages':messages(text)},render)=='invalid'
    q.close();q=m.Queue(root)
    assert q.db.execute('SELECT error FROM jobs WHERE id=?',(job['id'],)).fetchone()[0].startswith("ValueError('Heldout")
    assert q.claim('two')['id']!=job['id'];q.close()


def test_duplicate_preserved_original_and_same_question_sequence(root):
    q=enabled(root)
    q.db.execute('INSERT INTO prompts VALUES (?,?,?)',('da',m.prompt_hash(messages()),'prior'))
    job=q.claim('one')
    assert q.submit(job['id'],'one','generate',{'messages':messages()},render)=='duplicate'
    assert q.db.execute('SELECT owner FROM prompts').fetchone()[0]=='prior'
    q.close()


def test_attempt_budget_six_no_failed_replays(root):
    q=enabled(root);ids=[]
    for _ in range(6):
        job=q.claim('one');ids.append(job['id']);q.fail(job['id'],'one','fixture transport failure')
    assert len(set(ids))==6 and q.claim('one') is None
    assert q.status()['jobs']=={'failed':6}
    q.close()


def test_ownership_result_and_request_drift(root):
    q=enabled(root);job=q.claim('one')
    with pytest.raises(ValueError,match='owned'):q.fail(job['id'],'two','no')
    q.submit(job['id'],'one','generate',{'messages':messages()},render)
    review=q.claim('two');q.submit(review['id'],'two','audit',audit(),None)
    with pytest.raises(ValueError,match='overwrite'):q.submit(review['id'],'two','audit',audit(False),None)
    q.close()


def test_payload_tampering_cannot_claim(root):
    q=enabled(root);q.db.execute("UPDATE jobs SET payload='{}'")
    with pytest.raises(ValueError,match='request drift'):q.claim('one')
    assert q.status()['jobs']=={'queued':1}
    assert q.db.execute("SELECT active FROM targets WHERE language='da'").fetchone()[0]==0
    q.close()


def test_render_failure_never_audited(root):
    q=enabled(root);job=q.claim('one')
    def invalid(_):raise ValueError('too long')
    assert q.submit(job['id'],'one','generate',{'messages':messages()},invalid)=='invalid'
    assert q.db.execute('SELECT candidate FROM jobs WHERE id=?',(job['id'],)).fetchone()[0] is None
    q.close()


def test_bad_audit_cannot_credit(root):
    q=enabled(root);job=q.claim('one');q.submit(job['id'],'one','generate',{'messages':messages()},render)
    review=q.claim('two');bad=audit();bad['coherence']=2
    assert q.submit(review['id'],'two','audit',bad,None)=='invalid'
    assert q.db.execute("SELECT accepted_new FROM targets WHERE language='da'").fetchone()[0]==0
    q.close()


def test_manifest_pin_drift_blocks_activation(root):
    write_json(root/'recipe.json',{})
    with pytest.raises(ValueError,match='artifact drift'):m.Queue(root).activate(authorization(root))


def test_prepare_refuses_existing_root(root):
    with pytest.raises(FileExistsError):m.prepare(root)
