#!/usr/bin/env python3
"""Exercise the real asynchronous C ABI; no Flutter or network service required."""
import argparse
import ctypes
import json
import os
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('library')
parser.add_argument('model')
parser.add_argument('profile')
parser.add_argument('device', nargs='?', default='auto')
parser.add_argument('--mixed-lm', action='store_true')
parser.add_argument('--report')
parser.add_argument('--compaction-stress', action='store_true')
args = parser.parse_args()
measurements = []
lib = ctypes.CDLL(args.library)
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
    started = time.monotonic()
    first_token = None
    deadline = started + 180
    while time.monotonic() < deadline:
        pointer = lib.mimir_poll(engine)
        if not pointer:
            time.sleep(.01)
            continue
        event = json.loads(ctypes.string_at(pointer))
        lib.mimir_free(pointer)
        if event['type'] == 'token' and first_token is None:
            first_token = time.monotonic() - started
        if event['type'] == 'done':
            result = next((e for e in events if e['type'] == 'reply'), {})
            if command['op'] == 'reply':
                measurements.append({'prompt': command['prompt'], 'historyMessages': len(command.get('history', [])),
                                     'firstTokenSeconds': first_token, 'totalSeconds': time.monotonic() - started,
                                     'reusedPrefixTokens': result.get('reusedPrefixTokens', 0),
                                     'text': result.get('text'), 'compactedPrompt': result.get('compactedPrompt'),
                                     'preparedTokens': next((e['tokens'] for e in events if e['type'] == 'prepared'), None),
                                     'summaryPasses': sum(e['type'] in ('summary', 'promptSummary') and e.get('text') == '' for e in events),
                                     'cancelled': result.get('cancelled', False)})
            return events
        events.append(event)
        if event['type'] == stop_on:
            lib.mimir_cancel(engine)
    raise TimeoutError(command['op'])

try:
    profile = json.load(open(args.profile))
    events = run({'op': 'devices'})
    assert events[0]['devices']
    events = run({'op': 'load', 'path': args.model, 'modelBytes': os.path.getsize(args.model),
                  'profile': profile, 'context': 1024, 'device': args.device, 'mixedLM': args.mixed_lm})
    assert events[0]['type'] == 'loaded', events
    reply = {'op': 'reply', 'history': [], 'prompt': 'Svar kort: Hvad er 2 + 2?', 'budget': 8}
    events = run(reply)
    assert not any(e['type'] == 'error' for e in events), events
    result = next(e for e in events if e['type'] == 'reply')
    assert result['text'] and not result['cancelled']
    assert ''.join(e['text'] for e in events if e['type'] == 'token') == result['text']
    assert result['reusedPrefixTokens'] == 0
    history = [{'role': 'user', 'content': reply['prompt']}, {'role': 'assistant', 'content': result['text']}]
    for prompt in ['Husk navnet Freja og byen Odense. Svar kort.', 'Hvad hedder personen, og hvilken by?']:
        run({'op': 'count', 'history': history})  # Counting must not flush reusable KV.
        followup = next(e for e in run(dict(reply, history=history, prompt=prompt, budget=24)) if e['type'] == 'reply')
        assert bool(followup['reusedPrefixTokens']) == args.mixed_lm, followup
        history += [{'role': 'user', 'content': prompt}, {'role': 'assistant', 'content': followup['text']}]
    edited = [dict(m) for m in history]
    edited[0]['content'] = 'Tidligere besked blev redigeret.'
    refreshed = next(e for e in run(dict(reply, history=edited)) if e['type'] == 'reply')
    assert refreshed['reusedPrefixTokens'] == 0
    fork = next(e for e in run(dict(reply, history=edited, conversation='different-chat')) if e['type'] == 'reply')
    assert fork['reusedPrefixTokens'] == 0
    invalid = run(dict(reply, history=[{'role': 'user', 'content': 'unfinished'}]))
    assert any(e['type'] == 'error' for e in invalid)
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
    assert result['reusedPrefixTokens'] == 0, 'Compaction must rebuild the effective prefix'
    full += [{'role': 'user', 'content': reply['prompt']}, {'role': 'assistant', 'content': result['text']}]
    after = next(e for e in run(dict(reply, history=full, memory=result['memory'])) if e['type'] == 'reply')
    assert bool(after['reusedPrefixTokens']) == args.mixed_lm, after
    if args.compaction_stress:
        oversized = ('Rejsen går til Odense. Freja ønsker vegetarisk frokost. Husk fredag klokken 14. æøå 😀\n' * 50 +
                     'Hvilken by skal Freja besøge? Svar kort på dansk.')
        events = run(dict(reply, prompt=oversized, budget=128))
        assert not any(e['type'] == 'error' for e in events), events
        compacted = next(e for e in events if e['type'] == 'reply')
        assert compacted['compactedPrompt'] and not compacted['cancelled'], compacted
        assert next(e for e in events if e['type'] == 'prepared')['tokens'] + 128 <= 1024
        assert len([e for e in events if e['type'] == 'promptSummary' and e['text'] == '']) > 1
        continuation = [{'role': 'user', 'content': oversized, 'compactedContent': compacted['compactedPrompt']},
                        {'role': 'assistant', 'content': compacted['text']}]
        counted = run({'op': 'count', 'history': continuation})
        assert counted[0]['tokens'] < 1024, counted
        assert run({'op': 'count', 'history': continuation, 'compact': False})[0]['tokens'] > 1024
        continued = run(dict(reply, history=continuation))
        assert not any(e['type'] in ('error', 'promptSummary') for e in continued), continued
        disabled = run(dict(reply, prompt=oversized, compact=False))
        assert any(e['type'] == 'error' for e in disabled)
        assert not any(e['type'] == 'compacting' for e in disabled)
        old = [{'role': 'user', 'content': oversized}, {'role': 'assistant', 'content': 'Odense.'}]
        old_events = run(dict(reply, history=old))
        assert not any(e['type'] == 'error' for e in old_events), old_events
        old_reply = next(e for e in old_events if e['type'] == 'reply')
        assert old_reply['memory']['covered'] == 2
        assert next(e for e in old_events if e['type'] == 'prepared')['tokens'] + 8 <= 1024
        stopped = run(dict(reply, prompt=oversized), 'promptSummary')
        stopped_reply = next(e for e in stopped if e['type'] == 'reply')
        assert stopped_reply['cancelled'] and stopped_reply['compactedPrompt'] is None
        assert next(e for e in run(reply) if e['type'] == 'reply')['text']
        print('PASS: oversized prompt, reusable prompt metadata, oversized old turn, disabled mode, cancellation/recovery')
    print('PASS: devices, load, template generation, streaming, cancellation/recovery, streamed compaction, cache lifecycle')
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

if args.report:
    with open(args.report, 'w') as out:
        json.dump({'mixedLM': args.mixed_lm, 'device': args.device, 'turns': measurements}, out, indent=2, ensure_ascii=False)
        out.write('\n')
