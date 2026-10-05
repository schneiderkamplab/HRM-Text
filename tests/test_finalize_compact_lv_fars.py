from copy import deepcopy
import json

import pytest

from dfm12.io import digest, write_json
from scripts import finalize_compact_lv_fars as final


@pytest.mark.parametrize('verdict', ['repair', 'reject', 'needs_verification'])
def test_nonkeeps_never_selected(verdict):
    row = dict(raw=dict(finish_reason='stop', content=json.dumps(dict(verdict=verdict, issues=['incorrect'], reason='Named defect.'))))
    assert not final.keep(row)


def test_keep_requires_complete_noncontradictory_raw():
    row = dict(raw=dict(finish_reason='stop', content='{"verdict":"keep","issues":[],"reason":"Supported."}'))
    assert final.keep(row)
    row['raw']['finish_reason'] = 'length'
    assert not final.keep(row)


def test_pending_repair_cannot_fallback(tmp_path):
    original = dict(status='valid', decision=dict(verdict='repair'))
    kind, path = final.chosen('id', original, repairs=tmp_path)
    assert kind == 'repair' and path is None
    write_json(tmp_path / 'outcomes/id.json', dict(status='unresolved'))
    assert final.chosen('id', original, repairs=tmp_path)[1] == tmp_path / 'outcomes/id.json'


def test_repair_exact_user_source_and_audit_binding():
    record = dict(messages=[dict(role='user', content='Original source.'), dict(role='assistant', content='Bad.')], source=dict(text='Original source.'))
    fixed = deepcopy(record); fixed['messages'][1]['content'] = 'Supported.'
    row = dict(status='reaudited', parent_request_sha256='r', parent_outcome_sha256='o',
               repair_raw=dict(finish_reason='stop', content='{"1":"Supported."}'))
    bundle = dict(record=fixed, original_record_sha256=digest(record), parent_request_sha256='r')
    request = dict(repaired_record_sha256=digest(fixed), request=dict(messages=[{}, dict(content=json.dumps(fixed))]))
    assert final.validate_repair(record, row, bundle, request, 'r', 'o') == fixed
    bundle['record']['messages'][0]['content'] = 'Silently changed source.'
    with pytest.raises(ValueError, match='binding'):
        final.validate_repair(record, row, bundle, request, 'r', 'o')


def test_retry_supersedes_original_even_when_missing(tmp_path):
    kind, path = final.chosen('id', dict(status='invalid'), invalid=tmp_path)
    assert kind == 'retry' and path is None
