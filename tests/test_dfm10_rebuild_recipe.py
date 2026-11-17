import json
import subprocess

import pytest

from scripts import rebuild_dfm10 as recipe10
from scripts import queue_dfm_hf_rebuild as queue


def test_dfm10_sample_epochs_match_history():
    assert queue.SAMPLE_EPOCHS[10] == 10
    assert queue.SAMPLE_EPOCHS[9] == 10


def test_dfm10_stage_gates_and_argv(tmp_path, monkeypatch):
    root = tmp_path / 'root'
    (root / 'config/data').mkdir(parents=True)
    (root / 'scripts').mkdir()
    (root / 'scripts/rebuild_dfm10.py').write_text('# stub\n')
    shutil = __import__('shutil')
    shutil.copyfile(recipe10.ROOT / 'data_io/prefix_config_dfm10.yaml',
                    root / 'data_io_prefix.yaml')
    (root / 'data_io').mkdir()
    shutil.move(str(root / 'data_io_prefix.yaml'), str(root / 'data_io/prefix_config_dfm10.yaml'))
    import hashlib
    config = dict(version=10, epochs=10,
                  prefix_config_sha256=hashlib.sha256(
                      (root / 'data_io/prefix_config_dfm10.yaml').read_bytes()).hexdigest(),
                  composition=dict(addition_tasks=4351, base_tasks=11395, total_tasks=15748))
    (root / 'config/data/dfm10_hf_rebuild.json').write_text(json.dumps(config))
    monkeypatch.setattr(queue, 'ROOT', root)
    work = tmp_path / 'dfm10'
    work.mkdir()
    (work / 'all-token-comparison.json').write_text('{"status":"mismatch"}')
    with pytest.raises(ValueError, match='must match'):
        queue.dfm10_command(tmp_path, 'sample')
    (work / 'all-token-comparison.json').write_text('{"status":"matched"}')
    (work / 'prefix_config.yaml').write_text('tampered')
    with pytest.raises(ValueError, match='sampling policy'):
        queue.dfm10_command(tmp_path, 'sample')
    shutil.copyfile(root / 'data_io/prefix_config_dfm10.yaml', work / 'prefix_config.yaml')
    cmd = queue.dfm10_command(tmp_path, 'sample')
    joined = ' '.join(cmd)
    assert 'sample_tokenized.py' in joined
    assert f'tokenized_path={work / "union"}' in joined
    assert 'epochs=10' in joined and 'seed=0' in joined and 'concat_workers=4' in joined
    with pytest.raises(ValueError, match='Unknown DFM10 stage'):
        queue.dfm10_command(tmp_path, 'verify-rows')
    for stage in ('prepare', 'tokenize', 'assemble', 'verify'):
        argv = queue.dfm10_command(tmp_path, stage)
        assert argv[2:4] == [stage, '--work']
        assert argv[1].endswith('scripts/rebuild_dfm10.py')


def test_dfm10_component_flags_match_committed_builder():
    builder = subprocess.check_output(
        ['git', 'show', recipe10.BUILDER_REVISION
         + ':scripts/build_tokenized_dfm10_tree.py'], cwd=recipe10.ROOT).decode()
    manifest = json.loads((recipe10.MANIFEST).read_text())
    labels = [k for k in manifest['task_counts'] if k not in ('dfm9', 'output')]
    assert set(labels) == set(recipe10.LABEL_TO_FLAG)
    for label, flag in recipe10.LABEL_TO_FLAG.items():
        assert f'"--{flag}"' in builder or f"'--{flag}'" in builder, flag
    assert manifest['replacement_sources'] == {
        'nemotron_terminal_corpus__': 'nemotron_terminal_native',
        'dolci_instruct_sft_tool_use__': 'dolci_tool_use_repaired',
        'dolci_instruct_sft_tool_use_sa__': 'dolci_tool_use_repaired',
        'dolci_native_tool_use__': 'dolci_tool_use_repaired'}


def test_dfm10_recipe_constants():
    assert recipe10.ADAPTER_REVISION == 'cd88c93'
    assert recipe10.NATIVE_ADAPTER_REVISION == 'ccbb215'
    assert recipe10.BUILDER_REVISION == 'ccbb215'
    assert recipe10.DATA_IO_REVISION == '1f52b10'
    assert len(recipe10.REPLACED_BASE_PREFIXES) == 4
    assert recipe10.NATIVE_MAX_SEQ_LEN == 4096
    fallback = recipe10.ROOT / recipe10.FALLBACK_SOURCES[
        'sapient_scibench_repaired__train.parquet']
    assert fallback.is_file() and fallback.stat().st_size == 117679
    gate = recipe10.ROOT / 'data/tokenized_dfm10_dst_table_prompts_repaired/production_gate.json'
    assert gate.is_file()


def test_dfm10_enable_requires_dfm9_receipt(tmp_path):
    (tmp_path / 'dfm10').mkdir()
    with pytest.raises(Exception):
        queue.enable_dfm10(tmp_path)


def test_missing_danish_charter_manifest_entry_uses_existing_fallback():
    assert recipe10.component_tree_name({}, 'dfm10_synthetic_values_model_charter_da') == 'data/tokenized_dfm10_synthetic_values_model_charter_da'.split('/')[-1]
    assert recipe10.component_tree_name({'alexandra':'data/tokenized_dfm10_alexandra'}, 'alexandra') == 'tokenized_dfm10_alexandra'
    with pytest.raises(ValueError, match='Missing component path'):
        recipe10.component_tree_name({}, 'unknown')


def test_queue_through_does_not_start_next_version(tmp_path):
    (tmp_path/'runner.lock').touch()
    plan={'rows':[{'version':10,'status':'done'}, {'version':11,'status':'pending'}]}
    (tmp_path/'plan.json').write_text(json.dumps(plan))
    queue.run(tmp_path,through=10)
    assert json.loads((tmp_path/'plan.json').read_text())==plan


