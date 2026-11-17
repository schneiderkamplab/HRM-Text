import pytest
import asyncio
import httpx
import time

from scripts.run_dfm16_odin_judge import RateLimitedClient, OdinProse


def test_single_verdict_period_without_explanation():
    body = {'choices': [{'finish_reason': 'stop', 'message': {'content': 'Yes.'}}]}
    assert OdinProse.parse_review(body)['decision'] == 'accept'
    assert body['choices'][0]['message']['content'] == 'Yes.'
    body['choices'][0]['message']['content'] = 'Yes. However, no.'
    with pytest.raises(ValueError):
        OdinProse.parse_review(body)


def test_no_private_metadata_or_vendor_options(tmp_path):
    adapter = OdinProse(tmp_path, tmp_path/'out', 'https://api.odincore.ai/v1')
    payload = adapter.prepare(dict(prompt='Text question', expected='reject'))
    assert payload['messages'] == [{'role': 'user', 'content': 'Text question'}]
    assert payload['max_tokens'] == 8
    assert 'chat_template_kwargs' not in payload


def test_fixed_concurrency_and_actual_dispatch_rate():
    async def check():
        starts = []
        active = peak = 0
        async def handle(request):
            nonlocal active, peak
            starts.append(time.monotonic())
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(.005)
            active -= 1
            return httpx.Response(200, json={})
        async with RateLimitedClient(2, 3, .05, transport=httpx.MockTransport(handle)) as client:
            await asyncio.gather(client.get('https://example.test/models'),
                *(client.post('https://example.test') for _ in range(8)))
            assert client.requests == 9 and peak <= 2
            assert client.capacity == 2
            assert all(starts[i+3]-starts[i] >= .049 for i in range(6))
    asyncio.run(check())


def test_429_cools_down_without_changing_concurrency():
    async def check():
        async with RateLimitedClient(64, 180, .01, transport=httpx.MockTransport(
                lambda request: httpx.Response(429, headers={'Retry-After': '.02'}))) as client:
            await client.post('https://example.test')
            assert client.capacity == 64
            assert client.cooldown_until > time.monotonic()
    asyncio.run(check())
