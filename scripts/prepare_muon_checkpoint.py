"""Explicit CPU-only AdamATan2 -> Muon migration; never edit the source."""
import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
import torch.distributed.checkpoint as dcp
from torch.distributed.checkpoint.format_utils import _EmptyStateDictLoadPlanner, _load_state_dict
import yaml
from models.muon import matrix_splits


def convert_state(state, momentum=.95, ns_steps=5, scale=1.0):
    counts = {'muon_matrices': 0, 'adamw_auxiliary': 0}
    for name, slots in state['optim']['state'].items():
        parameter = state['model'][name]
        if matrix_splits(name, parameter) is not None:
            slots.pop('exp_avg', None)
            slots.pop('exp_avg_sq')
            slots['momentum_buffer'] = torch.zeros_like(parameter)
            slots['step'].zero_()
            counts['muon_matrices'] += 1
        else:
            # AdamW uses the same first/second moment definitions; retain them.
            counts['adamw_auxiliary'] += 1
        assert 'param_ema' in slots, f'Missing EMA for {name}'
    for group in state['optim']['param_groups']:
        group.update(optimizer_kind='muon_adamw', muon_momentum=momentum,
                     muon_ns_steps=ns_steps, muon_lr_scale=scale)
    return counts


def convert(source, target, tag):
    assert not target.exists(), f'Output already exists: {target}'
    cfg = yaml.safe_load((source / 'all_config.yaml').read_text())
    metadata = json.loads((source / f'checkpoint_state_{tag}.json').read_text())
    assert cfg.get('optimizer', 'adam_atan2') == 'adam_atan2'
    assert metadata['carry_policy'] == 'none'
    partial = target.with_name(target.name + '.partial')
    assert not partial.exists(), f'Inspect incomplete conversion: {partial}'
    state = {}
    _load_state_dict(state, storage_reader=dcp.FileSystemReader(source / f'fsdp2_{tag}'),
                     planner=_EmptyStateDictLoadPlanner(), no_dist=True)
    counts = convert_state(state)
    partial.mkdir(parents=True)
    dcp.save(state, checkpoint_id=partial / f'fsdp2_{tag}', no_dist=True)
    cfg.update(optimizer='muon', muon_momentum=.95, muon_ns_steps=5, muon_lr_scale=1.)
    (partial / 'all_config.yaml').write_text(yaml.safe_dump(cfg))
    shutil.copy2(source / 'train_metadata.yaml', partial / 'train_metadata.yaml')
    metadata['optimizer'] = 'muon'
    (partial / f'checkpoint_state_{tag}.json').write_text(json.dumps(metadata, indent=2) + '\n')
    receipt = dict(source=str(source.resolve()), tag=tag, **counts,
                   weights_ema_cursor_preserved=True, matrix_momentum='zero',
                   auxiliary_moments='preserved', optimizer='muon')
    (partial / 'muon_conversion.json').write_text(json.dumps(receipt, indent=2) + '\n')
    partial.rename(target)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tag', default='step_3800000')
    args = parser.parse_args()
    print(json.dumps(convert(args.source, args.output, args.tag)), flush=True)
