from scripts.decision_source_overlap import compile_manifest, match


MANIFEST = {'sources': {
    'glue/mnli': {'dataset': 'nyu-mll/glue'},
    'glue/qnli': {'dataset': 'nyu-mll/glue'},
    'snli': {'dataset': 'stanfordnlp/snli'},
    'super_glue/boolq': {'dataset': 'aps/super_glue'},
    'contract-nli/full': {'dataset': 'tasksource/contract-nli', 'originals': ['kiddothe2b/contract-nli']},
}}


def test_exact_repo_and_original_alias():
    result = match({'dataset': 'local', 'hf_ids': ['kiddothe2b/contract-nli']}, compile_manifest(MANIFEST))
    assert result['status'] == 'EXACT REPO'
    assert result['tasks'] == ['contract-nli/full']


def test_config_specific_not_entire_glue():
    result = match({'dataset': 'flan/glue_mnli_2.0.0'}, compile_manifest(MANIFEST))
    assert result['tasks'] == ['glue/mnli']


def test_generic_names_do_not_match():
    result = match({'dataset': 'synthetic_nli_code_math'}, compile_manifest(MANIFEST))
    assert result['status'] == 'NOT IDENTIFIED'


def test_derivative_and_boundaries():
    compiled = compile_manifest(MANIFEST)
    assert match({'dataset': 'synthetic_snli'}, compiled)['status'] == 'POSSIBLE DERIVATIVE'
    assert match({'dataset': 'snli_extra'}, compiled)['status'] == 'TASK/FAMILY MATCH'
    assert match({'dataset': 'xsni_snlish'}, compiled)['status'] == 'NOT IDENTIFIED'
    assert match({'dataset': 'boolq_entailment.jsonl'}, compiled)['status'] == 'POSSIBLE DERIVATIVE'
