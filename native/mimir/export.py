"""Export a complete F32 or BF16 Mimir GGUF using the pinned native converter and record provenance."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import shutil

__all__ = []


def _sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--outtype", choices=["f32", "bf16"], default="f32")
    parser.add_argument("--model-name", help="Display name embedded in GGUF metadata")
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--reference-gguf", type=Path, help="Optional independently validated export for bit-exact tensor comparison")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    model = args.model.resolve()
    config = json.loads((model / "config.json").read_text())
    if config.get("architectures") != ["HrmTextForCausalLM"] or not config.get("prefix_lm"):
        raise ValueError("Expected a PrefixLM HrmTextForCausalLM checkpoint")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    converter = root / "llama.cpp/convert_hf_to_gguf.py"
    command = [sys.executable, str(converter), str(model), "--outtype", args.outtype]
    if args.model_name:
        command += ["--model-name", args.model_name]
    command += ["--outfile", str(output)]
    if args.verify_existing:
        if not output.is_file():
            raise ValueError("--verify-existing needs an existing export")
        artifact = output
    else:
        if output.exists():
            raise ValueError("Output already exists; choose a new path or --verify-existing")
        temporary = output.with_name(output.name + ".partial")
        if temporary.exists():
            raise ValueError(f"Previous partial export exists: {temporary}")
        subprocess.run(command[:-1] + [str(temporary)], check=True)
        artifact = temporary
    # gguf-py is the pinned converter's public package.
    sys.path.insert(0, str(root / "llama.cpp/gguf-py"))
    import gguf
    reader = gguf.GGUFReader(artifact)
    required = ["tokenizer.ggml.model", "tokenizer.ggml.tokens", "tokenizer.chat_template",
                "tokenizer.ggml.bos_token_id", "tokenizer.ggml.eos_token_id", "hrm_text.hrm.prefix_lm"]
    if any(key not in reader.fields for key in required):
        raise ValueError("Incomplete tokenizer/template/PrefixLM metadata")
    allowed = {gguf.GGMLQuantizationType.F32}
    if args.outtype == "bf16":
        allowed.add(gguf.GGMLQuantizationType.BF16)
    if not reader.tensors or any(tensor.tensor_type not in allowed for tensor in reader.tensors):
        raise ValueError("Unexpected tensor precision for requested output")
    if not any(tensor.name == "hrm.z_l_init" for tensor in reader.tensors):
        raise ValueError("Missing recurrent state vector")
    expected = {"hrm_text.hrm.prefix_lm": True, "tokenizer.ggml.bos_token_id": config['bos_token_id'],
                "tokenizer.ggml.eos_token_id": config['eos_token_id']}
    expected['tokenizer.ggml.pre'] = 'gemma4'
    for key, value in expected.items():
        if reader.fields[key].contents() != value:
            raise ValueError(f'Incorrect metadata: {key}')
    vocab = reader.fields['tokenizer.ggml.tokens'].contents()
    types = reader.fields['tokenizer.ggml.token_type'].contents()
    for byte in range(256):
        index = vocab.index(f'<0x{byte:02X}>')
        if types[index] != gguf.TokenType.BYTE:
            raise ValueError(f'Byte fallback token has incorrect type: {byte}')
    if args.reference_gguf:
        reference = {tensor.name: tensor for tensor in gguf.GGUFReader(args.reference_gguf).tensors}
        for tensor in reader.tensors:
            previous = reference.pop(tensor.name)
            if (tensor.shape != previous.shape).any() or tensor.tensor_type != previous.tensor_type or \
               hashlib.sha256(tensor.data).digest() != hashlib.sha256(previous.data).digest():
                raise ValueError(f'Tensor differs from independent reference: {tensor.name}')
        if reference:
            raise ValueError('Export is missing reference tensors')
    manifest = {"command": command, "format": args.outtype.upper(), "gguf_sha256": _sha256(artifact),
                "bit_exact_reference": str(args.reference_gguf) if args.reference_gguf else None,
                "tensor_count": len(reader.tensors), "bytes": artifact.stat().st_size,
                "llama_revision": subprocess.check_output(["git", "-C", str(root / "llama.cpp"), "rev-parse", "HEAD"], text=True).strip(),
                "source_sha256": {str(path.relative_to(root)): _sha256(path) for path in [converter, root / "llama.cpp/conversion/hrm_text.py", root / "llama.cpp/conversion/base.py", root / 'llama.cpp/convert_hf_to_gguf_update.py']},
                "input_sha256": {path.name: _sha256(path) for path in sorted(model.iterdir()) if path.suffix in {".json", ".jinja", ".safetensors"} or path.name == "LICENSE"}}
    if not args.verify_existing:
        artifact.rename(output)
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.copyfile(model / 'LICENSE', output.with_suffix('.LICENSE'))
    print(f"Verified {len(reader.tensors)} tensors and complete tokenizer/template metadata")


if __name__ == "__main__":
    _main()
