import copy
import json
from pathlib import Path
import yaml

from dfm14.prepare_evals import build_eval_definitions
from scripts import prepare_dfm14_eval_extension as importer

ROOT=Path(__file__).resolve().parents[1]


def test_shared_definitions_match_current_artifacts_without_writing():
    previous=json.loads((ROOT/'config/multilingual_headline_populations_dfm13_dala_v2_20261006.json').read_text())
    before=copy.deepcopy(previous)
    suite,tasks,populations=build_eval_definitions(ROOT,importer.MANIFEST,importer.SUITE,previous)
    assert suite==yaml.safe_load(importer.SUITE.read_text())
    assert tasks==json.loads(importer.REGISTRY.read_text())
    assert populations==json.loads(importer.POPULATION.read_text())
    assert previous==before
    assert [len(p['languages']) for p in populations['populations']]==[16,48,50]
    assert all(p['aggregation_policy']=='available_tasks_then_available_languages_v1'
               for p in populations['populations'])
    assert importer.build_eval_definitions is build_eval_definitions


def test_caller_paths_and_no_aliasing():
    previous=json.loads((ROOT/'config/multilingual_headline_populations_dfm13_dala_v2_20261006.json').read_text())
    suite,tasks,populations=build_eval_definitions('/isolated/root','/local/heldout.json','/local/suite.yaml',previous)
    assert tasks[0]['config']=='/local/suite.yaml'
    task=suite['sets']['dala_ga']['tasks'][0]
    assert task['name']=='/isolated/root/evaluation/dfm14_tasks.py@dala_dfm14'
    assert 'manifest=/local/heldout.json' in task['args']
    populations['populations'][0]['metrics']['ga']['dala']['key']='changed'
    assert populations['populations'][1]['metrics']['ga']['dala']['key']!='changed'
