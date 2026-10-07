"""Prepare attributed English evidence reservoirs; no model calls or admission."""
from collections import Counter
import json
from pathlib import Path
import typer
from dfm12.io import atomic, digest, file_hash, lock, rows, write_json

app = typer.Typer()


@app.command()
def run(root:Path=Path('data/dfm14/knowledge-pilot-v1')):
    with lock(root / '.lock'):
        accepted = Path('data/mimir_openstax_sft/accepted/openstax_mimir_sft.jsonl')
        passages = Path('data/mimir_openstax_sft/passages/openstax_cc_by_en.jsonl')
        used = {r['provenance']['passage_id'] for r in rows(accepted)}
        counts = Counter()
        books = Counter()
        with atomic(root / 'openstax-unused-passages.jsonl') as output:
            for row in rows(passages):
                counts['openstax_total_passages'] += 1
                if row['passage_id'] in used:
                    counts['openstax_previously_used'] += 1
                    continue
                if row.get('license') != 'CC-BY-4.0' or len(row['passage']) < 250:
                    counts['openstax_held'] += 1
                    continue
                output.write(json.dumps(dict(id=row['passage_id'], language='en', text=row['passage'],
                    provenance=row, training_ready=False),ensure_ascii=False)+'\n')
                counts['openstax_unused_passages'] += 1
                books[row['book_slug']] += 1
        atomic_path = Path('data/dfm14/knowledge-seeds/downloads/data/train-00000-of-00001-1ca58cdaff3335a9.parquet')
        revision = '82293ed322e798dbe2d1509775bce2a2c40c360b'
        metadata = atomic_path.parents[1] / '.cache/huggingface/download/data' / (atomic_path.name + '.metadata')
        if metadata.read_text().splitlines()[0] != revision:
            raise ValueError('ATOMIC source revision changed')
        seen = set()
        with atomic(root / 'atomic-train-relations.jsonl') as output:
            for ordinal, row in enumerate(rows(atomic_path)):
                counts['atomic_input_rows'] += 1
                if not isinstance(row.get('tail'),list):
                    raise ValueError('Unexpected ATOMIC schema')
                tails = sorted({t.strip() for t in row['tail'] if isinstance(t,str) and t.strip().lower() not in ('','none','nan')})
                if not tails:
                    counts['atomic_no_evidence'] += 1
                    continue
                key = digest([row['event'],row['relation'],tails])
                if key in seen:
                    counts['atomic_duplicate'] += 1
                    continue
                seen.add(key)
                output.write(json.dumps(dict(id=key, language='en', event=row['event'], relation=row['relation'],
                    relation_description=row['relation_description'], plausible_completions=tails,
                    provenance=dict(repo='Estwld/atomic2020-origin',revision=revision,split='train',row=ordinal),
                    generation_note='Plausible commonsense relations, not universal facts. Resolve placeholders consistently; do not assert certainty.',
                    training_ready=False),ensure_ascii=False)+'\n')
                counts['atomic_relation_seeds'] += 1
        write_json(root / 'manifest.json', dict(counts=dict(counts), openstax_unused_by_book=dict(books),
            inputs={str(p):file_hash(p) for p in (accepted,passages,atomic_path)},
            accepted_targets=dict(textbook=150000,science=100000,commonsense=100000,explanatory_qa=75000,evidence=25000,math=50000),
            training_ready=False, remaining=['seed selection and coverage caps','English generation calibration',
                'grounded generation','independent semantic audit','inherited and benchmark decontamination']))
        print(json.dumps(dict(counts)),flush=True)


if __name__ == '__main__': app()
