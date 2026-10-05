"""Publication-only source holds; never mutate source quality ledgers."""
from pathlib import Path

from .io import file_hash, load, lock, write_json


STATUS = 'quality_hold_source_fidelity'
COMPONENTS = frozenset({
    'ParsiAI--FarsInstruct-fa-pn_sum',
    'ParsiAI--FarsInstruct-fa-wiki_sum',
})
RECEIPT = Path('data/dfm13/wave4/publication-holds/farsinstruct-source-fidelity-20261003.json')
BALTIC_QA_COMPONENTS = frozenset({'baltic_lt_qa', 'baltic_lv_qa'})


def entry_quality_hold(entry):
    """Reject named source holds even when a caller has a stale registry snapshot."""
    names = {'dfm13_wave3_' + c for c in BALTIC_QA_COMPONENTS}
    names.update('dfm13_wave4_' + c.replace('--', '_').replace('-', '_') for c in COMPONENTS)
    return bool(entry.get('name') in names or entry.get('status') == STATUS
                or entry.get('quality_hold'))


def publication_hold(component):
    # Deliberately no receipt-based clearance: deletion/malformed evidence must
    # not silently authorize publication. Clearance requires reviewed code change.
    return STATUS if component in COMPONENTS | BALTIC_QA_COMPONENTS else None


def require_publication_allowed(component):
    if publication_hold(component):
        raise ValueError(f'{STATUS}: {component}; pending independent 31B full-source audit')


def mark_registry(registry=Path('config/dfm13_sources.json'), receipt=RECEIPT):
    """Atomically mark existing uploads, preserving repeat/counts/files/pins."""
    receipt = Path(receipt)
    evidence = load(receipt)
    if set(evidence['components']) != COMPONENTS or evidence['status'] != STATUS:
        raise ValueError('Invalid publication-hold receipt')
    names = {'dfm13_wave4_' + c.replace('--', '_').replace('-', '_') for c in COMPONENTS}
    registry = Path(registry)
    with lock(registry.with_suffix('.lock')):
        data = load(registry)
        changed = []
        for row in data['additions']:
            if row.get('name') not in names:
                continue
            row.setdefault('status_before_source_fidelity_hold', row.get('status'))
            row['status'] = STATUS
            row['quality_hold'] = dict(receipt=str(receipt.resolve()),
                receipt_sha256=file_hash(receipt), scope='entire_source_component',
                admission_authorized=False)
            changed.append(row['name'])
        if changed:
            write_json(registry, data)
        return changed
