"""Offline tests: inspect Python source, never import/run EuroEval models."""
import ast
from collections import Counter
import hashlib
from pathlib import Path

import pytest
import yaml

from scripts.inspect_euroeval_dfm12 import calls

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config/euroeval_dfm12_multilingual.yaml'


@pytest.fixture(scope='module')
def registry():
    return yaml.safe_load(CONFIG.read_text())


def test_exact_languages_and_complete_category_matrix(registry):
    expected=set('nl nb nn sv is fo pl de fr es it cs pt_pt fi el ro uk et ca'.split())
    assert set(registry['languages'])==expected
    assert len(registry['entries'])==190
    for language in expected:
        entries=[e for e in registry['entries'] if e['language']==language]
        assert Counter(e['category'] for e in entries)==Counter(registry['categories'])


def test_single_dataset_groups_and_exact_metric_key(registry):
    for entry in registry['entries']:
        if entry['dataset'] is None:
            assert entry['status']=='coverage_gap'
            assert entry['metric_key'] is None and not entry['include_in_average']
            continue
        assert entry['datasets']==[entry['dataset']]
        assert entry['deduplication_key']==entry['dataset']
        assert entry['metric_key']=='/'.join(['euroeval','_'.join(entry['euroeval_result_languages']),
            entry['task'],entry['dataset'],entry['metric_name']])
        assert entry['installed_18_1_supported']
        assert any(registry['source_evidence']['upstream_commit'] in ref for ref in entry['source_refs'])


def test_all_selected_names_and_categories_in_pinned_cached_install(registry):
    evidence=registry['source_evidence']['cached_18_1'];root=Path(evidence['path'])
    if not root.exists():pytest.skip('Cached EuroEval installation not present on this machine')
    configs={}
    for relative,sha in evidence['file_sha256'].items():
        path=root/relative
        assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
        if relative.startswith('dataset_configs/'):
            for cfg in calls(path.read_text(),'DatasetConfig').values():configs[cfg['name']]=cfg
    tasks=calls((root/'tasks.py').read_text(),'Task')
    for entry in registry['entries']:
        if not entry['dataset']:continue
        cfg=configs[entry['dataset']]
        assert cfg['source']==entry['source_dataset']
        assert tasks[cfg['task']]['name']==entry['task']
        assert tasks[cfg['task']]['metrics']==entry['metrics_code_symbols']


def test_norquad_visible_but_not_clean(registry):
    entries=[e for e in registry['entries'] if e['dataset']=='norquad']
    assert {e['language'] for e in entries}=={'nb','nn'}
    assert all(e.get('catalog_status',e['status'])=='contamination_flagged' and not e['include_in_average'] for e in entries)
    assert all('norquad_training_inclusion_and_known_passage_overlap' in e['contamination_flags'] for e in entries)
    assert all('/nb_nn_no/' in e['metric_key'] for e in entries)


def test_shared_norwegian_not_false_variant_results(registry):
    shared=[e for e in registry['entries'] if e.get('language_scope')=='shared_norwegian_not_variant_isolated']
    assert shared
    assert all(not e['include_in_average'] for e in shared)
    nb=next(e for e in registry['entries'] if e['dataset']=='scala-nb')
    nn=next(e for e in registry['entries'] if e['dataset']=='scala-nn')
    assert '/nb_no/' in nb['metric_key'] and '/nn_no/' in nn['metric_key']


def test_portuguese_variant_and_tool_gaps(registry):
    pt=[e for e in registry['entries'] if e['language']=='pt_pt']
    instruction=next(e for e in pt if e['task']=='instruction-following')
    assert instruction.get('catalog_status',instruction['status'])=='variant_unverified' and not instruction['include_in_average']
    assert '/pt/' in instruction['metric_key']
    ner=next(e for e in pt if e['task']=='named-entity-recognition')
    assert '/pt_pt-pt/' in ner['metric_key']
    assert all(e['dataset'] is None for e in registry['entries'] if e['task']=='tool-calling')


def test_existing_suite_not_replaced(registry):
    tree=ast.parse((ROOT/'eval_scheduler/eval_scheduler/catalog.py').read_text())
    baseline=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='EUROEVAL_GROUPS' for t in n.targets))
    assert [e['dataset'] for e in registry['existing_da_en_groups']]==baseline
    assert len(baseline)==20
    assert len([e for e in registry['existing_da_en_groups'] if e['language']=='en'])==10


def test_no_environment_resolution_or_launch(registry):
    execution=registry['execution']
    assert execution['version']=='18.1.0'
    assert 'uv run' not in execution['euroeval_bin']
    assert execution['dataset_arguments']==['--dataset','{dataset}']
    assert execution['do_not_combine_dataset_with']==['--language','--task']
    assert execution['checkpoint_launch_authorized_here'] is False


def test_coverage_counts_and_noncapability_values(registry):
    entries=registry['entries']
    assert sum(e['dataset'] is not None for e in entries)==163
    assert len({e['dataset'] for e in entries if e['dataset']})==157
    assert sum(e['status']=='coverage_gap' for e in entries)==27
    assert all(not e['include_in_average'] for e in entries if e['task']=='european-values')


def test_remote_failures_do_not_redefine_benchmark_population(registry):
    receipt_path=ROOT/'config/euroeval_dfm12_multilingual_access.json'
    import json
    receipt=json.loads(receipt_path.read_text())
    assert hashlib.sha256(receipt_path.read_bytes()).hexdigest()==registry['source_evidence']['access_receipt_sha256']
    assert receipt['unique_datasets']==157 and receipt['mass_download'] is False
    access={r['source_dataset']:r for r in receipt['sources']}
    for entry in registry['entries']:
        if not entry['dataset']:continue
        record=access[entry['source_dataset']]
        if record['status']!='accessible':
            assert entry['remote_probe']['classification']=='unresolved_remote_access'
            assert entry['status']==entry['catalog_status']
            assert entry['include_in_average']==entry['catalog_include_in_average']
        else:
            assert entry['dataset_revision']==record['revision']


def test_preflight_retains_catalog_policy_on_failure_and_recovery():
    from scripts.preflight_euroeval_dfm12 import apply_results
    config={'entries':[dict(language='nb',dataset='norquad',source_dataset='EuroEval/norquad-mini',
        status='contamination_flagged',include_in_average=False)],'coverage':{'nb':{}}}
    apply_results(config,[dict(source_dataset='EuroEval/norquad-mini',status='blocked_remote',revision=None)])
    assert config['entries'][0]['status']=='contamination_flagged'
    assert config['entries'][0]['remote_probe']['classification']=='unresolved_remote_access'
    apply_results(config,[dict(source_dataset='EuroEval/norquad-mini',status='accessible',revision='abc')])
    assert config['entries'][0]['status']=='contamination_flagged'
    assert config['entries'][0]['include_in_average'] is False


def test_runtime_auth_access_and_no_persisted_credentials(registry):
    import json
    import re
    receipt=json.loads((ROOT/'config/euroeval_dfm12_multilingual_access.json').read_text())
    assert receipt['authentication']=='installed_framework_primary_credential'
    assert receipt['counts']=={'accessible':157}
    for record in receipt['sources']:
        assert re.fullmatch('[0-9a-f]{40}',record['revision'])
        assert record['head_bytes']>0
    for path in (ROOT/'config').glob('euroeval_dfm12_multilingual*'):
        assert not re.search(r'hf_[A-Za-z0-9]{20,}',path.read_text())
