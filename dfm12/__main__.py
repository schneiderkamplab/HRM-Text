"""Run with python -m dfm12. No training, evaluation or final sampling commands."""
from pathlib import Path
import json
import subprocess
import sys
import typer

from . import catalog, identity, opus, prepare
from .io import load, lock, rows, Seen, write_json
from .jobs import Queue, run_clients
from .records import chat_fingerprint, validate_messages
from .pilot import require_pilot
from .budgets import opus_budget

app = typer.Typer(no_args_is_help=True)
ROOT = Path(__file__).resolve().parents[1]


def echo(value):
    typer.echo(json.dumps(value, indent=2, ensure_ascii=False))


@app.callback()
def main(ctx: typer.Context, root: Path = Path("data/dfm12"),
         config: Path = catalog.DEFAULT_CONFIG,
         tokenizer_metadata: Path = Path("data/sampled_dfm11/metadata.json")):
    ctx.obj = dict(root=root.resolve(), cfg=catalog.config(config), metadata=tokenizer_metadata)


def renderer(ctx):
    metadata = load(ctx.obj["metadata"])
    info = metadata.get("tokenizer_info", metadata)
    if info.get("enable_thinking"):
        raise ValueError("DFM12 preparation expects the non-thinking training template")
    return prepare.Renderer(info, ctx.obj["cfg"]["max_seq_len"])


@app.command()
def inventory(ctx: typer.Context):
    """Resolve exact HF revisions and file lists; retain review/access blockers."""
    result = catalog.resolve(ctx.obj["root"], ctx.obj["cfg"])
    echo({n: {"status": s["status"], "files": len(s.get("files", []))} for n, s in result["sources"].items()})


@app.command()
def download(ctx: typer.Context, source: str):
    """Download one approved source, never an unreviewed whole collection."""
    echo(catalog.download(ctx.obj["root"], source))


@app.command()
def approve(ctx: typer.Context, source: str, evidence: str, files: list[str] = typer.Option(..., "--file")):
    """Record an explicitly reviewed subset. Evidence must document the review."""
    root = ctx.obj["root"]
    entry = load(root / "sources.lock.json")["sources"][source]
    if not files or not set(files) <= set(entry.get("files", [])) or len(evidence.strip()) < 20:
        raise ValueError("Supply explicit locked file names and substantive review evidence")
    with lock(root / ".catalog.lock"):
        write_json(root / "approvals" / f"{source}.json",
                   dict(revision=entry["revision"], evidence=evidence, files=files))


@app.command()
def convert(ctx: typer.Context, source: str, exclude_index: Path | None = None, limit: int | None = None):
    """Convert and length-check a source into unaudited candidates."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    echo(prepare.convert_source(ctx.obj["root"], source, renderer(ctx), exclude_index, limit))


@app.command()
def fingerprint_index(output: Path, inputs: list[Path] = typer.Option(..., "--input")):
    """Index inherited or held-out conversations for exact-content exclusion."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with lock(output.with_suffix(".lock")):
        seen = Seen(output)
        count = 0
        try:
            for path in inputs:
                for row in rows(path):
                    validate_messages(row.get("messages"))
                    count += seen.add(chat_fingerprint(row["messages"]))
        finally:
            seen.close()
    echo(dict(added=count, output=str(output)))


@app.command()
def baselines(ctx: typer.Context, accepted_root: Path):
    """Measure unique accepted Danish rows; use the full inherited accepted root."""
    report = prepare.transformation_baseline(accepted_root, ctx.obj["cfg"])
    write_json(ctx.obj["root"] / "baselines.json", report)
    echo(report)


@app.command()
def transformations(ctx: typer.Context, source: str, candidate_factor: float = 1.5):
    """Broadly sample approved DynaWord files and prepare four task candidates."""
    if candidate_factor < 1:
        raise ValueError("candidate_factor must allow enough candidates for the accepted target")
    root = ctx.obj["root"]
    echo(prepare.prepare_transforms(root, source, load(root / "baselines.json"), ctx.obj["cfg"], renderer(ctx), candidate_factor))


@app.command()
def identity_jobs(ctx: typer.Context, profile: str = "xl-full-bp", count: int = 20, start: int = 0):
    """Prepare generation requests; extra candidates allow rejection/deduplication."""
    if count < 1 or start < 0:
        raise ValueError("Invalid request range")
    if count > 20 or start:
        require_pilot(ctx.obj["root"], ctx.obj["cfg"])
    queue = Queue(ctx.obj["root"] / "jobs.sqlite")
    try:
        for request in identity.requests(ctx.obj["cfg"], profile, count, start):
            queue.add("generate", request)
        echo(queue.status())
    finally:
        queue.close()


