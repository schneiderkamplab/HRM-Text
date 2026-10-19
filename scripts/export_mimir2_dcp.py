"""CPU-only strict EMA export into the companion Mimir2 Transformers model."""
import argparse
import json
from pathlib import Path
import shutil

import torch
import torch.distributed.checkpoint as dcp
import yaml
from transformers import AutoTokenizer
from transformers.models.mimir2.convert_mimir2_weights_to_hf import convert_checkpoint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tokenizer-reference', type=Path,
                        help='Production export whose effective tokenizer pipeline must be materialized')
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f'Refusing existing output: {args.output}')
    cfg = yaml.safe_load((args.checkpoint / 'all_config.yaml').read_text())
    meta = yaml.safe_load((args.checkpoint / 'train_metadata.yaml').read_text())
    if meta['tokenizer_info'].get('template_mode') == 'jinja_chat_template' and args.tokenizer_reference is None:
        raise RuntimeError('Gemma export requires --tokenizer-reference from the production converter')
    reader = dcp.FileSystemReader(args.checkpoint / f'fsdp2_{args.tag}')
    entries = reader.read_metadata().state_dict_metadata
    sources = {}
    for key, value in entries.items():
        if not key.startswith('model.'):
            continue
        name = key.removeprefix('model.')
        ema = f'optim.state.{name}.param_ema'
        source = ema if ema in entries else key
        if name.endswith('.weight') and source == key:
            raise RuntimeError(f'Missing EMA parameter: {name}')
        sources[name] = source
    tensors = {key: torch.empty(entries[key].size, dtype=entries[key].properties.dtype)
               for key in sources.values()}
    dcp.load(tensors, storage_reader=reader, no_dist=True)
    state = {name: tensors[source].to(torch.bfloat16) for name, source in sources.items()}
    # v1's H initial state is a nonpersistent zero placeholder, not a learned state.
    if 'model.zH_init' in state:
        if torch.count_nonzero(state['model.zH_init']):
            raise RuntimeError('Nonzero v1 H initializer cannot be discarded')
        del state['model.zH_init']
    native = cfg['arch'] | {k: meta[k] for k in ('vocab_size', 'max_seq_len')}
    model = convert_checkpoint(state, native)
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_reference or meta['tokenizer_info']['tokenizer_path'], fix_mistral_regex=True)
    if meta['tokenizer_info'].get('template_mode') == 'jinja_chat_template':
        tokenizer.init_kwargs['fix_mistral_regex'] = True
        for field, token in (('bos_token', '<bos>'), ('eos_token', '<turn|>'), ('pad_token', '<pad>')):
            if token not in tokenizer.get_vocab():
                raise RuntimeError(f'Missing required Gemma token: {token}')
            setattr(tokenizer, field, token)
    template = meta['tokenizer_info'].get('chat_template_path')
    if template:
        tokenizer.chat_template = Path(template).read_text()
    for target in (model.config, model.generation_config):
        for key in ('bos_token_id', 'eos_token_id', 'pad_token_id'):
            setattr(target, key, getattr(tokenizer, key))
    temp = args.output.with_name(args.output.name + '.partial')
    if temp.exists():
        raise RuntimeError(f'Inspect incomplete export before retry: {temp}')
    model.save_pretrained(temp)
    tokenizer.save_pretrained(temp)
    reloaded = AutoTokenizer.from_pretrained(temp, fix_mistral_regex=True)
    if tokenizer.backend_tokenizer.pre_tokenizer.__getstate__() != reloaded.backend_tokenizer.pre_tokenizer.__getstate__():
        raise RuntimeError('Tokenizer preprocessing changed across export/reload')
    shutil.copy2(args.checkpoint / f'checkpoint_state_{args.tag}.json', temp / 'native_checkpoint_state.json')
    (temp / 'export_receipt.json').write_text(json.dumps({
        'checkpoint': str(args.checkpoint), 'tag': args.tag, 'ema': True,
        'ema_tensors': sum(s.startswith('optim.') for s in sources.values()),
        'model_tensors': len(state), 'dtype': 'bfloat16',
        'tokenizer_reference': str(args.tokenizer_reference) if args.tokenizer_reference else None,
    }, indent=2) + '\n')
    temp.rename(args.output)
    print(args.output, flush=True)


if __name__ == '__main__':
    main()