def test_assembly_resumes_existing_component_with_missing_manifest_entry(tmp_path, monkeypatch):
    work=tmp_path/'work';work.mkdir()
    label='dfm10_synthetic_values_model_charter_da';name='charter.jsonl'
    for mode in ('tokenized','tokenized_native'):
        (work/mode).mkdir();(work/mode/'tokenizer_info.json').write_text('{}')
    (work/'tokenized'/name).mkdir()
    component=work/'components'/recipe10.component_tree_name({},label)
    component.mkdir(parents=True)
    ref=tmp_path/'reference';(ref/name).mkdir(parents=True)
    cfg={'tokenizer_info':{},'tasks':[{'task':name,'component':label,'native':False}],
         'composition':{'base_tasks':0,'addition_tasks':1,'total_tasks':1}}
    monkeypatch.setattr(recipe10,'check_config',lambda _:cfg)
    monkeypatch.setattr(recipe10,'component_tasks',lambda:({},[label],{}))
    monkeypatch.setattr(recipe10,'roots',lambda _:[work])
    monkeypatch.setattr(recipe10,'REFERENCE',ref)
    calls=[]
    def builder(argv,**kwargs):
        calls.append(argv);(work/'union'/name).mkdir(parents=True)
    monkeypatch.setattr(recipe10.subprocess,'run',builder)
    recipe10.assemble(work)
    assert (component/name).resolve()==(work/'tokenized'/name).resolve()
    assert str(component) in calls[0]
    assert json.loads((work/'assemble-receipt.json').read_text())['status']=='assembled'


def test_native_shard_resume_requires_matching_settings(tmp_path):
    import json
    from scripts.tokenize_dfm10_native_sharded import complete, FIELDS
    source=tmp_path/'input.parquet';source.write_bytes(b'input')
    output=tmp_path/'output';output.mkdir()
    for field in FIELDS:(output/(field+'.npy')).write_bytes(b'array')
    metadata={'source_size':source.stat().st_size,'source_mtime':int(source.stat().st_mtime),
              'max_seq_len':4096,'preserve_first_user':True}
    (output/'metadata.json').write_text(json.dumps(metadata))
    assert complete(output,source,4096)
    assert not complete(output,source,8192)
    metadata['preserve_first_user']=False
    (output/'metadata.json').write_text(json.dumps(metadata))
    assert not complete(output,source,4096)


def test_historical_capped_tasks_are_routed_separately():
    from scripts.restore_dfm10_token_limits import COMPONENTS
    from scripts import rebuild_dfm10 as recipe
    cfg=json.loads(recipe.CONFIG.read_text())
    expected=set()
    for task in cfg['tasks']:
        meta=json.loads((recipe.REFERENCE/task['task']/'metadata.json').read_text())
        if not task['native'] and meta.get('max_seq_len') is not None:
            assert meta['max_seq_len']==4096 and meta['preserve_first_user'] is False
            expected.add(task['task'])
    selected={t['task'] for t in cfg['tasks'] if t['component'] in COMPONENTS}
    assert selected==expected and len(selected)==14


def test_dolci_restore_order_preserves_published_values():
    from scripts.recover_dfm10_dolci_order import restore_mapping_order
    raw = {'frequency': {'hello': 1, 'HELLO': 1, 'Hello': 1},
           'conditions': ['>=', '2023-07-10']}
    published = {'conditions': ['2023-07-10', '>='],
                 'frequency': {'HELLO': 1, 'Hello': 1, 'hello': 1}}
    restored = restore_mapping_order(published, raw)
    assert restored == published
    assert list(restored['frequency']) == ['hello', 'HELLO', 'Hello']
    assert restored['conditions'] == published['conditions']
    from jinja2 import Environment
    template = Environment().from_string('{{ x|dictsort }}')
    assert template.render(x=restored['frequency']) != template.render(x=published['frequency'])
    with pytest.raises(ValueError, match='schema'):
        restore_mapping_order({'different': 1}, raw)
    with pytest.raises(ValueError, match='schema'):
        restore_mapping_order([1], [])


def test_frozen_swe_adapter_selects_only_designated_target(tmp_path):
    import importlib.util
    import sys
    path = tmp_path / 'frozen_swe.py'
    path.write_bytes(subprocess.check_output(['git', 'show', 'ccbb215:scripts/tokenize_chat_template.py']))
    spec = importlib.util.spec_from_file_location('frozen_swe_test', path)
    adapter = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = adapter
    spec.loader.exec_module(adapter)
    messages = [{'role': 'user', 'content': 'Inspect'},
                {'role': 'assistant', 'content': 'Earlier result'},
                {'role': 'user', 'content': 'Continue'},
                {'role': 'assistant', 'content': 'Final result'}]
    path = tmp_path / 'sample.jsonl'
    path.write_text(json.dumps({'messages': messages, 'target_message_index': 3})+'\n')
    examples = list(adapter.read_jsonl(path))
    assert len(examples) == 1
    assert examples[0].prompt_messages == messages[:3]
    assert examples[0].assistant_message == messages[3]
    assert len(list(adapter.examples_from_messages(messages))) == 2


def test_dfm10_sampling_uses_historical_drop_policy(tmp_path):
    from scripts.finish_dfm10_hf import sample_command
    args = sample_command(tmp_path)
    assert 'default_long_context=drop' in args
    assert 'epochs=10' in args and 'seed=0' in args
    assert 'reuse_tokens=true' not in args
    (tmp_path/'sampled').mkdir()
    (tmp_path/'sampled/tokens.npy').touch()
    assert 'reuse_tokens=true' in sample_command(tmp_path)