@app.command()
def audit_jobs(ctx: typer.Context, component: str, limit: int | None = None):
    """Enqueue candidates; --limit 100 is useful for the initial language pilot."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    if limit is None or limit > 100:
        require_pilot(ctx.obj["root"], ctx.obj["cfg"])
    echo(dict(enqueued=prepare.enqueue_candidates(ctx.obj["root"], component, ctx.obj["cfg"]["model"], limit)))


@app.command()
def identity_audits(ctx: typer.Context):
    """Enqueue independent audits of completed, renderable identity generations."""
    echo(dict(enqueued=prepare.generated_to_audit(ctx.obj["root"], renderer(ctx), ctx.obj["cfg"]["model"])))


@app.command()
def work(ctx: typer.Context, stage: str, endpoints: list[str] = typer.Option(..., "--endpoint"), concurrency: int = 32):
    """Use explicit OpenAI-compatible /v1 endpoints; starts no servers."""
    if stage not in {"generate", "audit"}:
        raise ValueError("stage must be generate or audit")
    run_clients(ctx.obj["root"] / "jobs.sqlite", stage, endpoints, concurrency)


@app.command()
def status(ctx: typer.Context):
    """Summarize source blockers, queued work and built components."""
    root = ctx.obj["root"]
    result = dict(final_sampling="not requested; DFM12 remains open for other additions")
    if (root / "sources.lock.json").exists():
        result["sources"] = {n: {k: e[k] for k in ("status", "revision", "review", "error") if k in e}
                             for n, e in load(root / "sources.lock.json")["sources"].items()}
    if (root / "jobs.sqlite").exists():
        queue = Queue(root / "jobs.sqlite")
        result["jobs"] = queue.status()
        queue.close()
    result["accepted_components"] = [str(p.parent.parent) for p in root.glob("accepted/*/metadata/manifest.json")]
    echo(result)


@app.command()
def export(ctx: typer.Context, component: str):
    """Build an immutable accepted component, NOT the final DFM12 corpus."""
    root = ctx.obj["root"]
    baseline = load(root / "baselines.json") if (root / "baselines.json").exists() else None
    echo(prepare.export_accepted(root, component, renderer(ctx), ctx.obj["cfg"], baseline))


@app.command()
def tokenize(ctx: typer.Context, component: str, workers: int = 16):
    """Tokenize one accepted component only; never sample the full mix."""
    if not 1 <= workers <= 16:
        raise ValueError("Use at most 16 tokenizer workers")
    root = ctx.obj["root"]
    accepted = root / "accepted" / component
    manifest = load(accepted / "metadata" / "manifest.json")
    info = manifest["tokenizer_info"]
    subprocess.run([sys.executable, str(ROOT / "scripts/tokenize_chat_template.py"), str(accepted),
                    "--tokenizer-path", info["tokenizer_path"], "--chat-template", info["chat_template_path"],
                    "--output-dir", str(root / "tokenized" / component), "--workers", str(workers),
                    "--max-seq-len", str(ctx.obj["cfg"]["max_seq_len"])], check=True, cwd=ROOT)


@app.command()
def opus_inventory(ctx: typer.Context):
    """Discover all 33 requested direct language pairs and record license holds."""
    result = opus.discover(ctx.obj["root"], ctx.obj["cfg"])
    echo({pair: {"corpora": len(item["corpora"]),
                 "approved": sum(c.get("status") == "approved" for c in item["corpora"]),
                 "error": item.get("error")} for pair, item in result["pairs"].items()})


@app.command()
def opus_pair(ctx: typer.Context, pair: str):
    """Prepare paired-direction audit records from approved direct corpora."""
    echo(opus.prepare_pair(ctx.obj["root"], pair, ctx.obj["cfg"], renderer(ctx)))


@app.command()
def translation_budget(ctx: typer.Context, sampling_report: Path):
    """Record future token caps from a real inherited sampler report, not row counts."""
    result = opus_budget(sampling_report, ctx.obj["cfg"])
    write_json(ctx.obj["root"] / "translation-budget.json", result)
    echo(result)


if __name__ == "__main__":
    app()
