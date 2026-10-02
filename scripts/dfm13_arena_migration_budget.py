"""One explicit infrastructure interruption allowance; finished failures still count."""
import asyncio


def retry_numbers(prior, maximum, exemptions, seq, stage):
    ignored = 0
    for n, status, request_hash, _ in prior:
        key = (seq, stage, n, request_hash)
        if status == 'inflight':
            raise ValueError('Unarchived inflight attempt')
        if status == 'interrupted_unknown':
            if key not in exemptions:
                raise ValueError('Unapproved infrastructure interruption')
            ignored += 1
    if ignored > 1:
        raise ValueError('One migration allowance per stage only')
    start = max((r[0] for r in prior), default=0) + 1
    return range(start, start + max(0, maximum - (len(prior) - ignored)))


def take(queues, preferred):
    """Single event-loop atomic claim, without await between inspect and get."""
    choices = [preferred] + sorted((i for i in range(len(queues)) if i != preferred),
                                   key=lambda i: queues[i].qsize(), reverse=True)
    for i in choices:
        try:
            return i, queues[i].get_nowait()
        except asyncio.QueueEmpty:
            pass
    return None
