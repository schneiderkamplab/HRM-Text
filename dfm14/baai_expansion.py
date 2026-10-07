"""Prepare newly accessible BAAI instructions without overlapping release variants."""
from pathlib import Path

from dfm12.io import write_json
from dfm14.prepare import run


def sources():
    result = [dict(repo="BAAI/Infinity-Instruct", component="infinity-" + config.lower(),
                   kind="instruction", languages=["zh"], language_field="langdetect",
                   patterns=[config + "/train-*.parquet"])
              for config in ("7M", "Gen")]
    result.append(dict(repo="BAAI/IndustryInstruction", component="industry-instruction",
                       kind="instruction", languages=["zh"], language_field="lang",
                       patterns=["*/*_train.jsonl"], explicit_train_suffix="_train.jsonl"))
    return result


if __name__ == "__main__":
    root = Path("data/dfm14/baai-expansion-v1")
    manifest = root / "sources.json"
    write_json(manifest, sources())
    run(root=root, workers=16, download_workers=8, max_files=200,
        source_gib=32, rows_per_file=100000,
        download_root=Path("data/dfm14/downloads"),
        curated_supplements=False, source_manifest=manifest)
