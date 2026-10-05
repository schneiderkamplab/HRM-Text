"""Metadata-only attachment backfill for already published SR manual exclusions."""
import argparse
from pathlib import Path
import shutil
import sqlite3

from .io import file_hash, load, lock, write_json
from .sr_manual_exclusion import publication_evidence

TASKS = ('denoising','paragraph-reordering','prefix-continuation','span-filling')
ROOT = Path('data/dfm13/wave4')
REGISTRY = Path('config/dfm13_sources.json')


def backfill(output, api=None, download=None):
    if api is None or download is None:
        from huggingface_hub import HfApi, hf_hub_download
        api = api or HfApi()
        download = download or hf_hub_download
    output = Path(output).resolve()
    ledger = ROOT/'release/wikipedia-sr'
    with lock(ledger/'.lock'):
        status = load(ledger/'status.json')
        if not status['terminal'] or not status['export_ready'] or status['counts'].get('excluded_manual_review') != 4:
            raise ValueError('SR is not terminal with four manual exclusions')
        for task in TASKS:
            stage = output/task
            publication_path = ledger/task/'publication.json'
            publication = load(publication_path)
            source = Path(publication['output']); canonical = source.parent.parent
            parent_path = stage/'parent-publication.json'
            if not parent_path.exists():
                if not publication.get('uploaded') or file_hash(source) != publication['output_sha256']:
                    raise ValueError('Parent publication/data unavailable')
                write_json(parent_path,publication)
                shutil.copyfile(canonical/'manifest.json',stage/'parent-export-manifest.json')
                shutil.copyfile(canonical/'README.md',stage/'parent-README.md')
            parent = load(parent_path)
            if file_hash(source) != parent['output_sha256']:
                raise ValueError('Never rewrite changed published data')
            with sqlite3.connect((ledger/'ledger.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
                attachments = publication_evidence(db, stage)
            prepared = dict(load(stage/'parent-export-manifest.json'), attribution_files=attachments,
                manual_review_evidence_backfilled=True, metadata_parent_revision=parent['hf_revision'])
            write_json(stage/'manifest.json',prepared)
            text = (stage/'parent-README.md').read_text()
            text += ('\n\n## Manual-review evidence (2026-10-03)\n\n'
                'This metadata-only revision adds `manual-review-decisions.json`; training data and token arrays are unchanged. '
                'Before publication, main-agent review excluded exactly four component-level IDs (cases32,36,37,47), '
                'separately from model rejection. The attachment preserves original records/model reviews, reasons and hash-bound provenance. '
                'Case45 remains accepted: meaningful Serbian introduction, cast table and coherent gap answer; '
                'wiki-table markers or an empty heading alone are insufficient for exclusion. No population regex or source-wide hold was applied. '
                'Source license and attribution conditions above remain unchanged.\n')
            (stage/'README.md').write_text(text)
            files = {name:file_hash(stage/name) for name in ('README.md','manifest.json','manual-review-decisions.json')}
            upload_path = stage/'upload.json'
            if upload_path.exists():
                uploaded = load(upload_path)
                if uploaded['files'] != files:
                    raise ValueError('Prepared metadata changed after upload')
            else:
                current = api.repo_info(parent['hf_repo_id'],repo_type='dataset').sha
                if current != parent['hf_revision']:
                    raise ValueError('Remote parent changed; do not overwrite')
                commit = api.upload_folder(repo_id=parent['hf_repo_id'],repo_type='dataset',folder_path=str(stage),
                    allow_patterns=list(files),parent_commit=current,
                    commit_message='Attach exact manual-review exclusion evidence; data and tokens unchanged')
                uploaded = dict(hf_revision=commit.oid,files=files,parent_revision=current)
                write_json(upload_path,uploaded)
            remote_files = dict(files, **{'data/train.jsonl':parent['output_sha256']})
            for relative, sha in remote_files.items():
                remote = download(parent['hf_repo_id'],relative,repo_type='dataset',revision=uploaded['hf_revision'])
                if file_hash(remote) != sha:
                    raise ValueError('Remote metadata/data hash mismatch: '+relative)
            # Canonical metadata changes only after all remote hashes verify.
            for relative in files:
                if relative.endswith('.json'):
                    write_json(canonical/relative,load(stage/relative))
                else:
                    from .io import atomic
                    with atomic(canonical/relative) as handle:
                        handle.write((stage/relative).read_text())
            updated = dict(parent, attribution_files=attachments, manual_review_evidence_backfilled=True,
                metadata_parent_revision=parent['hf_revision'], hf_revision=uploaded['hf_revision'])
            with lock(REGISTRY.with_suffix('.lock')):
                registry = load(REGISTRY)
                entry = next(e for e in registry['additions'] if e['name']==parent['name'])
                if entry['output_sha256'] != parent['output_sha256'] or entry['hf_revision'] not in (parent['hf_revision'],uploaded['hf_revision']):
                    raise ValueError('Registry revision/data changed; preserve concurrent edits')
                # Preserve concurrent CPU-tokenizer fields; only metadata changes.
                entry.update(attribution_files=attachments,manual_review_evidence_backfilled=True,
                    metadata_parent_revision=parent['hf_revision'],hf_revision=uploaded['hf_revision'])
                if 'manifest_sha256' in entry:
                    entry['manifest_sha256'] = None
                if 'export_manifest_sha256' in entry:
                    entry['export_manifest_sha256'] = file_hash(canonical/'manifest.json')
                write_json(publication_path,updated)
                if 'manifest_sha256' in entry:
                    entry['manifest_sha256'] = file_hash(publication_path)
                write_json(REGISTRY,registry)
            write_json(stage/'verified.json',dict(status='metadata_verified', hf_revision=uploaded['hf_revision'],
                parent_revision=parent['hf_revision'], unchanged_data_sha256=parent['output_sha256'],
                remote_verified_files=remote_files, publication_sha256=file_hash(publication_path)))
            print(task,uploaded['hf_revision'],'data unchanged',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    backfill(args.output)
