"""Prepare balanced story seeds and immutable accepted-target generation waves."""
import argparse
from collections import Counter
import json
from pathlib import Path
import random

from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from scripts.prepare_dfm16_dyna import publish_audit_manifest

ROOT = Path('data/dfm16/expansion-v1')
STORIES = ROOT/'stories'
CONFIG = Path('config/dfm16_expansion.json')


def seed_pools(root=ROOT):
    out = root/'stories'
    with lock(out/'.seeds.lock'):
        if (out/'seed-receipt.json').exists():
            receipt = load(out/'seed-receipt.json')
            for name, checksum in receipt['files'].items():
                if file_hash(out/name) != checksum:
                    raise ValueError('Changed seed pool')
            return
        groups = [('SimpleStories/SimpleStories', 'story', ['en', 'da'], 150000),
                  ('SimpleStories/SimpleStories-JA', 'story', ['ja'], 20000),
                  ('SmallScale/Simple-Stories-Eng-Hin', 'hindi', ['hi'], 20000)]
        outputs, counts = {}, {}
        for repo, field, languages, capacity in groups:
            directory = root/'downloads'/repo.replace('/', '__')
            status = load(directory/'status.json')
            if status['phase'] != 'downloaded':
                raise RuntimeError(f'Seed source not downloaded: {repo}')
            pin = load(directory/'source.json')
            snapshot = directory/'snapshot'
            files = sorted(p for p in snapshot.rglob('*') if p.suffix in ('.parquet', '.jsonl')
                           and 'train' in str(p.relative_to(snapshot)))
            if not files:
                raise ValueError('Missing explicit training files')
            rng, pool, eligible = random.Random(20261027), [], 0
            for path in files:
                for index, row in enumerate(rows(path)):
                    story = row.get(field)
                    if not isinstance(story, str) or not 100 <= len(story) <= 12000:
                        continue
                    provenance = dict(repo_id=repo, revision=pin['revision'],
                        file=str(path.relative_to(snapshot)), row=index,
                        source_id=row.get('generation_id'), source_family=digest(row.get('english') or story))
                    record = dict(text=story, provenance=provenance)
                    eligible += 1
                    if len(pool) < capacity:
                        pool.append(record)
                    else:
                        slot = rng.randrange(eligible)
                        if slot < capacity:
                            pool[slot] = record
            # Shared English/Danish pool partitions are disjoint, not duplicated translations.
            for language in languages:
                selected = pool if len(languages) == 1 else (pool[:120000] if language == 'en' else pool[120000:])
                unique = {r['provenance']['source_family']: r for r in selected}
                if len(unique) < 1000:
                    raise ValueError('Insufficient diverse story seeds')
                name = f'seeds-{language}.jsonl'
                with atomic(out/name) as stream:
                    for record in unique.values():
                        stream.write(json.dumps(record, ensure_ascii=False)+'\n')
                outputs[name] = file_hash(out/name)
                counts[language] = len(unique)
        write_json(out/'seed-receipt.json', dict(files=outputs, counts=counts, selection='uniform reservoir over full train files', seed=20261027))


def prepare_wave(root=ROOT, wave=0):
    config = load(CONFIG)['simple_stories']
    stories = root/'stories'
    out = stories/f'wave-{wave:02}'
    with lock(out/'.prepare.lock'):
        if (out/'readiness.json').exists():
            return out
        accepted = Counter()
        for previous in sorted(stories.glob('wave-*/audit/*/results.jsonl')):
            for result in rows(previous):
                if result.get('status') == 'reviewed' and result.get('review', {}).get('decision') == 'accept':
                    candidate = result['candidate']
                    accepted[candidate['language'], candidate['task']] += 1
        pools = {lang: list(rows(stories/f'seeds-{lang}.jsonl')) for lang in config['accepted_targets']}
        pending, chunks = [], []
        def flush():
            if not pending:
                return
            name = f'chunks/{len(chunks):05}.jsonl'
            with atomic(out/name) as stream:
                for record in pending:
                    stream.write(json.dumps(record, ensure_ascii=False)+'\n')
            chunks.append(dict(job_id=f'stories-{len(chunks):05}', input=name, rows=len(pending),
                               task='story_generation_review', sha256=file_hash(out/name)))
            pending.clear()
        groups = []
        for lang, total in config['accepted_targets'].items():
            offset = 0
            for task, percentage in config['task_percentages'].items():
                target = total*percentage//100
                missing = max(0, target-accepted[lang, task])
                groups.append(dict(language=lang, task=task, target=target, remaining=missing, offset=offset))
                offset += target
        # Interleave groups so a language/family does not become a GPU tail.
        for start in range(0, max(g['remaining'] for g in groups), config['chunk_size']):
            for group in groups:
                for i in range(start, min(start+config['chunk_size'], group['remaining'])):
                    lang, task = group['language'], group['task']
                    pool = pools[lang]
                    seed = pool[(group['offset']+i+wave*7919) % len(pool)]
                    key = digest([wave, lang, task, i, seed['provenance']])
                    revisions = (2 if i % 10 < 6 else 3 if i % 10 < 9 else 4) if task == 'revision' else 0
                    pending.append(dict(id=key, audit_id=key, language=lang, task=task,
                        variant=wave*1000000+i, revisions=revisions, seed=seed['text'],
                        provenance=dict(seed['provenance'], language=lang, task=task, wave=wave)))
                flush()
        write_json(out/'tokenizer.json', load('data/dfm15/native-reasoning-v2/sampled_dfm15/metadata.json')['tokenizer_info'])
        publish_audit_manifest(out, chunks)
        write_json(out/'targets.json', dict(groups=groups, config_sha256=file_hash(CONFIG),
                   seed_receipt_sha256=file_hash(stories/'seed-receipt.json')))
        return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--wave', type=int, default=0)
    args = parser.parse_args()
    seed_pools(args.root)
    print(prepare_wave(args.root, args.wave))
