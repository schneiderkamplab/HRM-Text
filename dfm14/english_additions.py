"""Explicit licensed English components; never ingest aggregate mixture configs."""
from pathlib import Path
from dfm12.io import write_json


def sources():
    result = []
    def add(repo, component, patterns, repeat, adapter=None):
        result.append(dict(repo=repo, component=component, patterns=patterns,
            kind='instruction', languages=['en'], repeat=repeat,
            license='mit' if repo.startswith(('OpenCoder-', 'HuggingFaceH4/')) else 'apache-2.0',
            adapter=adapter, max_row_chars=500000, max_training_tokens=4096,
            inherited_dedup_required=True, admission='independent_audit_required'))
    for name in ['smol-magpie-ultra', 'smol-constraints', 'smol-rewrite', 'smol-summarize']:
        add('HuggingFaceTB/smoltalk', name, [f'data/{name}/train-*.parquet'],
            1 if name == 'smol-magpie-ultra' else 2)
    for name in ['multi_turn_reasoning_if_think', 'smolagents_toolcalling_traces_think']:
        add('HuggingFaceTB/smoltalk2', name, [f'SFT/{name}-*.parquet'], 2, 'smoltalk_native')
    for name in ['educational_instruct', 'package_instruct']:
        add('OpenCoder-LLM/opc-sft-stage2', 'opencoder-'+name,
            [f'{name}/train-*.parquet'], 1)
    add('HuggingFaceH4/ultrachat_200k', 'ultrachat-nonoverlapping',
        ['data/train_sft-*.parquet'], 1)
    return result


if __name__ == '__main__':
    from dfm14.prepare import run
    root = Path('data/dfm14/english-additions-v1')
    manifest = root/'sources.json'
    write_json(manifest, sources())
    write_json(root/'admission-policy.json', dict(repeats={s['component']:s['repeat'] for s in sources()},
        training_ready=False, required=['native formatting', 'inherited and cross-source deduplication',
        'benchmark decontamination', 'independent quality audit', 'accepted-only export'],
        excluded=['aggregate configs', 'raw OpenHermes', 'LongAlign', 'OpenCoder evol and McEval', 'heldout splits']))
    run(root=root, workers=16, download_workers=8, max_files=100, source_gib=16,
        rows_per_file=1000000, download_root=Path('data/dfm14/downloads'),
        curated_supplements=False, source_manifest=manifest)
