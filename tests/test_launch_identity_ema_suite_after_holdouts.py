import copy
import pytest
from scripts import launch_identity_ema_suite_after_holdouts as watcher


@pytest.fixture
def evidence(tmp_path):
    case = {'id': 'case', 'suite': 'heldout', 'language': 'en', 'family': 'identity',
            'users': ['Question'], 'expected_targets': ['Answer'], 'requests': [['identity']]}
    cases, conversations = [], []
    for index in range(140):
        row = dict(case, id=str(index))
        history = [{'role': 'user', 'content': 'Question'}]
        turn = {'turn': 1, 'user': 'Question', 'expected_target': 'Answer', 'requests': ['identity'],
                'prompt_messages': copy.deepcopy(history), 'response': 'Answer', 'rendered_prompt': 'Question',
                'prompt_token_ids': [1], 'generated_token_ids': [2], 'generated_token_count': 1,
                'finish_reason': 'eos', 'truncated': False}
        history.append({'role': 'assistant', 'content': 'Answer'})
        conversations.append({k: row[k] for k in ('id', 'suite', 'language', 'family')} |
                             {'turns': [turn], 'generated_history': history, 'status': 'complete'})
        cases.append(row)
    report = {'status': 'complete', 'non_ema': False, 'ema': True, 'script_sha256': 'script',
              'heldout_manifest_sha256': 'manifest', 'cases': cases, 'max_new_tokens': 512,
              'runs': [{'tag': 'step_2881261', 'checkpoint': str(tmp_path / 'checkpoint'),
                        'status': 'complete', 'conversations': conversations,
                        'workers': [{'gpu': gpu, 'status': 'complete', 'ema': True,
                                     'ema_verification': {'verified': True}} for gpu in range(8)]}]}
    preflight = tmp_path / 'preflight.json'
    watcher.write_json(preflight, {'cases': cases})
    config = {'evaluator_sha256': 'script', 'heldout_manifest_sha256': 'manifest',
              'preflight_report': str(preflight), 'checkpoint': str(tmp_path / 'checkpoint')}
    return tmp_path, report, config


def seal(root, report):
    watcher.write_json(root / 'responses.json', report)
    watcher.write_json(root / 'completion.json', {'status': report['status'],
        'responses_sha256': watcher.file_hash(root / 'responses.json')})


def test_complete_ema_allows_semantic_failure(evidence):
    root, report, config = evidence
    report['identity_positive'] = False
    seal(root, report)
    assert watcher.validate_report(root, config)['answers_per_checkpoint'] == 140


@pytest.mark.parametrize('mutation', ['nonema', 'failed', 'missing', 'duplicate', 'wrong_step', 'hash', 'cases', 'script', 'worker_ema'])
def test_invalid_evidence_fails_closed(evidence, mutation):
    root, report, config = evidence
    if mutation == 'nonema': report['non_ema'] = True
    if mutation == 'failed': report['status'] = 'failed'
    if mutation == 'missing': report['runs'][0]['conversations'].pop()
    if mutation == 'duplicate': report['runs'][0]['conversations'][-1] = report['runs'][0]['conversations'][0]
    if mutation == 'wrong_step': report['runs'][0]['tag'] = 'step_2880261'
    if mutation == 'cases': report['cases'] = report['cases'][:-1]
    if mutation == 'script': report['script_sha256'] = 'changed'
    if mutation == 'worker_ema': report['runs'][0]['workers'][0]['ema_verification'] = None
    seal(root, report)
    if mutation == 'hash': watcher.write_json(root / 'responses.json', {'status': 'complete'})
    with pytest.raises(ValueError): watcher.validate_report(root, config)


def test_pin_drift(evidence):
    root, report, config = evidence
    seal(root, report)
    path = root / 'responses.json'
    config['pins'] = {str(path): watcher.file_hash(path)}
    watcher.verify_pins(config)
    path.write_text('{}')
    with pytest.raises(ValueError, match='Pinned input'):
        watcher.verify_pins(config)
