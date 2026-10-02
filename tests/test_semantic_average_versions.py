import copy
import json
from pathlib import Path

import pytest

from scripts.prepare_semantic_acceptability_averages import MANIFESTS, semantic_registry, extend
from eval_scheduler.model import Action, Job, JobStatus
from scripts.publish_semantic_population_panels import update_spec


@pytest.mark.parametrize('name', MANIFESTS)
def test_only_scoring_and_version_change(name):
    old = json.loads((Path('config') / name).read_text())
    before = copy.deepcopy(old)
    new = semantic_registry(old)
    assert old == before
    for a, b in zip(old['populations'], new['populations']):
        assert a['id'] != b['id']
        restored = copy.deepcopy(b)
        restored['id'] = a['id']
        for bindings in restored['metrics'].values():
            for binding in bindings.values():
                if binding:
                    binding['key'] = binding['key'].replace('/semantic_v1/macro_f1',
                        '/linguistic-acceptability/dfm_evals_macro_f1')
        assert restored == a


def test_plan_extension_additive_idempotent():
    job = Job(job_id='old', action=Action.AVERAGE, family='average', name='headline',
              deps=('a', 'b'), status=JobStatus.DONE, attempt=2, log_dir='/tmp/old',
              metadata={'multilingual_manifest': next(iter(MANIFESTS)),
                        'ckpt_tag': 'epoch_10', 'eval_step': 2877261})
    output = extend([job])
    assert output[0] == job
    assert len(output) == 2
    new = output[1]
    assert new.deps == job.deps
    assert new.status == JobStatus.PENDING and new.attempt == 0
    assert new.metadata['eval_step'] == 2877261
    assert new.metadata['multilingual_manifest'] != job.metadata['multilingual_manifest']
    assert extend(output) == output


def test_panel_update_preserves_selections_and_legacy_curves():
    old = {'selection': {'tree': ['keep']}, 'section': {'panelBankConfig': {'sections': [
        {'name': 'Headline Averages', 'panels': [
            {'config': {'metrics': ['avg_population/multilingual_v1/score'], 'xAxis': 'avg_population/epoch'}},
            {'config': {'metrics': ['headline_avg_v3/danish'], 'xAxis': 'headline_avg_v3/epoch'}}]},
        {'name': 'Spanish Headline Metrics', 'panels': [{'config': {
            'metrics': ['dfm_eval/dala_es/linguistic-acceptability/dfm_evals_macro_f1'],
            'chartTitle': 'DaLA', 'xAxis': 'dfm_eval/epoch'}}]}]}}}
    before = copy.deepcopy(old)
    updated, changes = update_spec(old)
    assert old == before
    assert updated['selection'] == old['selection']
    sections = updated['section']['panelBankConfig']['sections']
    assert sections[0]['panels'][1] == old['section']['panelBankConfig']['sections'][0]['panels'][1]
    assert sections[1]['panels'][0]['config']['xAxis'] == 'dfm_eval/epoch'
    assert len(changes) == 2
    assert update_spec(updated) == (updated, [])
