import asyncio
import json
from types import SimpleNamespace

import pytest

from scripts import dfm13_repochat_calibration_v2 as m
from scripts import dfm13_repochat_calibration_v3 as v3


@pytest.fixture(autouse=True, params=[m, v3])
def version(request, monkeypatch):
    import sys
    monkeypatch.setattr(sys.modules[__name__], 'm', request.param)


@pytest.fixture
def tools(tmp_path):
    text = '\n'.join(f'line {i}' for i in range(1, 351))
    (tmp_path / 'a.txt').write_text(text)
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'b').write_text('example')
    return m.RepositoryTools(tmp_path, {'files': {'a.txt': m.base.sha(text.encode()),
                                                 'src/b': m.base.sha(b'example')}})


def test_read_count_and_cursor(tools):
    result = tools.execute('read_file', {'path': 'a.txt', 'start_line': 121, 'line_count': 120})
    assert len(result['lines']) == 120
    assert result['lines'][0] == '121: line 121'
    assert result['lines'][-1] == '240: line 240'
    assert result['next_start_line'] == 241
    result = tools.execute('read_file', {'path': 'a.txt', 'start_line': 341, 'line_count': 120})
    assert result['next_start_line'] is None


@pytest.mark.parametrize('count', [0, 121, -1, '120', True])
def test_read_invalid_count_explained(tools, count):
    result = tools.execute('read_file', {'path': 'a.txt', 'start_line': 1, 'line_count': count})
    assert result['error'] == 'invalid_arguments'
    assert 'line_count=1..120' in result['hint']


def test_old_end_line_explained(tools):
    assert tools.execute('read_file', {'path': 'a.txt', 'start_line': 121, 'end_line': 300})['error'] == 'invalid_arguments'


def test_navigation_and_loop(tools):
    result = tools.execute('list_files', {'prefix': '', 'after': ''})
    assert result['directories'] == ['src/']
    assert result['next_after'] is None
    args = {'prefix': 'missing/', 'after': ''}
    result = tools.execute('list_files', args)
    assert result['root_directories'] == ['src/']
    assert 'repeat_warning' in tools.execute('list_files', args)
    with pytest.raises(ValueError, match='repeated_identical'):
        tools.execute('list_files', args)


def test_no_unknown_tools_or_traversal(tools):
    with pytest.raises(ValueError, match='unknown'):
        tools.execute('shell', {})
    with pytest.raises(ValueError, match='safe snapshot'):
        tools.execute('read_file', {'path': '../secret', 'start_line': 1, 'line_count': 1})


def valid_review():
    return {**dict.fromkeys(m.REVIEW_FIELDS, True), 'issues': [], 'explanation': 'Supported by retrieved lines.'}


def test_review_consistency():
    review = valid_review()
    assert m.validate_review(review)
    review['issues'] = ['Empty method does not implement insertion.']
    with pytest.raises(ValueError, match='inconsistent'):
        m.validate_review(review)
    review['complete'] = False
    assert not m.validate_review(review)
    review['issues'] = []
    with pytest.raises(ValueError, match='inconsistent'):
        m.validate_review(review)


@pytest.mark.parametrize('field', m.REVIEW_FIELDS)
def test_review_boolean_strict(field):
    review = valid_review()
    review[field] = 'true'
    with pytest.raises(ValueError, match='boolean'):
        m.validate_review(review)


def test_native_roundtrip_controls_resume(tmp_path, monkeypatch):
    from aiohttp import web
    monkeypatch.setattr(m, 'CONTROLS', ('known',))

    async def exercise():
        requests = []

        async def models(request):
            return web.json_response({'data': [{'id': 'test'}]})

        async def completion(request):
            payload = await request.json()
            requests.append(payload)
            if 'tools' not in payload:
                review = valid_review()
                if 'OLD_NEGATIVE' in payload['messages'][-1]['content']:
                    review.update(complete=False, issues=['Empty method.'])
                message = {'role': 'assistant', 'content': json.dumps(review)}
                finish = 'stop'
            elif payload['messages'][-1]['role'] == 'tool':
                assert payload['tool_choice'] == 'auto'
                message = {'role': 'assistant', 'content': 'Answer from a.txt:1.'}
                finish = 'stop'
            else:
                assert payload['tool_choice'] == ('auto' if m is v3 else 'required')
                assert 'OLD_NEGATIVE' not in json.dumps(payload)
                message = {'role': 'assistant', 'content': None, 'tool_calls': [
                    {'id': 'call1', 'type': 'function', 'function': {'name': 'read_file',
                    'arguments': json.dumps({'path': 'a.txt', 'start_line': 1, 'line_count': 120})}}]}
                finish = 'tool_calls'
            return web.json_response({'choices': [{'message': message, 'finish_reason': finish}]})

        app = web.Application()
        app.router.add_get('/v1/models', models)
        app.router.add_post('/v1/chat/completions', completion)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        try:
            baseline, root = tmp_path / 'old', tmp_path / 'new'
            source = baseline / 'repositories' / 'owner--repo'
            (source / 'files').mkdir(parents=True)
            (source / 'files' / 'a.txt').write_text('answer')
            m.base.save(source / 'snapshot.json', {'commit': 'a' * 40, 'files': {'a.txt': m.base.sha(b'answer')}})
            m.base.save(baseline / 'trajectories' / 'known' / 'trajectory.json', {'messages': [{'role': 'assistant', 'content': 'OLD_NEGATIVE'}]})
            selection = {'tasks': [{'id': 'case', 'repository': 'owner/repo', 'query': 'Find answer'}]}
            m.base.save(root / 'selection.json', selection)
            m.base.save(root / 'ready.json', {'baseline': str(baseline), 'pins': {}, 'selection_sha256': m.base.file_sha(root / 'selection.json')})
            args = SimpleNamespace(root=root, authorized=True, model='test', per_endpoint=1,
                                   max_turns=4, max_tokens=256,
                                   endpoints=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}/v1')
            await m.run(args)
            summary = m.base.load(root / 'summary.json')
            assert summary['quality_pass'] == 1 and summary['control_rejections'] == 1
            assert len(requests) == 4
            (root / 'trajectories' / 'case' / 'outcome.json').unlink()
            await m.run(args)
            assert len(requests) == 4
            assert m.base.load(root / 'summary.json')['quality_pass'] == 1
        finally:
            await runner.cleanup()
    asyncio.run(exercise())
