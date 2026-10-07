"""Construct every new task and check paired shards and semantic merge labels."""
from pathlib import Path
from dfm12.io import file_hash, write_json
from scripts.prepare_dfm14_eval_extension import ROOT, OUT, MANIFEST, SUITE, REGISTRY, POPULATION
from evaluation.dfm14_tasks import LANGUAGES, dala_dfm14, gec_dala_dfm14
from scripts.dala_semantic import extract_semantic_label


def main():
    from scripts.headline_population_registry import load_registry
    populations = load_registry(POPULATION)
    assert sorted(len(p['languages']) for p in populations['populations']) == [16,48,50]
    tasks = 0
    for lang in LANGUAGES:
        for constructor in (dala_dfm14, gec_dala_dfm14):
            seen = set()
            for shard in range(4):
                task = constructor(language=lang, manifest=str(MANIFEST), num_shards=4, shard_index=shard)
                ids = {sample.id for sample in task.dataset}
                assert len(ids) == 500 and not ids & seen
                seen.update(ids)
                for sample in task.dataset:
                    assert sample.metadata['split'] == 'test'
                    assert sample.metadata['language'] == lang
            assert len(seen) == 2000
            tasks += 1
        assert extract_semantic_label(' "YES." ', lang) == 'correct'
        assert extract_semantic_label(' No! ', lang) == 'incorrect'
        assert extract_semantic_label('yes, but maybe not', lang) is None
        print('Verified', lang, flush=True)
    files = [MANIFEST, SUITE, REGISTRY, POPULATION, ROOT/'evaluation/dfm14_tasks.py',
             ROOT/'scripts/dala_semantic.py', ROOT/'scripts/headline_population_registry.py']
    write_json(OUT/'preflight.json', dict(passed=True, tasks=tasks, samples=64000, gpu_calls=False,
               files={str(p):file_hash(p) for p in files}))


if __name__ == '__main__':
    main()
