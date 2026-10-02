"""Bounded frozen-corpus native-tool pilot. Generated rows are NOT admitted."""
import argparse
import asyncio
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request

import aiohttp
import jinja2
from tokenizers import Tokenizer
from scripts import tokenize_chat_template as training

LANGUAGES = dict(da='Danish', en='English', nb='Norwegian Bokmal', nn='Norwegian Nynorsk',
    sv='Swedish', fo='Faroese', nl='Dutch', pl='Polish', de='German',
    fr='French', es='Spanish', it='Italian', cs='Czech', pt_pt='European Portuguese',
    fi='Finnish', et='Estonian', ca='Catalan', el='Greek', ro='Romanian', uk='Ukrainian', **{'is': 'Icelandic'})
TOOLS = [{'type': 'function', 'function': {'name': name, 'description': description,
    'parameters': {'type': 'object', 'properties': {key: {'type': 'string'}},
                   'required': [key], 'additionalProperties': False}}}
    for name, key, description in [
        ('search', 'query', 'Search the frozen World Bank statistics corpus, not the live web. English country names and indicator words work best.'),
        ('read', 'document_id', 'Read one complete frozen statistical record returned by search.')]]
COUNTRIES = ['DNK', 'SWE', 'NOR', 'FIN', 'ISL', 'DEU', 'FRA', 'ESP', 'ITA', 'NLD',
             'POL', 'CZE', 'PRT', 'EST', 'GRC', 'ROU', 'UKR', 'IRL', 'BEL', 'AUT',
             'CHE', 'GBR', 'CAN', 'JPN', 'AUS', 'NZL', 'USA', 'LUX', 'HRV', 'SVN']
INDICATORS = ['NY.GDP.MKTP.CD', 'NY.GDP.PCAP.CD', 'NY.GDP.MKTP.KD.ZG']
SYSTEM = ('Use the frozen source tools to answer the user. Search, then read the relevant records. '
    'Cite document IDs. Distinguish reference year, units and retrieval date. Do not infer current '
    'conditions from historical observations. If evidence is insufficient, say so. '
    'You have at most three searches and three reads. Be concise.')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(canonical(value) + '\n')
    temp.replace(path)


def fetch(root, url):
    key = sha(url.encode())
    path = root / 'snapshots' / (key + '.bin')
    receipt = path.with_suffix('.json')
    if not path.exists():
        request = urllib.request.Request(url, headers={'User-Agent': 'MimirSearchResearch/1.0'})
        with urllib.request.urlopen(request, timeout=90) as response:
            data = response.read()
            headers = dict(response.headers)
            status = response.status
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        save(receipt, dict(url=url, sha256=sha(data), retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                           status=status, headers=headers))
    meta = json.loads(receipt.read_text())
    data = path.read_bytes()
    if sha(data) != meta['sha256']:
        raise ValueError('snapshot hash mismatch')
    return data, meta


def prepare(root):
    if (root / 'corpus.json').exists():
        return json.loads((root / 'corpus.json').read_text())
    rights_url = 'https://www.worldbank.org/ext/en/legal/terms-conditions/datasets'
    _, rights = fetch(root, rights_url)
    catalog_url = 'https://datacatalog.worldbank.org/search/dataset/0037712/world-development-indicators'
    _, catalog = fetch(root, catalog_url)
    docs = []
    for indicator in INDICATORS:
        raw, metadata = fetch(root, f'https://api.worldbank.org/v2/indicator/{indicator}?format=json')
        description = json.loads(raw)[1][0]
        url = ('https://api.worldbank.org/v2/country/' + ';'.join(COUNTRIES) +
               f'/indicator/{indicator}?date=2018:2023&format=json&per_page=20000&source=2')
        raw, provenance = fetch(root, url)
        payload = json.loads(raw)
        if payload[0]['pages'] != 1:
            raise ValueError('incomplete API pagination')
        grouped = {}
        for row in payload[1]:
            if row['value'] is not None:
                grouped.setdefault(row['countryiso3code'], []).append({'year': row['date'], 'value': row['value']})
        for country, values in grouped.items():
            name = next(r['country']['value'] for r in payload[1] if r['countryiso3code'] == country)
            # Country groups, including all indicators and translated counterparts, never cross splits.
            split = 'heldout' if country in ('CAN', 'JPN', 'AUS') else 'train'
            docs.append(dict(id=country + ':' + indicator, country=name, country_code=country,
                title=name + ' ' + description['name'], indicator=indicator, definition=description['sourceNote'],
                values=sorted(values, key=lambda x: x['year']), split=split, temporal='stable',
                provenance=provenance, metadata_snapshot=metadata,
                attribution='The World Bank: World Development Indicators: ' + description['sourceOrganization'],
                rights={'license': 'CC-BY-4.0 with World Bank dataset additional terms',
                        'terms_snapshot': rights, 'catalog_snapshot': catalog,
                        'review': 'WDI catalog license; selected national-accounts indicators; independent rights confirmation required before admission'},
                projection='Complete non-null country/indicator records for requested 2018:2023 window; immutable raw API response retained'))
    save(root / 'corpus.json', docs)
    return docs


