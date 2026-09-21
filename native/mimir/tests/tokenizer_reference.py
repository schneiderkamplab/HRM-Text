"""Training-faithful tokenizer shared by native HF reference generators."""
import json
from pathlib import Path


__all__ = ['load_training_tokenizer']


def load_training_tokenizer(model: Path):
    from transformers import PreTrainedTokenizerFast
    # Tokenizer.from_file is the training path; AutoTokenizer may rewrite its
    # pre-tokenizer based on flags added by a later HF export.
    config = json.loads((model / 'tokenizer_config.json').read_text())
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_file=str(model / 'tokenizer.json'),
        **{key: config[key] for key in ('bos_token', 'eos_token', 'pad_token', 'unk_token') if config.get(key)},
    )
    tokenizer.chat_template = (model / 'chat_template.jinja').read_text()
    return tokenizer
