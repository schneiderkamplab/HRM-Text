"""Exercise the actual JSON-lines chat executable, including real SIGINT cancellation."""
import argparse
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading

__all__ = []


class _Client:
    def __init__(self, command, log):
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                                        text=True, encoding='utf-8', bufsize=1)
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()
        assert self.event() == {'event': 'ready'}

    def _read(self):
        try:
            for line in self.process.stdout:
                self.queue.put(json.loads(line))
        except Exception as error:
            self.queue.put(error)
        self.queue.put(None)

    def event(self):
        value = self.queue.get(timeout=120)
        if value is None or isinstance(value, Exception):
            raise RuntimeError(f'Client output failed: {value}')
        return value

    def send(self, request):
        self.process.stdin.write(json.dumps(request) + '\n')
        self.process.stdin.flush()

    def prepare(self, messages, expected_tokens):
        self.send({'op': 'prepare', 'messages': messages, 'add_generation_prompt': True})
        prompt = self.event()
        assert prompt['event'] == 'prompt' and prompt['tokens'] == expected_tokens, prompt

    def reset(self):
        self.send({'op': 'reset'})
        assert self.event() == {'event': 'reset'}

    def reply(self, text, limit=4, cancel=None):
        self.send({'text': text, 'max_tokens': limit})
        assert self.event() == {'event': 'start'}
        if cancel == 'prefill':
            os.kill(self.process.pid, signal.SIGINT)
        deltas = []
        while True:
            event = self.event()
            if event['event'] == 'delta':
                deltas.append(event['text'])
                if cancel == 'answer':
                    os.kill(self.process.pid, signal.SIGINT)
                    cancel = None
            else:
                assert event['event'] == 'done', event
                assert ''.join(deltas) == event['text'], 'Stream differs from final text'
                return event

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.thread.join(timeout=2)


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--short-reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--flash', action='store_true')
    parser.add_argument('--device', choices=['cpu', 'metal'], default='metal')
    args = parser.parse_args()
    command = [str(args.client), '--model', str(args.model), '--device', args.device, '--ctx', '256', '--batch', '224', '--json']
    if args.flash:
        command.append('--flash')
    checks = []
    passed = False
    error = None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.with_suffix('.log').open('w') as log:
        client = _Client(command, log)
        try:
            messages = []
            for index, case in enumerate(json.loads(args.reference.read_text())):
                messages.append({'role': 'user', 'content': case['text']})
                client.prepare(messages, case['prompt_tokens'])
                checks.append({'name': f'Mimir template token parity turn {index}', 'pass': True})
                got = client.reply(case['text'], 32)
                assert got['tokens'] == case['tokens'] and got['text'] == case['answer'], got
                assert got['finish'] == case['finish'] and got['stop_token'] == case['stop_token'], got
                assert got['history_size'] == 2 * (index + 1)
                messages.append({'role': 'assistant', 'content': got['text']})
                checks.append({'name': f'HF free-running conversation turn {index}', 'pass': True, 'result': got})
            for case in json.loads(args.short_reference.read_text())[:2]:
                client.reset()
                client.prepare(case['messages'], case['token_ids'])
                checks.append({'name': f"Mimir template token parity {case['id']}", 'pass': True})
                got = client.reply(case['messages'][0]['content'])
                assert got['tokens'] == case['reference_answer_ids'], got
                assert got['finish'] == 'length'
                checks.append({'name': f"HF greedy {case['id']}", 'pass': True, 'result': got})
            probe = json.loads(args.short_reference.read_text())[0]
            for mode in ['prefill', 'answer']:
                client.reset()
                got = client.reply(probe['messages'][0]['content'], 64, cancel=mode)
                assert got['finish'] == 'cancelled' and got['history_size'] == 0, got
                recovered = client.reply(probe['messages'][0]['content'])
                assert recovered['tokens'] == probe['reference_answer_ids']
                checks.append({'name': f'SIGINT {mode} rollback and recovery', 'pass': True})
            got = client.reply('x ' * 400, 1)
            assert got['finish'] == 'error' and got['status'] == 2 and got['history_size'] == 2, got
            checks.append({'name': 'capacity preserves history', 'pass': True})
            for request in [{'op': 'unknown'}, {'text': 'x', 'max_tokens': -1}, {'text': 'x', 'max_tokens': 0}]:
                client.send(request)
                assert client.event()['event'] == 'error'
            client.reset()
            assert client.reply(probe['messages'][0]['content'])['tokens'] == probe['reference_answer_ids']
            checks.append({'name': 'invalid input and reset recovery', 'pass': True})
            passed = True
        except Exception as failure:
            error = f'{type(failure).__name__}: {failure}'
            raise
        finally:
            client.close()
            args.output.write_text(json.dumps({'pass': passed, 'command': command, 'checks': checks,
                                               'error': error}, ensure_ascii=False, indent=2) + '\n')
    print(len(checks), 'end-to-end scenarios passed')


if __name__ == '__main__':
    _main()
