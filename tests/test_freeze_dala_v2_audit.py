import hashlib
from scripts.freeze_dala_v2_audit import LANGUAGES, pin


def test_exact_requested_scope():
    assert len(LANGUAGES) == len(set(LANGUAGES)) == 26
    assert 'pt-PT' in LANGUAGES
    assert not {'nl', 'fa', 'da', 'sq', 'sr'} & set(LANGUAGES)


def test_pin_reads_without_modification(tmp_path):
    path = tmp_path/'source'
    path.write_bytes(b'original source\n')
    before = path.stat().st_mtime_ns
    result = pin(path)
    assert result['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result['mtime_ns'] == before == path.stat().st_mtime_ns
    assert result['bytes'] == len(path.read_bytes())
