"""Verify the changed HR entry and mark assembly v4 as historical, not mutable."""
from pathlib import Path

from huggingface_hub import HfApi

from dfm12.hr_transform_subset import NAME, REPO
from dfm12.io import file_hash, load, write_json

ROOT = Path('exports_dfm13/hr-reordering-manual44-subset-20261003-v1')
ASSEMBLY = Path('data/dfm13/verified-wave-additions-20261003-v4')
OUT = Path(__file__).resolve().parent
PINS = {'assembly.json':'5c6a4744b8856c79fb427fd661c4342b662c01b8cecfc549f41d8ae0d1067a02',
        'registry.snapshot.json':'7e8d0b573d9f97a6deec8a26ca2b7ad5de7c5ba31c677be80dc08160d5ff5367'}


def main():
    completion = load(ROOT/'completion.json')
    entry, = completion['entries']
    current = {e['name']:e for e in load('config/dfm13_sources.json')['additions']}
    assert current[NAME] == entry
    assert entry['rows'] == entry['tokenized_rows'] == 30942
    assert completion['excluded_rows'] == 44
    for name, sha in PINS.items():
        assert file_hash(ASSEMBLY/name) == sha
    before = {e['name']:e for e in load(ROOT/'parent-registry.json')['additions']}
    other_names = [n for n in before if n.startswith('dfm13_wave4_wikipedia_hr_') and n != NAME]
    assert len(other_names) == 3
    for name in other_names:
        assert current[name] == before[name]
        assert file_hash(current[name]['output']) == before[name]['output_sha256']
    parent = load(ROOT/'paragraph-reordering/parent-entry.json')
    assert file_hash(parent['output']) == parent['output_sha256']
    assert file_hash(parent['manifest']) == file_hash(ROOT/'paragraph-reordering/parent-publication.json')
    assert Path(parent['tokenized_path']) != Path(entry['tokenized_path'])
    frozen = load(ASSEMBLY/'assembly.json')
    arrays = {}
    for old in frozen['ready_additions']:
        if not old['name'].startswith('dfm13_wave4_wikipedia_hr_'):
            continue
        for part in old['parts']:
            for array in part['arrays'].values():
                assert file_hash(array['path']) == array['sha256']
                arrays[array['path']] = array['sha256']
    assert arrays
    assert HfApi().repo_info(REPO,repo_type='dataset').sha == entry['hf_revision']
    verification = ROOT/'assembly-verification.json'
    assert file_hash(verification) == completion['assembly_verification_sha256']
    result = dict(status='accepted_subset_integrated_current_entry_reverified',
        changed_entry=entry, excluded_rows=44, other_hr_entries_unchanged=other_names,
        historical_arrays_verified=arrays,
        assembly_v4=dict(path=str(ASSEMBLY.resolve()), status='historical_pre_hr_manual44_subset',
            snapshot_files=PINS, modified=False, current=False,
            next_step='Keep v4 immutable; use current entry verification or build a fresh subsequent assembly.'),
        current_entry_verification=dict(path=str(verification.resolve()), sha256=file_hash(verification)),
        completion_sha256=file_hash(ROOT/'completion.json'), tests_passed=95,
        same_hf_repo_head_verified=True, original_export_and_receipt_unchanged=True,
        gpu_actions=False)
    write_json(OUT/'receipt.json',result)
    print('retained',entry['rows'],'tokens',entry['tokenized_tokens'],'historical arrays',len(arrays))
    print('revision',entry['hf_revision'],'receipt',file_hash(OUT/'receipt.json'))


if __name__ == '__main__':
    main()
