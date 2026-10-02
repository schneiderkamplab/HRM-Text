import json
import os
from unittest.mock import patch

from scripts import serve_dfm13_tp8_headroom as server


def test_startup_requires_budget_but_no_extra_reserve():
    assert server.startup_fits({'devices': [{'total_mib': 100000, 'free_mib': 4500}]})
    assert not server.startup_fits({'devices': [{'total_mib': 100000, 'free_mib': 4499}]})


def test_adopt_does_not_stop_for_low_memory(tmp_path):
    item = server.identity(os.getpid())
    item['session_id'] = item['pid']
    (tmp_path / 'ownership.json').write_text(json.dumps(dict(
        owned=[item], server_session=item['pid'], endpoint='http://fake',
        created_at=item['create_time'])))
    observed = []

    def sleep(_):
        observed.append(json.loads((tmp_path / 'status.json').read_text()))
        (tmp_path / 'stop.request').touch()

    with patch.object(server, 'identity', return_value=item), \
            patch.object(server, 'remember'), \
            patch.object(server, 'memory', return_value={'devices': [{'free_mib': 1}]}), \
            patch.object(server.urllib.request, 'urlopen', side_effect=OSError('fake')), \
            patch.object(server.time, 'sleep', side_effect=sleep), \
            patch.object(server.signal, 'signal'), \
            patch.object(server, 'cleanup', return_value={'survivors': []}) as cleanup:
        server.adopt(tmp_path)
    assert len(observed) == 1
    assert observed[0]['free_mib'] == [1]
    assert observed[0]['free_memory_guard'] is False
    assert json.loads((tmp_path / 'status.json').read_text())['reason'] == 'stop_requested'
    cleanup.assert_called_once()
