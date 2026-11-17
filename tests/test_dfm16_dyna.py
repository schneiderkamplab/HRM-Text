import pytest

from scripts.prepare_dfm16_dyna import instruction


def row():
    return dict(id='source-1', prompt='Hva er dette?', target='Dette er et svar.',
                meta={'source_id': 'doc-1'}, sources=[{'dataset': 'source'}])


def test_conversion_preserves_target_and_lineage():
    original = row()
    converted = instruction(original, 'revision', 3)
    assert converted['messages'] == [
        {'role': 'user', 'content': original['prompt']},
        {'role': 'assistant', 'content': original['target']}]
    assert converted['provenance']['source_meta'] == original['meta']
    assert converted['provenance']['revision'] == 'revision'
    assert converted['provenance']['row'] == 3
    assert converted['language'] == 'no'  # Do not relabel Nynorsk as Bokmal.


@pytest.mark.parametrize('field', ['prompt', 'target'])
def test_empty_content_rejected(field):
    original = row()
    original[field] = ''
    with pytest.raises(ValueError):
        instruction(original, 'revision', 0)


def test_laya_access_never_selects_16k(monkeypatch):
    from pathlib import Path
    from scripts import prepare_dfm16_dyna as module
    files = []
    def fetch(pin, name):
        files.append(name)
        return Path(name)
    monkeypatch.setattr(module, 'fetch', fetch)
    result = module.laya_access({'repo': 'syvai/danish-dynaword-laya', 'revision': 'pin'})
    assert files == ['data/ctx1024/test.parquet', 'data/ctx1024/train.parquet']
    assert result['status'] == 'downloaded_schema_inspection_and_conversion_pending'


def test_laya_gating_is_explicit(monkeypatch):
    import httpx
    from huggingface_hub.errors import GatedRepoError
    from scripts import prepare_dfm16_dyna as module
    def fetch(pin, name):
        raise GatedRepoError('403', response=httpx.Response(403,
            request=httpx.Request('GET', 'https://huggingface.co/example')))
    monkeypatch.setattr(module, 'fetch', fetch)
    result = module.laya_access({'repo': 'syvai/danish-dynaword-laya', 'revision': 'pin'})
    assert result['status'] == 'blocked_gated_403'
