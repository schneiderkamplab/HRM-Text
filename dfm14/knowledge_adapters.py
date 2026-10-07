"""Strict adapters for explicitly delimited knowledge-pilot source records."""
import re


def swallow(row):
    text = row.get('text')
    if not isinstance(text, str):
        raise ValueError('missing_swallow_text')
    markers = list(re.finditer(r'^\*\*(Question|Answer) (\d+)\*\*:\s*', text, re.M))
    if not markers or text[:markers[0].start()].strip() or len(markers) % 2:
        raise ValueError('ambiguous_swallow_qa')
    messages = []
    seen = set()
    for i in range(0, len(markers), 2):
        q, a = markers[i:i+2]
        if q[1] != 'Question' or a[1] != 'Answer' or q[2] != a[2] or q[2] in seen:
            raise ValueError('ambiguous_swallow_numbering')
        seen.add(q[2])
        end = markers[i+2].start() if i+2 < len(markers) else len(text)
        question, answer = text[q.end():a.start()].strip(), text[a.end():end].strip()
        if not question or not answer or question.count('```') % 2 or answer.count('```') % 2:
            raise ValueError('incomplete_swallow_qa')
        messages += [dict(role='user', content=question), dict(role='assistant', content=answer)]
    return messages
