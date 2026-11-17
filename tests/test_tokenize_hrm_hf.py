import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts.tokenize_hrm_hf import DTYPES, process_file

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("extension", ["parquet", "jsonl"])
def test_rust_parity_and_resume(tmp_path, extension):
    binary = ROOT / "data_io/tokenizer/target/release/tokenizer"
    tokenizer = ROOT / "data_io/trained_tokenizers/bpe/tokenizer.json"
    if not binary.exists() or not tokenizer.exists():
        pytest.skip("Historical binary/tokenizer required for integration parity")
    source = tmp_path / "source"
    source.mkdir()
    path = source / f"examples.{extension}"
    rows = [
        dict(condition=c, instruction=i, response=r)
        for c, i, r in [
            ("direct", "", ""),
            ("cot,direct", "  Danish: æøå\n中文 <|im_end|>", "42\n"),
            ("synth", "Hello", "<|box_end|> special token literal"),
            ("noisy", "a\u0000b", "   response   "),
        ]
    ]
    if extension == "parquet":
        pq.write_table(pa.Table.from_pylist(rows), path)
    else:
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    rust = tmp_path / "rust"
    subprocess.run([str(binary), str(source), "--tokenizer-path", str(tokenizer),
                    "--workers", "1", "-o", str(rust)], check=True)
    out = tmp_path / "hf" / path.name
    job = (str(path), str(out), str(tokenizer), hashlib.sha256(tokenizer.read_bytes()).hexdigest())
    assert process_file(job)[1] == 4
    for key in DTYPES:
        actual = np.load(out / f"{key}.npy")
        expected = np.load(rust / path.name / f"{key}.npy")
        assert actual.dtype == expected.dtype
        np.testing.assert_array_equal(actual, expected)
    assert process_file(job)[1] == "cached"
    (out / "hf_receipt.json").unlink()
    (out / "tokens.npy").write_bytes(b"incomplete")
    assert process_file(job)[1] == 4
    assert json.loads((out / "metadata.json").read_text())["source_size"] == path.stat().st_size
