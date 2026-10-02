import io
import json
import tarfile

import pytest

from scripts import dfm13_repochat_calibration as m


def row(query='Explain the implementation', repo='https://github.com/owner/repo'):
    return {'winner': 'model_a', 'github_link': repo,
            'full_conversation_a': [{'role': 'user', 'content': 'OLD SOURCE [USER QUERY]\n' + query},
                                    {'role': 'assistant', 'content': 'OLD ANSWER'}]}


def test_selection_dedup_and_no_old_answer():
    rows, report = m.select([row(), row(), row('[Redacted Name] query')], 1)
    assert len(rows) == 1 and report['eligible'] == 1
    assert 'OLD' not in json.dumps(rows)
    assert rows == m.select([row(), row()], 1)[0]


def test_unsafe_eligibility():
    assert m.excluded_query('sexual content involving a child')
    with pytest.raises(ValueError, match='only 0'):
        m.select([row('sexual content involving a child')], 1)


@pytest.mark.parametrize('url', ['http://github.com/a/b', 'https://github.com/a/b/tree/main',
                                'https://github.com@localhost/a/b', 'https://github.com/../b'])
def test_repo_url(url):
    with pytest.raises(ValueError):
        m.repository(url)


@pytest.mark.parametrize('path', ['../x', '/etc/passwd', 'root/../../x', 'root\\evil'])
def test_paths(path):
    with pytest.raises(ValueError):
        m.safe_path(path)


def archive(path, entries):
    with tarfile.open(path, 'w:gz') as tf:
        for name, data, kind in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.size = len(data) if kind == tarfile.REGTYPE else 0
            member.linkname = '/etc/passwd' if kind == tarfile.SYMTYPE else ''
            tf.addfile(member, io.BytesIO(data) if member.isfile() else None)


def test_extract_tools_no_links_or_secrets(tmp_path):
    tar = tmp_path / 'a.tar.gz'
    archive(tar, [('repo/src/a.py', b'hello\nworld\n', tarfile.REGTYPE),
                  ('repo/link', b'', tarfile.SYMTYPE),
                  ('repo/.env', b'TOKEN=x', tarfile.REGTYPE),
                  ('repo/key.txt', b'-----BEGIN RSA PRIVATE KEY-----', tarfile.REGTYPE)])
    files = m.extract(tar, tmp_path / 'files')
    assert list(files) == ['src/a.py']
    tools = m.RepositoryTools(tmp_path / 'files', {'files': files})
    assert tools.execute('read_file', {'path': 'src/a.py', 'start_line': 1, 'end_line': 2})['lines'] == ['1: hello', '2: world']
    assert tools.execute('search_repository', {'query': 'world', 'prefix': ''})['matches'][0]['line'] == 2
    assert tools.execute('list_files', {'prefix': '', 'after': ''})['paths'] == ['src/a.py']
    with pytest.raises(ValueError):
        tools.read('../x')
    with pytest.raises(ValueError):
        tools.execute('exec', {'command': 'whoami'})
    with pytest.raises(ValueError):
        tools.execute('read_file', {'path': 'src/a.py', 'start_line': 1, 'end_line': 121})


def test_drift(tmp_path):
    (tmp_path / 'a').write_text('changed')
    tools = m.RepositoryTools(tmp_path, {'files': {'a': m.sha(b'original')}})
    with pytest.raises(ValueError, match='drift'):
        tools.read('a')


def test_archive_traversal(tmp_path):
    path = tmp_path / 'a.tar.gz'
    archive(path, [('root/../escape', b'bad', tarfile.REGTYPE)])
    with pytest.raises(ValueError):
        m.extract(path, tmp_path / 'out')


def test_atomic_save(tmp_path):
    path = tmp_path / 'out.json'
    m.save(path, {'status': 'complete'})
    assert m.load(path) == {'status': 'complete'}


def test_network_allowlist():
    with pytest.raises(ValueError):
        m.fetch('http://localhost:80/secrets', 100)


def test_complete_schemas():
    assert len(m.TOOLS) == 3
    for tool in m.TOOLS:
        schema = tool['function']['parameters']
        assert set(schema['properties']) == set(schema['required'])
        assert schema['additionalProperties'] is False


def test_native_roundtrip_review_and_receipt_resume(tmp_path):
    import asyncio
    from types import SimpleNamespace
    from aiohttp import web

    async def exercise():
        calls = []

        async def models(request):
            return web.json_response({'data': [{'id': 'test'}]})

        async def completion(request):
            body = await request.json()
            calls.append(body)
            assert body['chat_template_kwargs'] == {'enable_thinking': False}
            if 'tools' not in body:
                content = json.dumps(dict(correct=True, grounded=True, relevant=True, safe=True, explanation='Supported by file.'))
                message, finish = {'role': 'assistant', 'content': content}, 'stop'
            elif body['messages'][-1]['role'] == 'tool':
                assert body['messages'][-1]['tool_call_id'] == 'call-1'
                message, finish = {'role': 'assistant', 'content': 'The answer is in notes.txt:1.'}, 'stop'
            else:
                message, finish = {'role': 'assistant', 'content': None, 'tool_calls': [
                    {'id': 'call-1', 'type': 'function', 'function': {'name': 'read_file',
                    'arguments': json.dumps(dict(path='notes.txt', start_line=1, end_line=1))}}]}, 'tool_calls'
            return web.json_response({'choices': [{'message': message, 'finish_reason': finish}]})

        app = web.Application()
        app.router.add_get('/v1/models', models)
        app.router.add_post('/v1/chat/completions', completion)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            repo = tmp_path / 'repositories' / 'owner--repo'
            (repo / 'files').mkdir(parents=True)
            (repo / 'files' / 'notes.txt').write_text('answer')
            m.save(repo / 'snapshot.json', {'commit': 'a' * 40, 'files': {'notes.txt': m.sha(b'answer')}})
            m.save(tmp_path / 'selection.json', {'tasks': [{'id': 'case', 'repository': 'owner/repo', 'query': 'Find answer'}]})
            m.save(tmp_path / 'ready.json', {'implementation_sha256': m.file_sha(m.__file__),
                'selection_sha256': m.file_sha(tmp_path / 'selection.json'),
                'snapshots': {'owner/repo': m.file_sha(repo / 'snapshot.json')}})
            args = SimpleNamespace(authorized=True, root=tmp_path, endpoints=f'http://127.0.0.1:{port}/v1',
                                   model='test', concurrency=1, max_turns=4, max_tokens=512)
            await m.run(args)
            outcome = tmp_path / 'trajectories' / 'case' / 'outcome.json'
            assert m.load(outcome)['quality_pass'] is True
            assert m.load(outcome)['admission'] is False
            assert len(calls) == 3
            outcome.unlink()
            await m.run(args)
            assert len(calls) == 3  # Resume uses bound raw receipts, not another model sample.
            assert m.load(outcome)['status'] == 'reviewed'
        finally:
            await runner.cleanup()

    asyncio.run(exercise())
