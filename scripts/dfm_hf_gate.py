"""Exact predecessor gate for the corrected HF-only DFM10 chain."""
from pathlib import Path
import hashlib
import json


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_dfm10(queue):
    base = Path(queue) / 'dfm10-hf-v2'
    receipt = json.loads((base / 'verified.json').read_text())
    cfg_path = base / 'hf_recipe.json'
    cfg = json.loads(cfg_path.read_text())
    inputs = json.loads((base / 'inputs-verified.json').read_text())
    tokens = json.loads((base / 'all-token-comparison.json').read_text())
    if (receipt.get('version') != 10 or receipt.get('status') != 'matched'
            or receipt.get('verified_files') != 41
            or receipt.get('input_policy') != 'HF-only plus lexdk/DBC'
            or cfg.get('recipe') != 'dfm10-hf-v2'
            or receipt.get('config_sha256') != digest(cfg_path)
            or inputs.get('config_sha256') != digest(cfg_path)
            or tokens.get('status') != 'matched' or tokens.get('tasks') != 4351):
        raise ValueError('DFM10 exact HF-only verification gate failed')
    if not (base / 'union/tokenizer_info.json').is_file():
        raise ValueError('Verified DFM10 union is missing')
    return {'receipt': str(base / 'verified.json'),
            'receipt_sha256': digest(base / 'verified.json'),
            'config_sha256': digest(cfg_path), 'base_union': str(base / 'union')}
