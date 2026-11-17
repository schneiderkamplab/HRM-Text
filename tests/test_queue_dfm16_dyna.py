from pathlib import Path

import pytest

from dfm12.io import file_hash, load, write_json
from scripts import queue_dfm16_dyna as queue


def test_atomic_exchange_preserves_previous(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    a.mkdir(); b.mkdir()
    (a/'value').write_text('old')
    (b/'value').write_text('new')
    queue.exchange(a, b)
    assert (a/'value').read_text() == 'new'
    assert (b/'value').read_text() == 'old'


def test_publish_and_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, 'REPO', tmp_path)
    target, replacement, work = tmp_path/'data/sampled_dfm16', tmp_path/'replacement', tmp_path/'work'
    write_json(target/'metadata.json', {'old': True})
    write_json(replacement/'metadata.json', {'tokenizer_info': {'chat_template_path': 'temporary'}})
    receipt = {'metadata_sha256': file_hash(replacement/'metadata.json')}
    write_json(replacement/'ready.json', receipt)
    write_json(replacement/'validated.json', receipt)
    queue.publish(work, replacement)
    assert load(target/'metadata.json')['dfm16_dyna_campaign'] == str(work)
    assert load(replacement/'metadata.json') == {'old': True}
    (work/'published.json').unlink()
    queue.publish(work, replacement)
    assert load(target/'metadata.json')['dfm16_dyna_campaign'] == str(work)
    assert load(replacement/'metadata.json') == {'old': True}


def test_publish_rejects_changed_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, 'REPO', tmp_path)
    target, replacement = tmp_path/'data/sampled_dfm16', tmp_path/'replacement'
    write_json(target/'metadata.json', {'old': True})
    write_json(replacement/'metadata.json', {'bad': True})
    for name in ('ready.json', 'validated.json'):
        write_json(replacement/name, {'metadata_sha256': 'incorrect'})
    with pytest.raises(ValueError, match='metadata hash'):
        queue.publish(tmp_path/'work', replacement)
    assert load(target/'metadata.json') == {'old': True}


def test_publication_on_filesystem_without_exchange(tmp_path, monkeypatch):
    import errno
    monkeypatch.setattr(queue, 'REPO', tmp_path)
    def unsupported(*args):
        raise OSError(errno.EINVAL, 'Unsupported')
    monkeypatch.setattr(queue, 'exchange', unsupported)
    target, replacement, work = tmp_path/'data/sampled_dfm16', tmp_path/'replacement', tmp_path/'work'
    write_json(target/'metadata.json', {'old': True})
    write_json(replacement/'metadata.json', {'tokenizer_info': {}})
    receipt = {'metadata_sha256': file_hash(replacement/'metadata.json')}
    for name in ('ready.json', 'validated.json'):
        write_json(replacement/name, receipt)
    queue.publish(work, replacement)
    backup = Path(load(work/'published.json')['previous'])
    assert load(backup/'metadata.json') == {'old': True}
    assert load(target/'metadata.json')['dfm16_dyna_campaign'] == str(work)
    # Emulate interruption just after the old directory was moved aside.
    target.rename(replacement)
    (work/'published.json').unlink()
    queue.publish(work, replacement)
    assert load(target/'metadata.json')['dfm16_dyna_campaign'] == str(work)
    assert load(backup/'metadata.json') == {'old': True}
