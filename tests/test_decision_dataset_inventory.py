from scripts.build_decision_dataset_inventory import Inventory, assessment, source_key


def test_conservative_routing():
    for name in ('online', 'chocolate', 'tv2r'):
        assert assessment(name)['assessment_family'] == 'unmapped_unknown'
    assert assessment('dala_tv2r')['rubric'] == 'A'
    assert assessment('gec_dala_tv2r')['rubric'] == 'B'
    assert assessment('prefix-continuation')['rubric'] == 'C'
    assert assessment('ai_arena_udtraek')['assessment_family'] == 'grounded_or_open_response'
    assert assessment('arena_preferred')['assessment_family'] == 'preference'
    assert assessment('paragraph_reordering')['rubric'] == 'B'
    assert assessment('tasksource__nli')['rubric'] == 'A'
    assert assessment('tasksource__nli')['assessment_confidence'] == 'inferred_name_only'


def test_source_granularity():
    assert source_key('sapient_cleaned__data_clustered__tasksource__boolq.parquet').endswith('boolq')
    assert source_key('my_source__part-00001.jsonl') == 'my_source'


def test_task_evidence_keeps_provenance_without_rows(tmp_path):
    inventory = Inventory(tmp_path)
    for i in range(2):
        inventory.task(f'source__{i}.parquet', 1, 'reported_sampled_positive', tmp_path / 'report.md', f'line:{i}',
                       {'sampled_rows_report_total': 4})
    record = inventory.records['source_key:source']
    assert len(record['evidence']) == 1
    assert record['evidence'][0]['pointers'] == ['line:0', 'line:1']
    assert record['evidence'][0]['sampled_rows_report_total'] == 8
    assert len(inventory.tasks['source']) == 2
