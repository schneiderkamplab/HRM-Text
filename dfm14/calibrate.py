"""Resumable calibration using native v4 assembly and indexed semantic review."""
import asyncio
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path
import time

import httpx
import jsonschema
import typer

from dfm12.io import file_hash, load, lock, rows, write_json
from dfm12 import multilingual_generation_v4 as generation
from dfm12 import multilingual_review_indexed as legacy_reviewer
from dfm12.wave_synthetic_runtime import Budget as BaseBudget
from dfm14 import synthetic_review as reviewer
from dfm14.synthetic_quality import assemble, source_issues, QualityFailure
from dfm14.catalog import LANGUAGES
from dfm14.readiness import TEACHER
from dfm14.generation_contract import VERSION, generation_payload, review_payload

app = typer.Typer()
MODEL = 'google/gemma-4-26B-A4B-it'


class Budget(BaseBudget):
    """Count the actual DFM14 template, including thinking-review reservations."""
    def measure(self, payload, limit=32768):
        from collections.abc import Mapping
        from dfm12.io import digest
        thinking = payload.get('chat_template_kwargs', {}).get('enable_thinking')
        if payload.get('model') != MODEL or type(thinking) is not bool:
            raise ValueError('Exact teacher and explicit thinking mode required')
        reserve = payload.get('max_tokens')
        if type(reserve) is not int or reserve <= 0 or type(limit) is not int or not 0 < limit <= 32768:
            raise ValueError('Invalid token budget')
        ids = self.tokenizer.apply_chat_template(payload['messages'], tokenize=True,
            add_generation_prompt=True, enable_thinking=thinking)
        if isinstance(ids, Mapping):
            ids = ids['input_ids']
        if not isinstance(ids, list) or any(type(i) is not int for i in ids):
            raise ValueError('Expected flat token IDs')
        if len(ids) + reserve > limit:
            raise ValueError(f'Full prompt {len(ids)} + reserve {reserve} exceeds {limit}; no truncation')
        return dict(prompt_tokens=len(ids), max_tokens=reserve, total_tokens=len(ids)+reserve,
                    context_limit=limit, token_ids_sha256=digest(ids))


def configure():
    from dfm12.prepare import Renderer
    config = load('data/dfm14/cpu-preparation-expanded/configuration.json')
    renderer = Renderer(config['tokenizer'], 4096)
    budget = Budget(TEACHER)
    # Local to this isolated client process; no edits to historical adapters.
    generation._renderer = lambda: renderer
    generation._prompt_budget = lambda: budget
    return budget


def audit_record(candidate):
    record = {k: candidate[k] for k in ('language', 'family', 'messages', 'tools')}
    record['language_name'] = LANGUAGES[candidate['language']]
    spec = candidate['provenance']
    record['requested_subtype'] = spec['subtype']
    for key in ('reference', 'scenario', 'terminal_evidence', 'tool_dialogue_grounding', 'source'):
        if key in spec:
            record[key] = spec[key]
        elif key in candidate:
            record[key] = candidate[key]
    if candidate['family'] == 'openhermes':
        record['source_messages'] = spec['source']['messages']
    return record


async def query(client, endpoint, payload, path):
    if path.exists():
        saved = load(path)
        if saved['payload'] != payload:
            raise ValueError('Request changed on resume')
        return saved['response']
    for attempt in range(3):
        try:
            response = await client.post(endpoint + '/chat/completions', json=payload)
            response.raise_for_status()
            body = response.json()
            write_json(path, dict(payload=payload, response=body, endpoint=endpoint, time=time.time()))
            return body
        except httpx.HTTPError:
            if attempt == 2:
                raise
            await asyncio.sleep(attempt + 1)


