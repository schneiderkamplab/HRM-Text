"""Handle the named book-summary subset explicitly, not as full books."""
from pathlib import Path
from dfm12.io import write_json
from dfm14.prepare import run


if __name__ == '__main__':
    root = Path('data/dfm14/matina-summaries-v1')
    source = dict(repo='MatinaAI/matina_persian_text_corpus', component='matina-book-summaries',
        languages=['fa'], kind='document', patterns=['data_360book.jsonl.gz'],
        field_mapping={'Long_summary':'text','Title':'title'},
        source_description='Secondary book summaries, not original book text; audit factual claims against supplied summary only.')
    manifest = root / 'sources.json'
    write_json(manifest,[source])
    run(root=root,workers=4,download_workers=1,max_files=1,source_gib=1,rows_per_file=10000,
        download_root=Path('data/dfm14/downloads'),curated_supplements=False,source_manifest=manifest)
