"""CPU-only replay of captured reviewer whitespace boundaries."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import time
import sys

os.environ['CUDA_VISIBLE_DEVICES'] = ''
import xgrammar as xg
from transformers import AutoTokenizer

ROOT = Path('data/dfm12/multilingual-calibration-strong-penalty-20260927/raw')
OUT = Path('data/dfm12/reviewer-boundary-probe-20260927')
MODEL = '/work/mimir/.home/.cache/huggingface/hub/models--google--gemma-4-26B-A4B-it/snapshots/4d7ae4984b7db7de8f8457170b3f1a419ee76d52'


def main():
    global ROOT, OUT
    if len(sys.argv) > 1:
        ROOT = Path(sys.argv[1]) / 'raw'
        OUT = OUT / 'simple-schema'
    OUT.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    info = xg.TokenizerInfo.from_huggingface(tokenizer, vocab_size=262144)
    compiler = xg.GrammarCompiler(info, max_threads=1)
    results = []
    for path in sorted(ROOT.glob('*.response.json')):
        response = json.loads(path.read_text())
        content, token_ids = '', []
        for line in base64.b64decode(response.get('raw_body_base64', '')).decode().splitlines():
            if not line.startswith('data: {'):
                continue
            for choice in json.loads(line[6:]).get('choices', []):
                content += choice.get('delta', {}).get('content') or ''
                token_ids.extend(choice.get('token_ids') or [])
        loop = re.search(r'\s{100,}', content)
        if not loop and not ('literal_quote' in content and '\\"' in content):
            continue
        request_path = path.with_name(path.name.replace('response', 'request'))
        request = json.loads(request_path.read_text())['request']
        schema = request['structured_outputs']['json']
        compiled = compiler.compile_json_schema(json.dumps(schema), any_whitespace=True)
        result = {'response': str(path), 'request_sha256': hashlib.sha256(request_path.read_bytes()).hexdigest(),
                  'actual_token_ids_present': bool(token_ids), 'boundaries': []}
        boundaries = [('before_loop', content[:loop.start()]), ('after_loop', content)] if loop else [('captured_end', content)]
        quote_start = re.search(r'"literal_quote"\s*:\s*"', content)
        if quote_start:
            for match in list(re.finditer(r'\\"', content[quote_start.end():]))[:3]:
                pos = quote_start.end() + match.start()
                boundaries.append(('before_escaped_quote', content[:pos]))
            try:
                _, end = json.JSONDecoder().raw_decode(content, quote_start.end() - 1)
                boundaries.append(('before_literal_closing_quote', content[:end-1]))
            except ValueError:
                pass
        for name, prefix in boundaries:
            matcher = xg.GrammarMatcher(compiled)
            ids = tokenizer.encode(prefix, add_special_tokens=False)
            rejected = next((i for i, token in enumerate(ids) if not matcher.accept_token(token)), None)
            entry = {'name': name, 'prefix': prefix, 'retokenized_count': len(ids), 'first_rejected_index': rejected,
                     'roundtrip_exact': tokenizer.decode(ids) == prefix}
            string_matcher = xg.GrammarMatcher(compiled)
            entry['string_prefix_accepted'] = string_matcher.accept_string(prefix)
            if rejected is None:
                mask = xg.allocate_token_bitmask(1, 262144)
                start = time.monotonic()
                matcher.fill_next_token_bitmask(mask)
                entry['mask_seconds'] = time.monotonic() - start
                entry['probes'] = {}
                for text in ['}', '},', ' ', '\n', 'true', 'false', ',', '"', '\\"', '"}', '",']:
                    probe_ids = tokenizer.encode(text, add_special_tokens=False)
                    fork = matcher.fork()
                    entry['probes'][text] = {'ids': probe_ids,
                        'first_token_mask_allowed': bool(int(mask[0, probe_ids[0] // 32]) & (1 << (probe_ids[0] % 32))),
                        'sequence_accepted': all(fork.accept_token(t) for t in probe_ids)}
                entry['stop_mask_allowed'] = {str(t): bool(int(mask[0, t // 32]) & (1 << (t % 32))) for t in matcher.stop_token_ids}
            result['boundaries'].append(entry)
        results.append(result)
        print(path.name, [(b['name'], b.get('probes', {}).get('}'), b['first_rejected_index']) for b in result['boundaries']], flush=True)
        (OUT / 'results.json').write_text(json.dumps({'caveat': 'Text retokenization is not replay of original sampled token IDs; captures have null token_ids. CPU only, no logits or live GPU state.', 'results': results}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
