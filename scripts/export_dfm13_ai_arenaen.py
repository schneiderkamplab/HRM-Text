#!/usr/bin/env python3
"""Package and optionally publish the vote-selected AI-Arenaen dataset."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


CARD = """---
license: cc-by-4.0
language:
- da
task_categories:
- text-generation
tags:
- conversational
- dfm13
size_categories:
- 1K<n<10K
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train.jsonl
---
# DFM13 AI-Arenaen Preferred Conversations

Derived from [Danish Foundation Models' AI-Arenaen](https://huggingface.co/datasets/danish-foundation-models/ai-arenaen)
at revision `bb3b6d28e4e159fb23dbf9aa4f9902696ed678be`, under CC-BY-4.0.
Prepared by schneiderkamplab for DFM13. See `manifest.json` for provenance and hashes.

## Selection

The 3,879 source rows contain turn-level human votes. We retain A for
`a_better` (735 examples), B for `b_better` (743), and both sides separately
for `both_good` (1,124). Other votes and missing votes are excluded.
The train split contains 2,602 examples, including 361 with multi-turn context.
No validation or test split is claimed.

## Training Format: Selected Answer Only

`messages` preserves the selected side's preceding conversation and ends at
the rated assistant response. **Only `target_message_index` is a supervised
target.** Earlier assistant messages are context, not additional targets.
Earlier positively rated turns already receive separate examples through their
own votes. Do not apply loss to all assistant turns in each row.

Render the preceding messages and selected response with your tokenizer's
multi-turn chat template, and mask all preceding context from the loss.
For our Gemma4 pipeline, use `chat_template_kwargs.enable_thinking=false`
and target-only loss. The JSONL contains structured messages, not pre-rendered
template tokens. Generic trainers must explicitly honor the target index.

`id` identifies the source response and selected side. `metadata` records
source revision, vote, side, model, conversation/response identifiers and repairs.
Only visible content is included; separate reasoning fields are omitted.
Future conversation turns are removed. One exact duplicate consecutive user
message was removed; malformed or ambiguous histories otherwise fail closed.
Both-good sides are kept even if identical.

## Limitations

Human preference is relative, not a factual-correctness or safety guarantee.
Responses can contain factual errors, language errors, harmful content or
personal information present in the source. No additional safety, quality,
language-identification or privacy audit is claimed. Danish is the intended
domain, not a guarantee that every message is Danish. This derived dataset
can overlap earlier AI-Arenaen releases; check overlap before combining them.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('data/converted_sources/dfm13/ai_arenaen_preferred'))
    parser.add_argument('--output', type=Path, default=Path('exports_dfm13/dfm13-ai-arenaen-preferred'))
    parser.add_argument('--repo-id', default='schneiderkamplab/dfm13-ai-arenaen-preferred')
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    source = args.source / 'train.jsonl'
    manifest = json.loads((args.source / 'train.manifest.json').read_text())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == manifest['output_sha256'], 'Source hash mismatch'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    assert len(rows) == manifest['counts']['training_examples']
    assert len({row['id'] for row in rows}) == len(rows)
    for row in rows:
        assert row['target_message_index'] == len(row['messages']) - 1
        assert row['messages'][-1]['role'] == 'assistant'
    (args.output / 'data').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, args.output / 'data/train.jsonl')
    shutil.copyfile(args.source / 'train.manifest.json', args.output / 'manifest.json')
    (args.output / 'README.md').write_text(CARD)
    print(json.dumps({'rows': len(rows), 'jsonl_bytes': source.stat().st_size, 'sha256': digest}))
    if args.upload:
        from huggingface_hub import HfApi, hf_hub_download
        api = HfApi()
        api.create_repo(args.repo_id, repo_type='dataset', private=False, exist_ok=True)
        commit = api.upload_folder(repo_id=args.repo_id, repo_type='dataset', folder_path=args.output,
                                   commit_message='Publish vote-selected AI-Arenaen conversations',
                                   allow_patterns=['README.md', 'manifest.json', 'data/train.jsonl'])
        remote = hf_hub_download(args.repo_id, 'data/train.jsonl', repo_type='dataset', revision=commit.oid)
        assert hashlib.sha256(Path(remote).read_bytes()).hexdigest() == digest
        print(json.dumps({'repo_id': args.repo_id, 'commit': commit.oid, 'verified': True}))


if __name__ == '__main__':
    main()
