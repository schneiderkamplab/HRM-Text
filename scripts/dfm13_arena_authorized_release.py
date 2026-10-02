"""Explicit user release of validated automated candidates, without manual-gold claims."""
from pathlib import Path
from scripts import dfm13_arena_export_readiness as guard


def validate_release(path, recheck=True):
    release=guard.load(path)
    if not (release.get('user_release_authorized') is True
            and release.get('quality_certified') is False
            and release.get('manual_per_row_verified') is False
            and release.get('diagnostic100_merged') is False
            and release.get('exclude_all_current_holds') is True):
        raise ValueError('Release scope or quality representation mismatch')
    for name,h in release['pins'].items():
        if guard.file_hash(name)!=h:raise ValueError('Release pin drift: '+name)
    count=0;seen=set()
    for entry in release['selections']:
        receipt=guard.load(entry['readiness'])
        if receipt['blocked'] or not receipt['terminal']:
            raise ValueError('Held or nonterminal selection')
        if receipt['status'] not in ('manual_quality_review_required','ready_for_separate_export_authorization'):
            raise ValueError('Unexpected readiness status')
        for name,h in receipt['pins'].items():
            if guard.file_hash(name)!=h:raise ValueError('Readiness pin drift: '+name)
        if not guard.terminal_ready(receipt['ledger']):raise ValueError('Ledger no longer terminal')
        selection=guard.load(receipt['selection'])
        for row in selection['candidates']:
            key=(str(Path(receipt['ledger']).resolve()),row['seq'])
            if key in seen:raise ValueError('Duplicate release row')
            seen.add(key)
        if recheck:
            evidence={}
            findings=guard.check_selection(receipt['ledger'],selection,guard.load(receipt['holds']),evidence)
            if findings or evidence['selection_evidence_sha256']!=receipt['selection_evidence_sha256']:
                raise ValueError('Selection evidence/holds drift')
        count+=len(selection['candidates'])
    if count!=release['total']:raise ValueError('Release total mismatch')
    return release
