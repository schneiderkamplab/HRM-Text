import json
import scripts.dfm16_glm_gpu_handoff as handoff
from scripts.dfm16_glm_gpu_handoff import gpu_free,odin_owner
from scripts.dfm16_dual_generation import assign
from scripts.dfm16_glm_staged_stories import payload,decode
from scripts.dfm16_glm_fullscale_adapter import parse_local_verdict,source_record
from scripts.dfm16_glm_live_audit import LiveAudit
import pytest


ODIN_CMDLINE=b'python\x00-m\x00scripts.dfm16_english_fullscale_generate\x00run\x00'


def test_free_requires_all_eight_and_no_process():
    assert gpu_free('\n'.join(['0']*8),'')
    assert not gpu_free('\n'.join(['0']*7),'')
    assert not gpu_free('\n'.join(['0']*8),'1234')
    assert not gpu_free('\n'.join(['0']*7+['175000']),'')


def test_assignment_preserves_started_and_completed(tmp_path):
    jobs=[dict(job_id=f'quality-{i:06}',rows=128) for i in range(66)]
    (tmp_path/'quality-000001').mkdir()
    (tmp_path/'quality-000002').mkdir()
    (tmp_path/'quality-000002/receipt.json').write_text('{}')
    plans,completed=assign(jobs,tmp_path)
    odin={r['job_id'] for r in plans['odin']};glm={r['job_id'] for r in plans['glm']}
    assert 'quality-000001' in odin
    assert 'quality-000003' in glm
    assert not odin&glm
    assert len(odin|glm|set(completed))==66


def test_glm_thinking_is_retained_but_final_content_is_parsed():
    body=dict(choices=[dict(finish_reason='stop',message=dict(content='accept',reasoning='provider reasoning'))],usage=dict(completion_tokens=900))
    assert parse_local_verdict(body)=={'decision':'accept'}
    assert body['choices'][0]['message']['reasoning']=='provider reasoning'
    body['choices'][0]['finish_reason']='length'
    with pytest.raises(ValueError):decode(body)


def test_glm_requests_low_effort_without_fake_disable():
    p=payload('zai-org/GLM-5.3-Flash',[dict(role='user',content='Write a story.')])
    assert p['chat_template_kwargs']=={'reasoning_effort':'low'}
    assert p['max_tokens']==6144
    row=dict(text='Jo found a hat.',task='summary')
    assert source_record(row,{})['source']['reviewer']=='glm-source-and-request-audit'


def test_live_auditor_has_durable_auxiliary_methods():
    assert callable(LiveAudit.begin) and callable(LiveAudit.finish_stage)


def test_owner_absent_when_pid_file_missing(tmp_path):
    assert odin_owner(tmp_path/'generation.pid')==dict(state='absent',pid=None)


def test_owner_absent_when_pid_dead(tmp_path):
    (tmp_path/'generation.pid').write_text('2147480000')
    assert odin_owner(tmp_path/'generation.pid')['state']=='absent'


def test_owner_unexpected_cmdline_fails_closed(tmp_path,monkeypatch):
    pid_path=tmp_path/'generation.pid';pid_path.write_text('123')
    monkeypatch.setattr(handoff,'identity',lambda pid:'1')
    monkeypatch.setattr(handoff,'owner_command',lambda pid:b'bash\x00-c\x00')
    with pytest.raises(RuntimeError):odin_owner(pid_path)


def test_owner_without_credential_fails_closed(tmp_path,monkeypatch):
    pid_path=tmp_path/'generation.pid';pid_path.write_text('123')
    monkeypatch.setattr(handoff,'identity',lambda pid:'1')
    monkeypatch.setattr(handoff,'owner_command',lambda pid:ODIN_CMDLINE)
    monkeypatch.setattr(handoff,'owner_environ',lambda pid:[])
    with pytest.raises(RuntimeError):odin_owner(pid_path)


def test_owner_present_uses_owner_credential(tmp_path,monkeypatch):
    pid_path=tmp_path/'generation.pid';pid_path.write_text('123')
    monkeypatch.setattr(handoff,'identity',lambda pid:'1' if pid==123 else None)
    monkeypatch.setattr(handoff,'owner_command',lambda pid:ODIN_CMDLINE)
    monkeypatch.setattr(handoff,'owner_environ',lambda pid:[b'PATH=/bin',b'ODIN_API_KEY=secret'])
    owner=odin_owner(pid_path)
    assert owner==dict(state='present',pid=123,identity='1',credential='secret')
