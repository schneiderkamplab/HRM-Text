import pytest
from scripts.assemble_finished_wave_packages import merge


def test_merge_preserves_publication_state():
    local = dict(name='local', output_sha256='abc', uploaded=False)
    assert merge(dict(inherits='dfm12', additions=[]), dict(additions=[local]))['additions'] == [local]


def test_identical_published_wins_without_duplicates():
    pub = dict(name='same', output_sha256='abc', uploaded=True, status='accepted_uploaded')
    local = dict(name='same', output_sha256='abc', uploaded=False)
    assert merge(dict(additions=[pub]), dict(additions=[local]))['additions'] == [pub]


def test_conflicting_version_fails():
    with pytest.raises(ValueError, match='Conflicting'):
        merge(dict(additions=[dict(name='same', output_sha256='old')]),
              dict(additions=[dict(name='same', output_sha256='new')]))
