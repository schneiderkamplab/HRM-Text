import asyncio
import json

from scripts import audit_dfm13_jjzha as a


def test_prepare_imdb_sample_and_full_croco(tmp_path):
    converted=tmp_path/'converted'
    for name in ('jjzha_imdb_dutch','jjzha_croco'):
        folder=converted/name;folder.mkdir(parents=True)
        path=folder/'candidates.jsonl'
        rows=[dict(id=name+str(i),messages=[dict(role='user',content='Q'),dict(role='assistant',content='A')],target_message_index=1) for i in range(5)]
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        a.write_json(folder/'manifest.json',dict(output=str(path),output_sha256=a.sha(path)))
    root=tmp_path/'audit'
    result=a.prepare(root,converted,2)
    assert result['counts']=={'jjzha_croco':5,'jjzha_imdb_dutch':2}
    assert result['no_automatic_admission']
    db=a.database(root)
    for sid,name,offset,length,expected in db.execute('SELECT id,source,offset,length,row_hash FROM jobs'):
        with open(result['sources'][name]['path'],'rb') as f:
            f.seek(offset); raw=f.read(length)
        assert json.loads(raw)['id']==sid
        assert a.hashlib.sha256(raw).hexdigest()==expected
    db.close()


def test_reasonfirst_request_preserves_native_target_and_language_check():
    row=dict(messages=[dict(role='user',content='Q'),dict(role='assistant',content='A')],target_message_index=1)
    request=a.review_request(row,'jjzha_imdb_dutch','expected-model')
    assert request['model']=='expected-model'
    assert request['chat_template_kwargs']=={'enable_thinking':True}
    assert 'Dutch review fluency' in request['messages'][0]['content']
    assert list(request['response_format']['json_schema']['schema']['properties'])==['reason','verdict']


def test_unavailable_servers_do_not_start_work():
    class Session:
        def get(self,*args,**kwargs):
            raise ConnectionError('offline')
    assert asyncio.run(a.servers_ready(Session(),['http://127.0.0.1:1/v1'],'expected')) is False
