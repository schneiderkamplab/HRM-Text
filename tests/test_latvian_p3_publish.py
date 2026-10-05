import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from test_latvian_p3_export import fixture, write
from dfm12 import latvian_p3_export as export
from dfm12 import latvian_p3_publish as m


@pytest.fixture
def publication(fixture):
    f = fixture; root = f['root']; source = root/'audit-ready/latvian-p3/candidates.jsonl'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    with sqlite3.connect(root/'release/latvian-p3/ledger.sqlite') as db:
        for row in rows:
            row['rendered_tokens'] = 5
            db.execute('UPDATE rows SET record=? WHERE id=?', (json.dumps(row), row['id']))
    source.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    receipt = export.load(source.parent/'receipt.json'); receipt['sha256'] = export.file_hash(source)
    tokenizer = root/'tokenizer.json'; tokenizer.write_text('fixture tokenizer')
    template = root/'template.jinja'; template.write_text('fixture template')
    receipt.update(tokenizer_info=dict(tokenizer_path=str(tokenizer), chat_template_path=str(template)),
        tokenizer_sha256=export.file_hash(tokenizer), template_sha256=export.file_hash(template))
    write(source.parent/'receipt.json', receipt)
    export.export(**f)
    output = root.parent/'publication'
    m.build(f['output'], output, renderer=SimpleNamespace(count=lambda messages: 5))
    registry = root.parent/'registry.json'; write(registry, dict(additions=[dict(name='unrelated')]))
    return output, registry


class Remote:
    def __init__(self, root, corrupt=None):
        self.root = root; self.files = {}; self.calls = []; self.corrupt = corrupt; self.uploads = 0

    def create_repo(self, *args, **kwargs): pass

    def upload_folder(self, repo_id, folder_path, allow_patterns, **kwargs):
        self.uploads += 1
        for name in allow_patterns:
            self.files[(repo_id, name)] = (folder_path/name).read_bytes()
        return SimpleNamespace(oid='fixed-'+str(self.uploads))

    def download(self, repo_id, filename, revision, **kwargs):
        self.calls.append((repo_id, filename, revision))
        path = self.root/'remote'; path.write_bytes(
            b'corrupted' if filename == self.corrupt else self.files[(repo_id, filename)])
        return path


def test_all_remote_files_verified_and_tokenizer_eligible(publication):
    from scripts.tokenize_wave_releases import eligible
    output, registry = publication; remote = Remote(output.parent)
    records = m.publish(output, registry, remote, remote.download)
    assert len(records) == 2 and all(eligible(r) for r in records)
    for record in records:
        assert record['rows'] == 2 and record['rendered_tokens'] == 10
        assert record['license'] in m.LICENSES
        assert set(record['remote_verified_files']) == {name for repo, name, _ in remote.calls if repo == record['hf_repo_id']}
        assert 'LICENSE.txt' in record['remote_verified_files']
        assert Path(record['manifest']).is_file()
    config = export.load(registry)
    assert config['additions'][0] == dict(name='unrelated')
    config['additions'][1].update(tokenization_performed=True, tokenized_tokens=10)
    write(registry, config)
    m.publish(output, registry, remote, remote.download)
    assert remote.uploads == 2
    assert export.load(registry)['additions'][1]['tokenized_tokens'] == 10


@pytest.mark.parametrize('filename', ['data/train.jsonl', 'LICENSE.txt', 'NOTICE.txt', 'evidence/arc.txt'])
def test_remote_corruption_never_registers(publication, filename):
    output, registry = publication; before = registry.read_bytes()
    remote = Remote(output.parent, corrupt=filename)
    with pytest.raises(ValueError, match='hash mismatch'):
        m.publish(output, registry, remote, remote.download)
    assert registry.read_bytes() == before
    assert not (output/'integrated.json').exists()


def test_local_license_tampering_blocks_upload(publication):
    output, registry = publication
    (output/m.folder_name('cc-by-4.0')/'LICENSE.txt').write_text('wrong license')
    remote = Remote(output.parent)
    with pytest.raises(ValueError, match='hash mismatch'):
        m.publish(output, registry, remote, remote.download)
    assert remote.uploads == 0


def test_republish_cannot_clear_owner_quality_hold(publication):
    output, registry = publication; remote = Remote(output.parent)
    m.publish(output, registry, remote, remote.download)
    config = export.load(registry)
    for row in config['additions']:
        if row['name'] != 'unrelated': row['status'] = 'quality_hold_source_fidelity'
    write(registry, config); before = registry.read_bytes()
    with pytest.raises(ValueError, match='cannot be cleared'):
        m.publish(output, registry, remote, remote.download)
    assert registry.read_bytes() == before


def test_partial_preparation_not_publishable(fixture):
    export.export(**fixture)
    manifest = export.load(fixture['output']/'manifest.json'); manifest['partial'] = True
    write(fixture['output']/'manifest.json', manifest)
    with pytest.raises(ValueError, match='terminal'):
        m.build(fixture['output'], fixture['root'].parent/'publish')


def test_publication_receipt_consumed_by_wave_assembler(publication, monkeypatch):
    import numpy as np
    from scripts import assemble_dfm13_additions as assembly
    output, registry = publication; remote = Remote(output.parent)
    records = m.publish(output, registry, remote, remote.download)
    info = dict(tokenizer_path=str(output.parent/'source/tokenizer.json'),
        chat_template_path=str(output.parent/'source/template.jinja'),
        enable_thinking=False, template_mode='jinja_chat_template', vocab_size=32)
    contract = assembly.token_contract(info, {})
    monkeypatch.setattr(assembly, 'native_encoder', lambda info:
        lambda row, final_only=True: [([1, 2], [3, 4, 5])])
    for i, entry in enumerate(records):
        root = output.parent/f'tokens-{i}'; part = root/'part-000000.jsonl'; part.mkdir(parents=True)
        for field, values in dict(tokens=[1,2,3,4,5]*2, inst_start=[0,5], inst_len=[2,2],
                                  resp_start=[2,7], resp_len=[3,3]).items():
            np.save(part/(field+'.npy'), np.array(values, dtype=np.uint32))
        write(root/'tokenizer_info.json', info)
        write(root/'completion.json', dict(rows=2, files=1, skipped_rows_this_run=0, max_seq_len=4096))
        write(root/'verified.json', dict(rows=2, tokens=10, output=str(root), pins=dict(
            source_sha256=entry['output_sha256'], tokenizer_sha256=contract['tokenizer_path_sha256'],
            template_sha256=contract['chat_template_path_sha256'])))
        entry.update(tokenization_performed=True, tokenized_path=str(root), tokenization_receipt=str(root/'verified.json'),
                     tokenized_rows=2, tokenized_tokens=10)
        assert assembly.unready_reason(entry) is None
        result = assembly.verify_entry(entry, contract, {})
        assert result['rows'] == 2 and result['tokens'] == 10
