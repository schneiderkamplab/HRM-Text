import json

from scripts import queue_dfm_hf_rebuild as rebuild


def test_enable_dfm3_preserves_dfm2(tmp_path):
    plan = {'rows': [
        {'version': i, 'status': 'done' if i < 3 else 'pending', 'completed_stages': []}
        for i in range(1, 16)]}
    (tmp_path / 'plan.json').write_text(json.dumps(plan))
    rebuild.enable_dfm3(tmp_path)
    actual = json.loads((tmp_path / 'plan.json').read_text())
    assert actual['rows'][:2] == plan['rows'][:2]
    assert all(r['tokenizer_workers'] == 32 for r in actual['rows'][2:])
    assert actual['rows'][2]['recipe'] == 'dfm3-hf-v1'
    assert actual['rows'][2]['transform_source'] == 'hf-package'
    assert 'compare' in actual['rows'][2]['stages']
    command = rebuild.dfm3_command(tmp_path, 'generate')
    assert any('fetch_historical_dfm_package.py' in arg for arg in command)
    assert '--historical-full-reconstruction' not in command


def test_dfm3_commands_are_isolated(tmp_path):
    generate = rebuild.dfm3_command(tmp_path, 'generate')
    assert generate[generate.index('--max-chars') + 1] == '3000'
    assert '--historical-full-reconstruction' in generate
    assemble = rebuild.dfm3_command(tmp_path, 'assemble')
    assert str(tmp_path / 'dfm1/tokenized') in assemble
    assert str(tmp_path / 'dfm2/tokenized_extra') in assemble
    assert str(tmp_path / 'dfm2/tokenized') not in assemble
    sample = rebuild.dfm3_command(tmp_path, 'sample')
    assert 'epochs=4' in sample
    assert 'concat_workers=1' in sample


def test_historical_generation_preserves_full_targets():
    from scripts.generate_dfm3_common_pile_tasks import make_rows
    text = "An English sentence with several distinct words. " * 60
    short = dict(make_rows(text, 20260531, "example.parquet", 0, 0))
    full = dict(make_rows(text, 20260531, "example.parquet", 0, 0, True))
    assert full.keys() == short.keys()
    for name in full:
        if "continuation" in name:
            assert short[name] == full[name]
        else:
            assert full[name]["response"] == text
            assert len(short[name]["response"]) <= 1390


def test_repair_dfm3_keeps_acquisition_and_conversion(tmp_path):
    (tmp_path / "dfm3").mkdir()
    plan = {"rows": [{"version": 3, "status": "blocked", "error": "mismatch",
                     "completed_stages": ["acquire", "convert", "generate", "tokenize",
                                          "assemble", "sample"]}]}
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    rebuild.repair_dfm2(tmp_path, version=3)
    row = json.loads((tmp_path / "plan.json").read_text())["rows"][0]
    assert row["completed_stages"] == ["acquire", "convert"]
    assert row["status"] == "pending"
