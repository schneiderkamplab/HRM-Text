#!/usr/bin/env python3
"""Exercise the real asynchronous C ABI; no Flutter or network service required."""
import ctypes
import json
import sys
import time

lib = ctypes.CDLL(sys.argv[1])
lib.mimir_create.restype = ctypes.c_void_p
lib.mimir_submit.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.mimir_submit.restype = ctypes.c_int
lib.mimir_poll.argtypes = [ctypes.c_void_p]
lib.mimir_poll.restype = ctypes.c_void_p
lib.mimir_free.argtypes = [ctypes.c_void_p]
lib.mimir_cancel.argtypes = [ctypes.c_void_p]
lib.mimir_destroy.argtypes = [ctypes.c_void_p]
engine = lib.mimir_create()
assert engine

def run(command, stop_on=None):
    assert lib.mimir_submit(engine, json.dumps(command).encode()) == 1
    events = []
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        pointer = lib.mimir_poll(engine)
        if not pointer:
            time.sleep(.01)
            continue
        event = json.loads(ctypes.string_at(pointer))
        lib.mimir_free(pointer)
        if event['type'] == 'done':
            return events
        events.append(event)
        if event['type'] == stop_on:
            lib.mimir_cancel(engine)
    raise TimeoutError(command['op'])

try:
    profile = json.load(open(sys.argv[3]))
    events = run({'op': 'devices'})
    assert events[0]['devices']
    import os
    events = run({'op': 'load', 'path': sys.argv[2], 'modelBytes': os.path.getsize(sys.argv[2]),
                  'profile': profile, 'context': 1024, 'device': sys.argv[4] if len(sys.argv) > 4 else 'auto'})
    assert events[0]['type'] == 'loaded', events
    reply = {'op': 'reply', 'history': [], 'prompt': 'Svar kort: Hvad er 2 + 2?', 'budget': 8}
    events = run(reply)
    assert not any(e['type'] == 'error' for e in events), events
    result = next(e for e in events if e['type'] == 'reply')
    assert result['text'] and not result['cancelled']
    assert ''.join(e['text'] for e in events if e['type'] == 'token') == result['text']
    cancelled = run(dict(reply, budget=64, prompt='Skriv en lang historie om Odense.'), 'token')
    assert next(e for e in cancelled if e['type'] == 'reply')['cancelled']
    assert next(e for e in run(reply) if e['type'] == 'reply')['text'] == result['text']
    full = []
    for i in range(30):
        full.extend([{'role': 'user', 'content': f'Tur {i}: Vi rejser med tog til Odense og ønsker vegetarisk frokost. Husk planen til weekenden.'},
                     {'role': 'assistant', 'content': 'Tog til Odense og vegetarisk frokost. Jeg husker planen.'}])
    events = run(dict(reply, history=full))
    result = next(e for e in events if e['type'] == 'reply')
    assert result['memory']['covered'] > 0
    summaries = [e for e in events if e['type'] == 'summary']
    assert len(summaries) > 1 and summaries[-1]['text'] == result['memory']['summary']
    assert events.index(next(e for e in events if e['type'] == 'compacting')) < events.index(next(e for e in events if e['type'] == 'prepared'))
    print('PASS: devices, load, template generation, streaming, cancellation/recovery, streamed compaction')
    assert lib.mimir_submit(engine, json.dumps(dict(reply, budget=512, prompt='Skriv en lang historie om en rejse gennem Danmark.')).encode()) == 1
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        pointer = lib.mimir_poll(engine)
        if not pointer:
            time.sleep(.01)
            continue
        event = json.loads(ctypes.string_at(pointer))
        lib.mimir_free(pointer)
        if event['type'] == 'token':
            break
        assert event['type'] not in ('error', 'done'), event
    else:
        raise TimeoutError('First token before shutdown')
    started = time.monotonic()
    lib.mimir_destroy(engine)
    engine = None
    assert time.monotonic() - started < 30
    print('PASS: destruction during active generation cancels and joins')
finally:
    if engine:
        lib.mimir_destroy(engine)
print('PASS: shutdown and resource release')
