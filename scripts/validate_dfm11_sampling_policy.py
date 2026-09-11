#!/usr/bin/env python3
"""Reject drift in DFM11's inherited DFM10 sampling policy."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def validate():
    base = yaml.safe_load((ROOT / 'data_io/prefix_config_dfm10.yaml').read_text())
    combined = yaml.safe_load((ROOT / 'data_io/prefix_config_dfm11.yaml').read_text())
    inherited = [rule for rule in combined if not rule['prefix'].startswith('dfm11-')]
    if inherited != base:
        raise ValueError('DFM11 inherited rules differ from current DFM10, including order')
    prefixes = [rule['prefix'] for rule in combined]
    if len(prefixes) != len(set(prefixes)):
        raise ValueError('Duplicate DFM11 sampling prefix')
    print('DFM11 policy: exact DFM10 inheritance verified')


if __name__ == '__main__':
    validate()
