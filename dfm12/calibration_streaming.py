"""Fail-closed streaming guards; never repair or accept truncated responses."""
import base64
import copy
import json
import time


class LoopGuard:
    def __init__(self):
        self.quoted = self.escaped = False
        self.whitespace = 0
        self.tail = ''

    def feed(self, text):
        for char in text:
            if self.quoted:
                if self.escaped:
                    self.escaped = False
                elif char == '\\':
                    self.escaped = True
                elif char == '"':
                    self.quoted = False
            elif char == '"':
                self.quoted = True
                self.whitespace = 0
            elif char.isspace():
                self.whitespace += 1
                if self.whitespace >= 128:
                    return 'structural_whitespace_loop'
            else:
                self.whitespace = 0
        self.tail = (self.tail + text)[-2048:]
        # At least eight identical blocks and 512 chars; not ordinary repetition.
        for size in range(64, 257):
            if len(self.tail) >= size * 8 and self.tail[-size:] * 8 == self.tail[-size * 8:]:
                return 'repeated_text_loop'
        return None


def loop_reason(text):
    return LoopGuard().feed(text)


async def stream_query(session, endpoint, payload, writer, metadata):
    from .multilingual_diagnose import MAX_RESPONSE_BYTES
    from .multilingual_calibration_v6 import HTTPFailure, strict_json
    request = copy.deepcopy(payload)
    request.update(stream=True, stream_options={'include_usage': True})
    rid = writer.begin(endpoint, request, metadata)
    body, pending, text = bytearray(), b'', ''
    status = finish = usage = error = first = None
    start = time.monotonic()
    guard = LoopGuard()
    try:
        async with session.post(endpoint.rstrip('/') + '/chat/completions', json=request) as response:
            status = response.status
            if status != 200:
                body.extend(await response.content.read(MAX_RESPONSE_BYTES))
                raise HTTPFailure(status)
            async for chunk in response.content.iter_any():
                remaining = MAX_RESPONSE_BYTES - len(body)
                body.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    raise ValueError('Raw HTTP byte budget exceeded')
                pending += chunk
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    line = line.strip()
                    if not line.startswith(b'data: ') or line == b'data: [DONE]':
                        continue
                    event = strict_json(line[6:].decode())
                    if event.get('error'):
                        raise ValueError('Stream server error: ' + str(event['error']))
                    for choice in event.get('choices', []):
                        delta = choice.get('delta', {}).get('content') or ''
                        if delta and first is None:
                            first = time.monotonic() - start
                        text += delta
                        reason = guard.feed(delta)
                        if reason:
                            raise ValueError(reason)
                        finish = choice.get('finish_reason') or finish
                    usage = event.get('usage') or usage
            if finish is None:
                raise ValueError('Incomplete stream without finish reason')
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        writer.finish(rid, status=status, raw_body_base64=base64.b64encode(body).decode(),
                      raw_body_utf8=body.decode('utf-8', errors='replace'),
                      transport_error=error, content=text, first_token_seconds=first,
                      elapsed_seconds=time.monotonic()-start)
    return dict(content=text, finish_reason=finish, usage=usage, raw_request_id=rid)