def execute(name, args, docs, visible):
    key = {'search': 'query', 'read': 'document_id'}.get(name)
    if not key or set(args) != {key} or not isinstance(args[key], str) or not args[key].strip():
        raise ValueError('invalid tool arguments')
    if name == 'search':
        terms = set(re.findall(r'\w+', args[key].casefold()))
        ranked = sorted(docs, key=lambda d: (-len(terms & set(re.findall(r'\w+', (d['title'] + ' ' + d['id']).casefold()))), d['id']))
        selected = [d for d in ranked if terms & set(re.findall(r'\w+', (d['title'] + ' ' + d['id']).casefold()))][:5]
        visible.update(d['id'] for d in selected)
        return {'scope': 'frozen corpus, not live web', 'results': [{'document_id': d['id'], 'title': d['title'], 'years': [v['year'] for v in d['values']]} for d in selected]}
    if args[key] not in visible:
        raise ValueError('read requires a prior search result')
    doc = next(d for d in docs if d['id'] == args[key])
    return {k: doc[k] for k in ('id', 'title', 'definition', 'values', 'attribution', 'projection')} | {
        'source_url': doc['provenance']['url'], 'retrieved_at': doc['provenance']['retrieved_at'],
        'snapshot_sha256': doc['provenance']['sha256']}


