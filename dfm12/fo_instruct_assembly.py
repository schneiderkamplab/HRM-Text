"""Source-fidelity and native token verification for Setur/fo-instruct."""
import json
from pathlib import Path


def unready(entry):
    if (entry.get('name') != 'setur_fo_instruct' or entry.get('repeat') != 10
            or entry.get('status') != 'source_native_tokenized'
            or not entry.get('tokenization_performed')):
        return 'setur_source_not_ready'
    return None


def verify(entry, contract, pins, api):
    from scripts.prepare_dfm13_fo_instruct import convert, REPO, REVISION
    api.require(unready(entry) is None, 'Setur admission not ready')
    api.require(entry['repo_id'] == REPO and entry['revision'] == REVISION
                and entry['license'] == 'cc-by-4.0' and entry['split'] == 'train'
                and entry['hard_truncation'] is False, 'Setur source policy drift')
    raw = api.pin(entry['raw_source'], pins, entry['raw_source_sha256'])
    source = api.pin(entry['output'], pins, entry['output_sha256'])
    api.pin(entry['source_card'], pins, entry['source_card_sha256'])
    expected = [convert(json.loads(line), i) for i, line in enumerate(raw.read_text().splitlines())]
    actual = [json.loads(line) for line in source.read_text().splitlines()]
    api.require(expected == actual and len(actual) == entry['rows'] == 571, 'Setur source/target mismatch')
    root = Path(entry['tokenized_path']).resolve()
    api.require({str(p.resolve()) for p in root.rglob('*') if p.is_file()} == set(entry['token_files']),
                'Setur token inventory mismatch')
    for path, sha in entry['token_files'].items():
        api.pin(path, pins, sha)
    info = api.read_json(root / 'tokenizer_info.json', pins)
    api.require(api.token_contract(info, pins) == contract, 'Setur tokenizer/template mismatch')
    completion = api.read_json(root / 'completion.json', pins)
    api.require(completion['rows'] == len(actual) and not completion['skipped_rows_this_run']
                and completion['max_seq_len'] is None, 'Setur rows dropped/truncated')
    parts = [dict(api.verify_arrays(p, contract['vocab_size'], pins), path=str(p),
                  link_name=entry['name'] + '__' + p.name) for p in sorted(root.iterdir()) if p.is_dir()]
    api.require(sum(p['rows'] for p in parts) == len(actual), 'Setur token row mismatch')
    parity = api.verify_native_sample(source, parts, info, len(actual))
    return dict(name=entry['name'], source=str(source), repeat=10, rows=len(actual),
                tokens=sum(p['tokens'] for p in parts), parts=parts, tokenized_root=str(root),
                native_token_parity=parity, repo_id=REPO, revision=REVISION,
                quality_basis='upstream instruction pairs; not model audited')
