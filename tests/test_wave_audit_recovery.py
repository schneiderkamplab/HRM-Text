import json

from dfm12.jobs import Queue, audit_payload
from dfm12.wave_repair import MODEL
from scripts.recover_wave_audits import recover


def test_recovery_is_idempotent_and_preserves_failed_source(tmp_path):
    source = Queue(tmp_path / 'audit/jobs.sqlite')
    row = dict(id='example', language='lt', messages=[
        dict(role='user', content='Question'), dict(role='assistant', content='Answer')])
    key = source.add('audit', audit_payload(row, MODEL))
    source.db.execute("UPDATE jobs SET status='failed',attempts=4,error='timeout' WHERE id=?", (key,))
    recover(tmp_path)
    report = json.loads((tmp_path / 'repair/source-audit-retries.json').read_text())
    assert report == dict(failed_source_jobs=1, newly_queued=1, reused=0)
    recover(tmp_path)
    report = json.loads((tmp_path / 'repair/source-audit-retries.json').read_text())
    assert report == dict(failed_source_jobs=1, newly_queued=0, reused=1)
    assert source.db.execute('SELECT status,attempts,error FROM jobs').fetchone() == ('failed', 4, 'timeout')
    retry = Queue(tmp_path / 'repair/jobs.sqlite')
    assert retry.db.execute('SELECT count(*) FROM jobs').fetchone()[0] == 1
    payload = json.loads(retry.db.execute('SELECT payload FROM jobs').fetchone()[0])
    assert payload['record'] == row
    assert payload['request']['response_format']['type'] == 'json_schema'
    source.close();retry.close()