def seeds(docs, cap):
    eligible = [d for d in docs if d['split'] == 'train' and len(d['values']) >= 2]
    others = [l for l in LANGUAGES if l not in ('da', 'en')]
    schedule = ['da', 'en', 'da', 'other']
    for i in range(cap):
        lang = schedule[i % 4]
        if lang == 'other':
            lang = others[(i // 4) % len(others)]
        doc = eligible[(i // 4 + i % 4 * 17) % len(eligible)]
        first, last = doc['values'][0], doc['values'][-1]
        mode = (i // len(eligible)) % 3
        topic = doc['title']
        if lang == 'da':
            question = (f'Hvad var {topic} i {last["year"]}? Angiv enheden og kilden.' if mode == 0 else
                f'Sammenlign {topic} i {first["year"]} og {last["year"]}. Angiv begge tal, enheden og ' +
                ('den absolutte forskel.' if mode == 1 else 'om tallet steg eller faldt.'))
        else:
            question = (f'What was {topic} in {last["year"]}? Give the unit and source.' if mode == 0 else
                f'Compare {topic} in {first["year"]} and {last["year"]}. Give both values, the unit and ' +
                ('the absolute difference.' if mode == 1 else 'whether it increased or decreased.'))
            if lang != 'en':
                question += f' Answer in {LANGUAGES[lang]}.'
        yield dict(id=f'candidate-{i:04}', language=lang, question=question, temporal='stable',
                   source_group=doc['country_code'], oracle_document=doc['id'],
                   prompt_origin='agent-authored compositional; non-DA/EN prompts English with requested response language')


class Renderer:
    def __init__(self):
        info = json.loads(Path('data/sampled_dfm11/metadata.json').read_text())['tokenizer_info']
        self.tokenizer = Tokenizer.from_file(info['tokenizer_path'])
        self.template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())

    def prompt_length(self, messages):
        text = training.render(self.template, [training.normalize_message(m) for m in messages], TOOLS, True, False)
        return len(self.tokenizer.encode(text, add_special_tokens=False).ids)

    def targets(self, messages):
        lengths = []
        for i, message in enumerate(messages):
            if message['role'] == 'assistant':
                example = list(training.examples_from_messages(messages, TOOLS, i))[0]
                prompt, target = training.tokenize_example(self.tokenizer, self.template, example, False)
                lengths.append({'index': i, 'prompt_tokens': len(prompt), 'target_tokens': len(target), 'total': len(prompt) + len(target)})
        return lengths


async def generate(root, endpoint, docs, seed, renderer, session):
    folder = root / 'candidates' / seed['id']
    if (folder / 'result.json').exists():
        return
    messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': seed['question']}]
    visible = set(); counts = {'search': 0, 'read': 0}; final = False
    try:
        for turn in range(7):
            budget = min(768, 4096 - renderer.prompt_length(messages))
            if budget < 128:
                raise ValueError('native student budget exhausted; no truncation')
            payload = dict(model='dfm13-gemma4', messages=messages, tools=TOOLS, tool_choice='auto',
                temperature=0.2, max_tokens=budget, chat_template_kwargs={'enable_thinking': False})
            save(folder / f'request-{turn}.json', payload)
            async with session.post(endpoint.rstrip('/') + '/v1/chat/completions', json=payload) as response:
                raw = await response.json()
                save(folder / f'response-{turn}.json', raw)
                response.raise_for_status()
            choice = raw['choices'][0]
            if choice['finish_reason'] not in ('stop', 'tool_calls'):
                raise ValueError('incomplete generation: ' + str(choice['finish_reason']))
            source = choice['message']
            message = {'role': 'assistant', 'content': source.get('content') or ''}
            calls = source.get('tool_calls') or []
            if calls:
                message['tool_calls'] = calls
            messages.append(message)
            if not calls:
                if not message['content'].strip() or not counts['read']:
                    raise ValueError('final answer without source read or empty')
                final = True
                break
            for call in calls:
                name = call['function']['name']
                args = call['function']['arguments']
                args = json.loads(args) if isinstance(args, str) else args
                if name not in counts or counts[name] >= 3:
                    raise ValueError('tool budget or unknown tool')
                counts[name] += 1
                result = execute(name, args, docs, visible)
                save(folder / f'tool-{turn}-{counts[name]}-{name}.json', dict(call=call, result=result))
                messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': canonical(result)})
        if not final:
            raise ValueError('no final answer')
        lengths = renderer.targets(messages)
        if any(t['total'] > 4096 for t in lengths):
            raise ValueError('oversize native target')
        save(folder / 'result.json', dict(seed=seed, messages=messages, tools=TOOLS, target_lengths=lengths,
            target_message_indices=[t['index'] for t in lengths], status='pending_independent_review',
            admitted=False, oracle_withheld=True, source_corpus_sha256=sha((root / 'corpus.json').read_bytes())))
    except Exception as error:
        save(folder / 'result.json', dict(seed=seed, messages=messages, status='held', admitted=False,
                                         error=type(error).__name__ + ': ' + str(error)))


async def run(args):
    root = Path(args.root); root.mkdir(parents=True, exist_ok=True)
    with (root / 'campaign.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        save(root / 'launch.json', dict(pid=os.getpid(), endpoint=args.endpoint, concurrency=1,
            started_at=dt.datetime.now(dt.timezone.utc).isoformat(), candidate_cap=args.candidate_cap,
            accepted_target=200, desired_language_counts={'da': 100, 'en': 50, 'other_19': 50},
            desired_temporal_counts={'stable': 180, 'current': 20}, paid_calls=0,
            script_sha256=sha(Path(__file__).read_bytes()), admission='Independent controls/rights/source-grounded review required; no auto admission',
            limitations=['Initial tranche stable national-accounts only; current 20 not yet sourced',
                        'Non-DA/EN prompts currently English; output language needs independent assessment']))
        docs = prepare(root)
        queue = list(seeds(docs, args.candidate_cap))
        save(root / 'private-oracles.json', queue)
        renderer = Renderer()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            for seed in queue:
                await generate(root, args.endpoint, [d for d in docs if d['split'] == 'train'], seed, renderer, session)
                results = [json.loads(p.read_text()) for p in (root / 'candidates').glob('*/result.json')]
                progress = dict(terminal=len(results), pending_independent_review=sum(r['status']=='pending_independent_review' for r in results),
                               held=sum(r['status']=='held' for r in results), accepted=0, last_id=seed['id'])
                save(root / 'progress.json', progress)
                print(canonical(progress), flush=True)
        save(root / 'generation-complete.json', progress)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='data/dfm13/mimir-search-pilot200-20261001-v1')
    parser.add_argument('--endpoint', default='http://127.0.0.1:8810')
    parser.add_argument('--candidate-cap', type=int, default=320)
    asyncio.run(run(parser.parse_args()))
