"""Prepare approved Dyna/Matina additions and bounded knowledge-pilot sources."""
from pathlib import Path
import typer
from dfm12.io import write_json
from dfm14.catalog import sources
from dfm14.prepare import run as prepare

app=typer.Typer()


def registry():
    result=[s for s in sources() if s['repo'] in {
        'danish-foundation-models/faroese-dynaword','SlayerLab/polish-dynaword',
        'MatinaAI/matina_persian_text_corpus'}]
    # Books and institutional educational sources only, not Matina web/news dumps.
    for s in result:
        if s['repo'].startswith('MatinaAI/'):
            s['patterns']=['chap-sch-books.jsonl.gz','persianBooks_*.jsonl.gz','data_360book.jsonl.gz']
    for repo,patterns,kind,component in [
        ('nvidia/Nemotron-SFT-Science-v2',['syn_mcq.jsonl'],'instruction','science-syn-mcq'),
        ('tokyotech-llm/swallow-math-v2',['stage3-qa/*.jsonl'],'instruction','swallow-stage3-qa'),
        ('allenai/peS2o',['data/v2/train-*.json.gz'],'document','pes2o-evidence'),
        ('allenai/dolmino-mix-1124',['data/stackexchange/*.json.gz'],'document','stackexchange-explanatory'),
    ]:
        source = dict(repo=repo,languages=['en'],kind=kind,component=component,
                      patterns=patterns,generate_transforms=False)
        if component == 'science-syn-mcq':
            source['adapter'] = 'smoltalk_native'
        elif component == 'swallow-stage3-qa':
            source['adapter'] = 'swallow_delimited_qa'
        result.append(source)
    return result


@app.command()
def run(root: Path=Path('data/dfm14/enrichment-v2')):
    manifest=root/'sources.json'; write_json(manifest,registry())
    write_json(root/'pilot-plan.json',dict(status='cpu_preparation',accepted_targets={
        'textbook':150000,'science':100000,'commonsense':100000,'explanatory_qa':75000,
        'evidence':25000,'math':50000},
        local_openstax='data/mimir_openstax_sft/passages/openstax_cc_by_en.jsonl',
        openstax_provenance='data/mimir_openstax_sft/source_manifest.json',
        outstanding=['ATOMIC 2020 training relations','OpenStax uncovered-chapter selection',
                     'Inherited-source deduplication','Source-specific schema/answer-format inspection',
                     'Grounded generation and independent audit'],training_ready=False))
    prepare(root=root,workers=64,download_workers=8,max_files=8,source_gib=8,
            rows_per_file=40000,download_root=Path('data/dfm14/downloads'),
            curated_supplements=False,source_manifest=manifest)


if __name__=='__main__': app()
