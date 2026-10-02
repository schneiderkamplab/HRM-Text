import asyncio
import json
from types import SimpleNamespace

import pytest

from dfm12.calibration_streaming import LoopGuard, loop_reason, stream_query


def test_whitespace_guard_across_chunks():
    guard = LoopGuard()
    assert guard.feed('{"x": "hello"' + ' ' * 100) is None
    assert guard.feed(' ' * 28) == 'structural_whitespace_loop'


def test_quoted_whitespace_is_not_structural():
    assert loop_reason(json.dumps({'text': 'a' + ' ' * 150 + 'b'})) is None
    guard = LoopGuard()
    assert guard.feed('{"text":"a\\') is None
    assert guard.feed('"b"}') is None


def test_repetition_guard():
    phrase = 'This explanation repeats the same sentence without adding any information. '
    assert loop_reason(phrase * 8) == 'repeated_text_loop'
    assert loop_reason(phrase * 2) is None


@pytest.mark.parametrize('loop', [False, True])
def test_stream_records_raw_and_rejects_loops(loop):
    events = [dict(choices=[dict(delta={'content': '{"x":1}'}, finish_reason=None)])]
    if loop:
        events.append(dict(choices=[dict(delta={'content': ' ' * 128}, finish_reason=None)]))
    events.append(dict(choices=[dict(delta={}, finish_reason='stop')], usage={'completion_tokens': 4}))
    data = ''.join('data: ' + json.dumps(x) + '\n\n' for x in events).encode()
    class Response:
        status = 200
        def __init__(self):
            self.content = self
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def iter_any(self):
            for i in range(0, len(data), 7):
                yield data[i:i+7]
    receipts = []
    writer = SimpleNamespace(begin=lambda *a: 'test', finish=lambda *a, **kw: receipts.append(kw))
    session = SimpleNamespace(post=lambda *a, **kw: Response())
    if loop:
        with pytest.raises(ValueError, match='structural_whitespace_loop'):
            asyncio.run(stream_query(session, 'http://test', {}, writer, {}))
    else:
        result = asyncio.run(stream_query(session, 'http://test', {}, writer, {}))
        assert result['content'] == '{"x":1}'
        assert result['finish_reason'] == 'stop'
    assert len(receipts) == 1
    assert receipts[0]['raw_body_base64']
