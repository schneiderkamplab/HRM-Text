import pytest

from dfm12.european_expansion import NEW, configuration
from dfm12.opus import pairs
from dfm12 import catalog
from dfm12.records import convert, language
from dfm12.transform import PROMPTS, transform
from dfm12.trustllm import validate_generation


def test_pair_mesh_and_legacy():
    cfg = configuration()
    assert len(NEW) == 12
    assert len(cfg['languages']) == 21
    assert len(pairs(cfg)) == 174
    assert len(pairs(catalog.config())) == 33
    assert ('en', 'pt_pt') in pairs(cfg)
    assert ('ca', 'fo') in pairs(cfg)
    assert ('da', 'nl') not in pairs(cfg)
    assert set(NEW) <= PROMPTS.keys()


@pytest.mark.parametrize('lang', NEW)
@pytest.mark.parametrize('task', ['denoising', 'prefix-continuation', 'span-filling', 'paragraph-reordering'])
def test_transform_languages(lang, task):
    text = '\n\n'.join(f'{i}: ' + 'Example text with sufficiently many distinct words. ' * 20 for i in range(3))
    result = transform(text, lang, task, {'test': True})
    assert result['language'] == lang
    assert result['audit_context']['original'] == text
    assert PROMPTS[lang][0] in result['messages'][0]['content']


def test_aya_adapter_and_portuguese_fail_closed():
    source = dict(configuration()['sources']['aya-human-train'], revision='test')
    result = convert(dict(language_code='deu', inputs='Frage', targets='Antwort'), source, 'train.parquet', 0)
    assert result['language'] == 'de'
    with pytest.raises(ValueError):
        language(dict(language='pt'), dict(language='pt_pt'))


def test_sharegpt_and_tools_not_silently_dropped():
    source = dict(repo='test', revision='test', language='de', kind='instruction')
    row = dict(conversations=[dict(role='user', content='Hi'), dict(role='assistant', content='Hallo')])
    assert convert(row, source, 'train', 0)['messages'] == row['conversations']
    row['conversations'][1]['tool_calls'] = [{'id': 'call'}]
    with pytest.raises(ValueError, match='requires_native_tool_converter'):
        convert(row, source, 'train', 0)


def test_custom_system_context_preserved():
    source = dict(repo='test', revision='test', language='en', kind='instruction')
    row = dict(messages=[dict(role='user', content='Hi'), dict(role='assistant', content='Hello')],
               chat_template_kwargs=dict(custom_instructions='Use short answers.', enable_thinking=False, python_tools=[]))
    assert convert(row, source, 'train', 0)['messages'][0] == dict(role='system', content='Use short answers.')
    row['chat_template_kwargs']['python_tools'] = ['calculator']
    with pytest.raises(ValueError, match='unsupported_template_metadata'):
        convert(row, source, 'train', 0)


def test_trust_native_prompt_unchanged():
    record = dict(audit_context=dict(synthetic_prompt=False, seed_prompt='Hej?'))
    result = dict(messages=[dict(role='user', content='Hi?'), dict(role='assistant', content='Hello')])
    with pytest.raises(ValueError, match='Native prompt changed'):
        validate_generation(record, result)
    result['messages'][0]['content'] = 'Hej?'
    assert validate_generation(record, result) == result['messages']


def test_portuguese_document_filters():
    from dfm12.european_texts import corege_allowed
    row = {'pt.auto': 'true', 'pt.pt.auto': 'true', 'pt.mean.confidence.auto': '.95',
           'pt.pt.mean.confidence.auto': '.9', 'dc.rights.uri': 'https://creativecommons.org/licenses/by-nc-sa/4.0/'}
    assert corege_allowed(row)
    for field, value in [('pt.pt.auto', 'false'), ('pt.pt.mean.confidence.auto', 'nan'),
                         ('dc.rights.uri', ''), ('dc.rights.uri', 'https://creativecommons.org/licenses/by-nd/4.0/')]:
        assert not corege_allowed(dict(row, **{field: value}))


def test_trust_transfer_uses_export_queue(tmp_path):
    from dfm12.jobs import Queue
    from dfm12.trustllm import transfer_to_audit
    class Renderer:
        def count(self, messages):
            return 5
    queue = Queue(tmp_path / 'trustllm.sqlite')
    record = dict(component='trustllm-da', audit_context=dict(synthetic_prompt=False, seed_prompt='Hej?'))
    payload = dict(record=record)
    queue.add('generate', payload)
    job = queue.claim('generate', 'worker')
    queue.finish(job[0], 'worker', 1, result=dict(messages=[dict(role='user', content='Hej?'), dict(role='assistant', content='Hej!')]))
    queue.close()
    assert transfer_to_audit(tmp_path, Renderer(), 'model')['audit_queued'] == 1
    assert transfer_to_audit(tmp_path, Renderer(), 'model')['audit_queued'] == 1
    queue = Queue(tmp_path / 'jobs.sqlite')
    assert queue.status() == [dict(stage='audit', status='pending', count=1)]
    queue.close()
