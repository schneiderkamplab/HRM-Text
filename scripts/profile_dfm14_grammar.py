"""CPU-only grammar-mask diagnostic; never changes live servers or datasets."""
import argparse
import json
from pathlib import Path
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import xgrammar as xgr
from transformers import AutoTokenizer


def remove(node, keys):
    if isinstance(node, dict):
        return {k: remove(v, keys) for k, v in node.items() if k not in keys}
    if isinstance(node, list):
        return [remove(v, keys) for v in node]
    return node


def prefix(node):
    if 'enum' in node:
        return json.dumps(node['enum'][0]), False
    if node['type'] == 'string':
        return '"This is a sample text ', True
    if node['type'] == 'array':
        value, found = prefix(node['items'])
        return '[' + value, found
    values = []
    for key, child in node['properties'].items():
        value, found = prefix(child)
        values.append(json.dumps(key) + ':' + value)
        if found:
            return '{' + ','.join(values), True
    return '{' + ','.join(values) + '}', False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', required=True)
    p.add_argument('--prompts', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    info = xgr.TokenizerInfo.from_huggingface(tokenizer)
    compiler = xgr.GrammarCompiler(info, max_threads=8)
    schemas = {}
    for row in json.loads(args.prompts.read_text()):
        s = row['response_format']['json_schema']['schema']
        schemas.setdefault(json.dumps(s, sort_keys=True), s)
    results = []
    for number, schema in enumerate(schemas.values()):
        text, found = prefix(schema)
        if not found:
            continue
        for label, keys in [('original', ()), ('no_minLength', ('minLength',)),
                            ('no_maxLength', ('maxLength',)),
                            ('no_string_lengths', ('minLength', 'maxLength'))]:
            start = time.perf_counter()
            compiled = compiler.compile_json_schema(json.dumps(remove(schema, keys)))
            compile_seconds = time.perf_counter() - start
            matchers = [xgr.GrammarMatcher(compiled) for _ in range(512)]
            for matcher in matchers:
                assert matcher.accept_string(text), (number, label, text)
            masks = xgr.allocate_token_bitmask(512, info.vocab_size)
            def batch(start):
                for i in range(start, start + 16):
                    matchers[i].fill_next_token_bitmask(masks, i)
            timings = []
            with ThreadPoolExecutor(max_workers=8) as pool:
                for _ in range(11):
                    start = time.perf_counter()
                    list(pool.map(batch, range(0, 512, 16)))
                    timings.append(time.perf_counter() - start)
            result = dict(schema=number, variant=label, prefix=text,
                compile_seconds=compile_seconds,
                mask_512_ms=1000*statistics.median(timings[1:]))
            results.append(result)
            print(json.dumps(result), flush=True)
    args.output.write_text(json.dumps(dict(vocab_size=info.vocab_size,
        batch=512, workers=8, results=results), indent=2)+'\n')


if __name__ == '__main__':
    main()
