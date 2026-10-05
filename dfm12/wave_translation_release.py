"""Publish selected parallel pairs with both directions and source attribution."""
import argparse
import copy
import json
from pathlib import Path
import re

from .baltic_sources_cpu import renderer
from .io import atomic, digest, file_hash, load, lock, rows, write_json
from .jobs import validate_audit


def attribution(origin, folder, files, licenses):
    origin = copy.deepcopy(origin)
    if origin.get('method') == 'exact_english_anchor_join':
        if len(origin.get('legs', [])) != 2:
            raise ValueError('Pivot must retain exactly two source legs')
        origin['legs'] = [attribution(leg, folder, files, licenses) for leg in origin['legs']]
        return origin
    license_id = origin.get('license', '').lower()
    if not re.fullmatch(r'cc-by(?:-sa)?-[234]\.0|cc0-1\.0|public-domain', license_id):
        raise ValueError('Unapproved parallel-source license: ' + license_id)
    source = Path(origin['attribution'])
    sha = file_hash(source)
    evidence = load(source)
    if evidence['entry'].get('status') != 'approved' or evidence['entry']['url'] != origin['url']:
        raise ValueError('Parallel-source attribution mismatch')
    if evidence['entry']['license'].lower() != license_id:
        raise ValueError('Conflicting source license')
    destination = folder / 'attribution' / (sha + '.json')
    if sha not in files:
        with atomic(destination) as out:
            out.write(source.read_text())
        if file_hash(destination) != sha:
            raise ValueError('Attribution copy changed')
        files[sha] = str(destination.relative_to(folder))
    licenses.add(license_id)
    origin['attribution'] = files[sha]
    origin['attribution_sha256'] = sha
    return origin


def card_languages(pair):
    languages = pair.split('-')
    text = 'language: ' + json.dumps(['pt' if x == 'pt_pt' else x for x in languages]) + '\n'
    if 'pt_pt' in languages:
        text += 'language_bcp47: ' + json.dumps(['pt-PT' if x == 'pt_pt' else x for x in languages]) + '\n'
    return text


def release(root, pair, upload=False, render=None):
    directory = root / 'translation-release' / pair
    with lock(directory / '.lock'):
        selection = load(directory / 'receipt.json')
        if not selection['ready'] or selection['pending_components']:
            raise ValueError('Unfinished translation reviews')
        path = Path(selection['path'])
        if file_hash(path) != selection['sha256']:
            raise ValueError('Selected translations changed')
        wave = 'wave3' if root.name == 'baltic' else 'wave4'
        name = f'dfm13-{wave}-opus-{pair}'
        repo = 'schneiderkamplab/' + name
        folder = Path('exports_dfm13') / name
        output = folder / 'data/train.jsonl'
        render = render or renderer()
        files, licenses, count, tokens, pair_count = {}, set(), 0, 0, 0
        with atomic(output) as out:
            for selected in rows(path):
                record, review = selected['record'], selected['review']
                validate_audit(review)
                if not review['keep']:
                    raise ValueError('Nonpositive translation review')
                if {record['language'], record['reverse_language']} != set(pair.split('-')):
                    raise ValueError('Wrong translation pair')
                provenance = attribution(record['provenance'], folder, files, licenses)
                directions = [(record['language'], record['messages']),
                              (record['reverse_language'], record['reverse_messages'])]
                measured = [render.count(messages) for _, messages in directions]
                if sum(measured) != selected['combined_tokens']:
                    raise ValueError('Translation tokenization differs from audited preflight')
                for (language, messages), size in zip(directions, measured):
                    row = dict(id=digest([selected['id'], language]), language=language,
                        task='translation', pair=pair, messages=messages,
                        target_message_index=len(messages) - 1, rendered_tokens=size,
                        provenance=provenance, audit=review, quality_status='accepted',
                        admission_authorized=True, source_pair_id=selected['id'])
                    out.write(json.dumps(row, ensure_ascii=False) + '\n')
                    count += 1
                    tokens += size
                pair_count += 1
        if (not count or pair_count != selection['selected_pairs']
                or tokens != selection['combined_rendered_tokens'] or tokens > selection['token_cap']):
            raise ValueError('Selection totals or shared pair cap mismatch')
        publication = dict(name=name.replace('-', '_'), repo_id=repo, hf_repo_id=repo,
            rows=count, pairs=pair_count, rendered_tokens=tokens, repeat=1,
            output=str(output.resolve()), output_sha256=file_hash(output),
            selection_sha256=selection['sha256'], token_cap=selection['token_cap'],
            attribution_files=files, licenses=sorted(licenses), tokenization_performed=False,
            uploaded=False, target_policy='final_assistant_only_native_gemma')
        write_json(folder / 'manifest.json', publication)
        with atomic(folder / 'README.md') as out:
            out.write('---\nlicense: other\nlicense_name: source-specific-opus-terms\n'
                f'license_link: https://huggingface.co/datasets/{repo}/blob/main/README.md#source-terms\n'
                + card_languages(pair) +
                'task_categories:\n- translation\nconfigs:\n- config_name: default\n'
                '  data_files:\n  - split: train\n    path: data/train.jsonl\n---\n\n'
                f'# {name}\n\n{count} accepted conversations ({pair_count} bilingual pairs), '
                'including both directions. Every pair passed automated Gemma 4 review; '
                'automated review is fallible. Direct and exact-English-pivot routes share '
                'one token cap and are deduplicated before export.\n\n'
                'Render messages with the native Gemma 4 template, thinking disabled; '
                'supervise target_message_index only. No benchmark decontamination claim.\n\n'
                '## Source terms\n\nNo blanket relicensing is asserted. Per-row provenance '
                'identifies the original corpus, version, URL and license. The attribution '
                'directory bundles the original retrieved README/license evidence. Pivot '
                'rows retain both source legs and their English anchor. Observed source '
                'licenses: ' + ', '.join(sorted(licenses)) + '.\n')
        if upload:
            from huggingface_hub import HfApi, hf_hub_download
            api = HfApi()
            api.create_repo(repo, repo_type='dataset', exist_ok=True)
            commit = api.upload_folder(repo_id=repo, repo_type='dataset', folder_path=folder,
                allow_patterns=['README.md', 'manifest.json', 'data/*.jsonl', 'attribution/*.json'],
                commit_message='Publish audited bidirectional translations with source attribution')
            remote = hf_hub_download(repo, 'data/train.jsonl', repo_type='dataset', revision=commit.oid)
            if file_hash(remote) != publication['output_sha256']:
                raise ValueError('Remote translation bytes differ')
            for sha, relative in files.items():
                remote_attribution = hf_hub_download(repo, relative, repo_type='dataset', revision=commit.oid)
                if file_hash(remote_attribution) != sha:
                    raise ValueError('Remote attribution bytes differ')
            publication.update(uploaded=True, hf_revision=commit.oid, status='accepted_uploaded')
            registry = Path('config/dfm13_sources.json')
            with lock(registry.with_suffix('.lock')):
                data = load(registry)
                data['additions'] = [r for r in data['additions'] if r['name'] != publication['name']]
                data['additions'].append(dict(publication,
                    manifest=str((directory / 'publication.json').resolve())))
                write_json(registry, data)
        write_json(directory / 'publication.json', publication)
        print(json.dumps(publication), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/dfm13/baltic'))
    parser.add_argument('--pair', required=True)
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    release(args.root, args.pair, args.upload)