async def item(client, endpoint, row, directory, budget, semaphore):
    async with semaphore:
        path = directory / row['id']
        if (path / 'result.json').exists():
            return load(path / 'result.json')
        spec = row['spec']
        result = dict(id=row['id'], language=spec['language_code'], family=spec['family'], training_ready=False)
        stage = 'source_preflight'
        try:
            issues = source_issues(spec)
            if issues:
                raise QualityFailure(','.join(issues))
            stage = 'generation'
            payload, schema = generation_payload(spec, generation, MODEL)
            budget.measure(payload)
            transport = payload
            body = await query(client, endpoint, transport, path / 'generation.json')
            choice = body['choices'][0]
            if choice['finish_reason'] != 'stop':
                raise ValueError('Incomplete generation: ' + str(choice['finish_reason']))
            output = generation._parse(choice['message']['content'])
            jsonschema.validate(output, schema)
            stage = 'assembly'
            candidate = assemble(spec, output, generation)
            result['candidate'] = candidate
            record = audit_record(candidate)
            checks = legacy_reviewer.deterministic_checks(record)
            result['checks'] = checks
            if not all(c['passed'] for c in checks):
                raise QualityFailure('deterministic_reference_or_trajectory_failure')
            stage = 'review'
            payload = review_payload(record, MODEL)
            budget.measure(payload)
            transport = payload
            body = await query(client, endpoint, transport, path / 'review.json')
            choice = body['choices'][0]
            if choice['finish_reason'] != 'stop':
                raise ValueError('Incomplete review')
            review = generation._parse(choice['message']['content'])
            reviewer.validate(review, record)
            keep = reviewer.keeps(review, record)
            result.update(status='accepted' if keep else 'rejected', candidate=candidate, review=review, checks=checks)
        except QualityFailure as exc:
            result.update(status='held' if stage == 'source_preflight' else 'rejected',
                          stage=stage, error=str(exc))
        except (ValueError, KeyError, TypeError, httpx.HTTPError, jsonschema.ValidationError) as exc:
            result.update(status='error', stage=stage, error_type=type(exc).__name__, error=str(exc)[:1500])
        write_json(path / 'result.json', result)
        return result


async def execute(root, output, endpoint, concurrency):
    budget = configure()
    manifest = load(root / 'manifest.json')
    async with httpx.AsyncClient(timeout=900, limits=httpx.Limits(max_connections=concurrency,max_keepalive_connections=concurrency)) as client:
        info = await client.get(endpoint + '/models'); info.raise_for_status()
        assert any(m['id']==MODEL and m.get('max_model_len',0)>=32768 for m in info.json()['data'])
        # Small mixed-family chunks keep all endpoints useful without language barriers.
        groups = [list(rows(g['path'])) for g in manifest['groups']]
        interleaved = [group[i] for i in range(max(map(len,groups))) for group in groups if i < len(group)]
        for start in range(0, len(interleaved), concurrency):
            for gi, group in enumerate([interleaved]):
                chunk = group[start:start+concurrency]
                if not chunk:
                    continue
                directory = output / f'chunk-{start:06d}-{gi:03d}'
                try:
                    with lock(directory / '.lock'):
                        if (directory / 'receipt.json').exists():
                            continue
                        semaphore = asyncio.Semaphore(concurrency)
                        results = await asyncio.gather(*(item(client,endpoint,r,directory,budget,semaphore) for r in chunk))
                        counts = dict(Counter(r['status'] for r in results))
                        write_json(directory / 'receipt.json', dict(rows=len(results),counts=counts,endpoint=endpoint))
                        print(json.dumps(dict(chunk=directory.name,counts=counts)),flush=True)
                except BlockingIOError:
                    continue


def worker(*args):
    asyncio.run(execute(*args))


@app.command()
def run(root: Path=Path('data/dfm14/generation-calibration-v1'), output: Path=Path('data/dfm14/calibration-v1'),
        endpoints: list[str]=typer.Option(...,'--endpoint'), concurrency: int=128):
    if len(set(endpoints))!=len(endpoints) or not 1<=concurrency<=1024:
        raise ValueError('Unique endpoints and valid concurrency required')
    manifest = load(root / 'manifest.json')
    for group in manifest['groups']:
        if file_hash(group['path']) != group['sha256']:
            raise ValueError('Calibration input changed')
    config=dict(input_sha256=file_hash(root/'manifest.json'),model=MODEL,concurrency=concurrency,
                contract=VERSION,code_sha256={str(p):file_hash(p) for p in
                    [Path(__file__),Path('dfm14/generation_contract.py'),
                     Path('dfm14/synthetic_quality.py'),Path('dfm14/synthetic_review.py'),
                     Path(generation.__file__),Path('dfm12/multilingual_tool_dialogue.py'),
                     Path('dfm12/multilingual_tasks.py'),Path('dfm12/multilingual_calibration_v6.py'),
                     Path('dfm12/wave_synthetic_runtime.py')]})
    with lock(output / '.controller.lock'):
        if (output/'configuration.json').exists() and load(output/'configuration.json')!=config:
            raise ValueError('Calibration configuration changed')
        write_json(output/'configuration.json',config)
        with ProcessPoolExecutor(max_workers=len(endpoints)) as pool:
            futures=[pool.submit(worker,root,output,e,concurrency) for e in endpoints]
            for future in futures: future.result()
        counts=Counter()
        groups={}
        for path in output.glob('chunk-*/*/result.json'):
            r=load(path); counts[r['status']]+=1
            groups.setdefault(r['language']+'/'+r['family'],Counter())[r['status']]+=1
        write_json(output/'summary.json',dict(counts=dict(counts),groups={k:dict(v) for k,v in groups.items()},
                   expected=manifest['rows'],production_authorized=False))


if __name__=='__main__':
    app()
