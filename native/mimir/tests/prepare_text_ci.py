"""Prepare a small vocabulary-only GGUF for text parity CI, without model weights."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

__all__ = []


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Use existing local tokenizer files instead of downloading')
    parser.add_argument('--output', type=Path, default=Path('logs/mimir-text-ci'))
    args = parser.parse_args()
    model = args.output / 'tokenizer'
    model.mkdir(parents=True, exist_ok=True)
    names = ['config.json', 'tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja', 'LICENSE']
    if args.source:
        for name in names:
            shutil.copyfile(args.source / name, model / name)
    else:
        from huggingface_hub import snapshot_download
        snapshot_download('danish-foundation-models/DFM-Mimir',
                          revision='2844f0178e695d7d9ce182cb660671fd34c76ce5',
                          allow_patterns=names, local_dir=model)
    root = Path(__file__).resolve().parents[3]
    subprocess.run([sys.executable, str(root / 'llama.cpp/convert_hf_to_gguf.py'), str(model),
                    '--outtype', 'f32', '--vocab-only', '--outfile', str(args.output / 'vocab.gguf')], check=True)
    subprocess.run([sys.executable, str(Path(__file__).with_name('text_reference.py')), '--model', str(model),
                    '--output', str(args.output / 'reference.json')], check=True)


if __name__ == '__main__':
    _main()
