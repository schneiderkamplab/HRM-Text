"""Qualify prepared GGUFs against the direct training tokenizer and chat smoke cases."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

__all__ = []


def _sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--gguf', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / 'llama.cpp/gguf-py'))
    import gguf
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(args.model / 'tokenizer.json'))
    audit = json.loads((root / 'native/mimir/training-tokenizer-audit.json').read_text())
    requests = [row['request'] for row in audit['models']['bundled']['results']]
    report = {'reference': 'Tokenizer.from_file(tokenizer.json), add_special_tokens=False',
              'tokenizer_sha256': _sha(args.model / 'tokenizer.json'), 'models': []}

    def run(path, device, queries, inspect=False):
        command = [str(args.client), '--model', str(path), '--device', device, '--json']
        command += ['--inspect'] if inspect else ['--ctx', '1024', '--batch', '1024', '--max-tokens', '32']
        process = subprocess.run(command, input='\n'.join(map(json.dumps, queries)) + '\n',
                                 text=True, capture_output=True, timeout=240)
        if process.returncode:
            raise RuntimeError(process.stderr[-2000:])
        events = [json.loads(line) for line in process.stdout.splitlines()]
        if any(e['event'] == 'error' for e in events):
            raise AssertionError(events)
        return events

    for path in args.gguf:
        reader = gguf.GGUFReader(path)
        assert reader.fields['tokenizer.ggml.pre'].contents() == 'gemma4'
        assert reader.fields['hrm_text.hrm.prefix_lm'].contents()
        byte_count = reader.fields['tokenizer.ggml.token_type'].contents().count(gguf.TokenType.BYTE)
        assert byte_count == 256
        prepared = [e for e in run(path, 'cpu', requests, True) if e['event'] == 'prompt']
        assert len(prepared) == len(requests)
        for event in prepared:
            assert event['tokens'] == tokenizer.encode(event['text'], add_special_tokens=False).ids
        result = {'file': path.name, 'bytes': path.stat().st_size, 'sha256': _sha(path),
                  'tokenizer_cases_passed': len(prepared), 'byte_fallback_tokens': byte_count,
                  'tensor_types': sorted({t.tensor_type.name for t in reader.tensors}), 'generation': {}}
        for device in ['cpu', 'metal']:
            queries = [{'op': 'reply', 'text': 'Hvad hedder Danmarks hovedstad?'},
                       {'op': 'reset'}, {'op': 'reply', 'text': 'What is 2 + 2? Answer briefly.'}]
            done = [e for e in run(path, device, queries) if e['event'] == 'done']
            assert len(done) == 2 and all(e['status'] == 0 and e['text'] for e in done)
            assert 'København' in done[0]['text']
            assert '4' in done[1]['text'] or 'four' in done[1]['text'].lower()
            result['generation'][device] = done
        report['models'].append(result)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        print(f"{path.name}: {len(prepared)} tokenizer cases and CPU/Metal chats passed", flush=True)


if __name__ == '__main__':
    _main()
