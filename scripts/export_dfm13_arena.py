#!/usr/bin/env python3
"""Export and publish the three converted Arena sources with their provenance."""
import argparse
import json
from pathlib import Path
import shutil

from prepare_dfm13_arena import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    specs = json.loads(Path('config/dfm13_sources.json').read_text())['additions']
    for spec in specs:
        if spec['converter'] != 'scripts/prepare_dfm13_arena.py':
            continue
        source = Path(spec['output'])
        manifest_path = source.with_suffix('.manifest.json')
        manifest = json.loads(manifest_path.read_text())
        assert sha256(source) == manifest['output_sha256']
        name = 'dfm13-' + spec['name'].replace('_', '-') + '-preferred'
        output = Path('exports_dfm13') / name
        (output / 'data').mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output / 'data/train.jsonl')
        shutil.copyfile(manifest_path, output / 'manifest.json')
        counts = manifest['counts']
        license_yaml = 'license: apache-2.0' if spec['name'].endswith('55k') else (
            'license: other\nlicense_name: cc-by-prompts-and-provider-output-terms\n'
            f'license_link: https://huggingface.co/datasets/{spec["repo_id"]}#license')
        card = f'''---
{license_yaml}
task_categories:
- text-generation
tags:
- conversational
- multilingual
- dfm13
size_categories:
- 10K<n<100K
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train.jsonl
---
# {name}

Winner-selected SFT examples prepared by schneiderkamplab from
[{spec['repo_id']}](https://huggingface.co/datasets/{spec['repo_id']})
at pinned revision `{spec['revision']}`.

## Data and Selection

{counts['source_rows']:,} upstream rows yield **{counts['training_examples']:,} examples**,
including {counts['multiturn_examples']:,} with multi-turn context.
Retain only explicit model-A/model-B winners. Exclude ties and both-bad votes;
ties do not imply both responses are good. There is no held-out split.
All source languages are retained, without automatic language reclassification.
55K has no per-row language labels; its language metadata is unspecified.

Exact full-message deduplication across the Danish AI-Arenaen addition and
the 140K, 100K, 55K releases, in that order, removed
{counts.get('exact_duplicates', 0):,} examples from this release.
{counts.get('invalid_rows', 0):,} rows were excluded for invalid content/history.
This is not fuzzy deduplication or a benchmark decontamination claim.

## Supervision and Templates

**Supervise only the final assistant response identified by
`target_message_index`.** Earlier user and assistant messages are context and
must be masked from the loss. A conversation-level preference does not prove
that every earlier assistant response is approved.

`messages` contains structured roles and visible text, not raw template tokens.
Use the target tokenizer's multi-turn chat template. Our Gemma4 path uses
`chat_template_kwargs.enable_thinking=false` and target-only loss. Generic
all-assistant-turn SFT collators must be adapted to honor the target index.

55K JSON turn arrays are interleaved. 100K message arrays are preserved.
140K's current evaluation block is uniquely matched to the selected side's
history, with previous context retained and future turns excluded. Ambiguous
matches fail closed. Separate hidden reasoning fields are not injected.
Visible answers are not rewritten or translated. Model names and vote metadata
remain outside the training text.

`metadata` records source, revision, source ID, selected side, winning model,
language, source licensing and content hash. `manifest.json` contains exact
counts, vote/language distributions, source file hashes and output SHA256.

## Attribution and Licensing

Source licensing: **{spec['license']}**. For the 100K and 140K releases,
the upstream cards license user prompts under CC-BY-4.0 and explicitly place
model outputs under their respective providers' terms. This derivative does
not grant additional rights or claim a blanket CC-BY license for outputs.
55K's source card declares Apache-2.0; retained source provenance permits
checking the original terms and attribution.

Please credit the source dataset and *Chatbot Arena: An Open Platform for
Evaluating LLMs by Human Preference*, Chiang et al. (2024),
https://arxiv.org/abs/2403.04132, and this schneiderkamplab conversion.

## Limitations

Preference is relative, not a correctness or safety certificate. Data can
contain errors, offensive content, personal information, outdated model
identities and benchmark overlap. No additional privacy, quality or safety
audit is claimed. Earlier context may contain nonpreferred answers. No model
generation or repair was used to create this derivative.
'''
        (output / 'README.md').write_text(card)
        result = {'repo_id': 'schneiderkamplab/' + name,
                  'rows': counts['training_examples'], 'bytes': source.stat().st_size}
        if args.upload:
            from huggingface_hub import HfApi, hf_hub_download
            api = HfApi()
            api.create_repo(result['repo_id'], repo_type='dataset', private=False, exist_ok=True)
            commit = api.upload_folder(repo_id=result['repo_id'], repo_type='dataset', folder_path=output,
                                       allow_patterns=['README.md', 'manifest.json', 'data/train.jsonl'],
                                       commit_message='Publish deduplicated winner-selected Arena SFT')
            remote = hf_hub_download(result['repo_id'], 'data/train.jsonl', repo_type='dataset', revision=commit.oid)
            assert sha256(Path(remote)) == manifest['output_sha256']
            result.update(commit=commit.oid, verified=True)
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
