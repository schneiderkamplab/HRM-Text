"""Lossless revision review view: print unchanged paragraphs by reference."""
import argparse
from scripts.dfm16_validation_labels import evidence
from scripts.dfm16_staged_validation_campaign import ROOT


def compact(messages):
    previous = None
    result = []
    for message in messages:
        text = message['content']
        if message['role'] != 'assistant':
            result.append(dict(message))
            continue
        parts = text.split('\n\n')
        if previous is None or len(parts) != 3 or len(previous) != 3:
            result.append(dict(message))
        else:
            changes = {i: p for i, p in enumerate(parts) if p != previous[i]}
            rebuilt = '\n\n'.join(changes.get(i, p) for i, p in enumerate(previous))
            assert rebuilt == text
            result.append(dict(role='assistant', changes=changes,
                unchanged=[i for i in range(3) if i not in changes]))
        previous = parts
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, required=True)
    parser.add_argument('--end', type=int, required=True)
    args = parser.parse_args()
    _, items = evidence(ROOT, 'en')
    for private, packet in items:
        if not args.start <= private['index'] < args.end or packet['status'] != 'generated':
            continue
        if private['task'] != 'revision':
            raise ValueError('this view is for revision conversations')
        print('\n###', private['index'], 'first_contract', packet['first_attempt_contract_clear'])
        for message in compact(packet['messages']):
            if 'content' in message:
                print(message['role'] + ':', message['content'])
            else:
                print('assistant: unchanged from preceding answer, paragraphs',
                      [i + 1 for i in message['unchanged']])
                for i, paragraph in message['changes'].items():
                    print('replacement paragraph', i + 1, ':', paragraph)
