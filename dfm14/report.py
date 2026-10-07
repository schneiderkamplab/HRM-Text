"""Write the measured DFM14 CPU handoff inventory, without reading whole corpora."""
from collections import Counter, defaultdict
from pathlib import Path
import typer

from dfm12.io import atomic, load, write_json
from dfm14.catalog import LANGUAGES

app=typer.Typer()


@app.command()
def run(output: Path=Path("docs/reports/dfm14-cpu-ready-20261006.md")):
    roots=[Path("data/dfm14")/r for r in ("cpu-preparation-expanded","curated-supplements","institutional-supplements-v2")]
    prepared=defaultdict(Counter)
    source_counts=defaultdict(Counter)
    for root in roots:
        for p in root.glob("candidates/*/*/receipt.json"):
            r=load(p)
            for language in r["source"]["languages"]:
                if language not in LANGUAGES:
                    continue
                n=r["counts"].get("language:"+language,0)
                kind="instruction" if r["source"]["kind"]=="instruction" else ("wikipedia" if r["source"]["repo"]=="wikimedia/wikipedia" else "supplement")
                prepared[language][kind]+=n
                source_counts[language][r["source"]["repo"]]+=n
    final=load("data/dfm14/gpu-ready/manifest.json")
    ready=load("data/dfm14/gpu-ready/readiness.json")
    generation=load("data/dfm14/generation-calibration-v1/manifest.json")
    result=dict(prepared=dict(prepared),sources=dict(source_counts),audit_rows=final["rows"],
        audit_chunks=len(final["chunks"]),audit_counts=final["languages"],cpu_holds=final["cpu_holds"],
        cross_campaign_duplicates=final["cross_campaign_duplicates"],generation_requests=generation["rows"],readiness=ready["status"])
    write_json(output.with_suffix(".json"),result)
    with atomic(output) as f:
        f.write("# DFM14 CPU Preparation and GPU Handoff\n\n")
        f.write("Status: CPU preparation complete for the instruction/grounding audit campaign and six-family generation calibration. No GPU calls, acceptance, publication, tokenization or training integration are claimed.\n\n")
        f.write("| Language | Instruction/chat candidates | Wikipedia documents | Added grounding rows | Audit-ready chat | Audit-ready transformations |\n|---|---:|---:|---:|---:|---:|\n")
        for l,name in LANGUAGES.items():
            p=prepared[l]; a=final["languages"][l]
            f.write(f"| {name} | {p['instruction']:,} | {p['wikipedia']:,} | {p['supplement']:,} | {a.get('instruction',0):,} | {sum(v for k,v in a.items() if k!='instruction'):,} |\n")
        f.write("\nAdded grounding rows are Wikisource/EUR-Lex documents and EUbookshop paragraph windows; they are not interchangeable document counts. They are bounded samples, not full upstream sizes. All sources remain subject to semantic quality review.\n\n")
        f.write(f"Final audit: **{final['rows']:,} rows in {len(final['chunks']):,} chunks**, at most 500 rows/chunk, eight independent output partitions. Generation calibration: **{generation['rows']:,} requests**, 100 for each of six families in sixteen languages.\n\n")
        f.write("## Source Inventory\n\n| Language | Source | Prepared rows |\n|---|---|---:|\n")
        for l,name in LANGUAGES.items():
            for repo,n in sorted(source_counts[l].items()):
                if n:
                    f.write(f"| {name} | `{repo}` | {n:,} |\n")
        f.write("\n## Remaining Gates\n\n- Run native-language/semantic audit and repair/re-audit; do not train on candidates.\n- Complete inherited and benchmark decontamination before admission.\n- Calibrate synthetic quality before assigning/launching full accepted production quotas.\n- Hindi's Wikisource supplement is especially weak; unresolved transclusions are removed, and Wikipedia remains its substantive grounding pool.\n- Wikisource can contain historical spelling/religious/literary text; source-grounded generation must not present historical assertions as current facts.\n- EUbookshop is reconstructed from tokenized XML and requires spacing/OCR review. Preserve original document/paragraph provenance.\n- Gated/unavailable instruction sources and unsupported schemas remain explicit holds in the original preparation receipts.\n- Separately managed DaLA, parallel-pair production and final release/sampling are not included in this readiness claim.\n\n")
        f.write("## Artifacts\n\n- `data/dfm14/gpu-ready/manifest.json`\n- `data/dfm14/gpu-ready/jobs.tsv`\n- `data/dfm14/gpu-ready/readiness.json`\n- `data/dfm14/generation-calibration-v1/manifest.json`\n- Commands and recovery contract: `dfm14/README.md`.\n")


if __name__=="__main__":
    app()
