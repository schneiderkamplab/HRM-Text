"""Frozen prose samples and independent judges; manual labels never enter prompts."""
import argparse
import asyncio
from collections import defaultdict
import getpass
import json
import os
from pathlib import Path
import random

import httpx

from audit_pipeline.runtime import EndpointUnavailable, run
from dfm12.io import atomic, file_hash, load, lock, rows, write_json
from scripts.queue_dfm16_stories_qwen import DEFAULT, audited_records, prepare_stage
from scripts.run_dfm16_odin_judge import OdinProse, RateLimitedClient

ROOT = DEFAULT/'ensemble-study'
MODELS = {'odin': ('odin-2-large', 'https://api.odincore.ai/v1'),
          'qwen27b': ('Qwen/Qwen3.8-27B', 'http://127.0.0.1:8505/v1'),
          'flash': ('Qwen/Qwen3.8-Flash-Next-FP8', 'http://127.0.0.1:8500/v1')}
QUESTIONS = {'language': 'Is the text grammatically acceptable and naturally written?',
             'coherence': 'Is the text understandable and internally coherent?'}


def save_rows(path, records):
    with atomic(path) as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False)+'\n')


def prepare(root):
    if (root/'samples.jsonl').exists():
        return
    samples = []
    for i, row in enumerate(rows(DEFAULT/'odin-accepted-manual-sample.jsonl'), 1):
        samples.append(dict(row, study_id=f'C{i:03}', cohort='current',
            language=row['label'].split('/')[0], task=row['label'].split('/')[1]))
    old = {r['id'] for r in rows(DEFAULT/'manual-review.jsonl')}
    groups = defaultdict(list)
    for source, result in audited_records(DEFAULT/'review'):
        if result.get('review', {}).get('decision') == 'accept' and source['id'] not in old:
            groups[(source['language'], source['task'])].append(source)
    rng = random.Random(20261029)
    for language in ('da', 'en', 'hi', 'ja'):
        tasks = ('creative', 'qa', 'revision', 'rewrite', 'summary')
        quotas = {task: min(10, len(groups[language, task])) for task in tasks}
        while sum(quotas.values()) < 50:
            for task in tasks:
                if quotas[task] < len(groups[language, task]) and sum(quotas.values()) < 50:
                    quotas[task] += 1
        for task in tasks:
            selected = rng.sample(sorted(groups[language, task], key=lambda r:r['id']), quotas[task])
            for source in selected:
                turns = [(i,m['content']) for i,m in enumerate(source['messages']) if m['role']=='assistant']
                turn, text = rng.choice(turns)
                samples.append(dict(study_id=f'H{len(samples)-19:03}', cohort='holdout',
                    parent_id=source['id'], turn_index=turn, language=language, task=task, text=text))
    assert len(samples) == 220
    assert len({r['parent_id'] for r in samples[20:]}) == 200
    assert not old.intersection(r['parent_id'] for r in samples[20:])
    save_rows(root/'samples.jsonl', samples)
    for name in MODELS:
        checks = []
        for row in samples:
            if name == 'odin' and row['cohort'] == 'current':
                continue  # Reuse identical previously completed Odin judgments.
            for aspect, question in QUESTIONS.items():
                identifier = row['study_id']+'/'+aspect
                checks.append(dict(row, id=identifier, audit_id=identifier, aspect=aspect,
                    prompt=f'Text:\n{row["text"]}\n\n{question} Answer only yes or no.'))
        prepare_stage(root/name, checks, 'ensemble_prose_v1')
    write_json(root/'design.json', dict(seed=20261029, samples_sha256=file_hash(root/'samples.jsonl'),
        current=20, holdout=200, unit='one intact assistant text per parent',
        policy='accept only if every selected judge accepts language AND coherence',
        scope='standalone prose; no source fidelity or instruction compliance',
        production_authorized=False))


class StudyJudge(OdinProse):
    def prepare(self, row):
        payload = super().prepare(row)
        if self.model != 'odin-2-large':
            payload['chat_template_kwargs'] = dict(enable_thinking=False)
        return payload

    def report(self, snapshot):
        write_json(self.output/'pipeline/live.json', snapshot)


async def judge(root, name, key=None):
    stage = root/name
    state = stage/'audit/pipeline/state.json'
    if state.exists() and load(state)['phase'] == 'complete':
        print(name+' already complete')
        return
    model, endpoint = MODELS[name]
    adapter = StudyJudge(stage, stage/'audit', endpoint)
    adapter.model = model
    if name == 'odin':
        client = RateLimitedClient(64, 90, 61, headers={'Authorization':'Bearer '+key},
            timeout=120, trust_env=False, follow_redirects=False,
            limits=httpx.Limits(max_connections=64))
        concurrency = 64
    else:
        client = httpx.AsyncClient(timeout=180, trust_env=False,
            limits=httpx.Limits(max_connections=128))
        concurrency = 128
    async with client:
        if name == 'odin':
            print('Odin: 64 concurrency; conservative 90 requests/minute (below 180 cap)', flush=True)
            await asyncio.sleep(65)
        write_json(state, dict(phase='running', model=model))
        try:
            await run(adapter, endpoint, concurrency, client=client, prefetch=1)
            write_json(state, dict(phase='complete', model=model))
        except BaseException as exc:
            write_json(state, dict(phase='failed', model=model, error_type=type(exc).__name__))
            raise
    print(name+' complete (verdicts withheld until manual labels)', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', *MODELS])
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    with lock(args.root/('.'+args.action+'.lock')):
        if args.action == 'prepare':
            prepare(args.root)
        else:
            key = (os.environ.get('ODIN_API_KEY') or getpass.getpass('API key: ')) if args.action=='odin' else None
            for attempt in range(6):
                try:
                    asyncio.run(judge(args.root, args.action, key))
                    break
                except EndpointUnavailable:
                    if args.action != 'odin' or attempt == 5:
                        raise
                    print('API unavailable: resume pending rows after quota cooldown', flush=True)


if __name__ == '__main__':
    main()
