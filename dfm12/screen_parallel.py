"""Bounded ordered CPU preparation; workers never open screening/queue databases."""
from collections import deque
import json

from .audit_gates import legacy_tool_reasons
from .io import digest
from .jobs import audit_payload
from .records import chat_fingerprint, validate_messages
from .scandi_overlap import normalized, text_hash, views
from .screening_application import text_fields


def batches(path, max_rows=64, max_bytes=1024 * 1024):
    batch, size = [], 0
    with open(path, 'rb') as handle:
        for line in handle:
            if not line.strip():
                continue
            if batch and (len(batch) >= max_rows or size + len(line) > max_bytes):
                yield batch
                batch, size = [], 0
            batch.append(line)
            size += len(line)
        if batch:
            yield batch


def ordered(pool, function, arguments, max_pending):
    """Backpressure includes completed out-of-order results, not just running jobs."""
    if max_pending < 1:
        raise ValueError('max_pending must be positive')
    iterator = iter(arguments)
    pending = deque()
    try:
        for _ in range(max_pending):
            try:
                pending.append(pool.submit(function, next(iterator)))
            except StopIteration:
                break
        while pending:
            yield pending.popleft().result()
            try:
                pending.append(pool.submit(function, next(iterator)))
            except StopIteration:
                pass
    finally:
        for future in pending:
            future.cancel()


def prepare_screen_row(row):
    found = list(legacy_tool_reasons(row))
    chats = views(row, 'new')
    if not chats:
        return dict(line=json.dumps(row, ensure_ascii=False), id=row.get('id'),
                    tokens=row.get('rendered_tokens', 0), chats=[], texts=[],
                    reasons=['unsupported_chat_schema'])
    keys = []
    for _, messages in chats:
        validate_messages(messages)
        keys.append(chat_fingerprint(messages))
    texts = [text_hash(text) for _, text in text_fields(row) if len(normalized(text)) >= 160]
    return dict(line=json.dumps(row, ensure_ascii=False), id=row.get('id'),
                tokens=row.get('rendered_tokens', 0), chats=keys, texts=texts, reasons=found)


def screen_batch(lines):
    return [prepare_screen_row(json.loads(line)) for line in lines]


def queue_batch(args):
    lines, component, model = args
    result = []
    for line in lines:
        row = json.loads(line)
        row['component'] = component
        payload = audit_payload(row, model)
        result.append((digest(['audit', payload]), 'audit', json.dumps(payload, ensure_ascii=False)))
    return result
