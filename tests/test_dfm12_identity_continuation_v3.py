import copy
import gzip
import json
from pathlib import Path

import pytest
import yaml

from dfm12.io import digest, file_hash
from scripts import evaluate_dfm12_identity_continuation_v3 as evaluation


def write_rows(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, 'wt', encoding='utf-8') as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')


def seal(root, manifest):
    manifest['files'] = [{'path': str(p.relative_to(root)), 'sha256': file_hash(p), 'bytes': p.stat().st_size}
                         for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'manifest.json']
    (root / 'manifest.json').write_text(json.dumps(manifest))
    return file_hash(root / 'manifest.json')


@pytest.fixture
def corpora(tmp_path):
    assets = {}
    for key in ('tokenizer', 'template'):
        path = tmp_path / key
        path.write_text('fixture ' + key)
        assets[key] = {'path': str(path), 'sha256': file_hash(path)}
    roots = {}
    for prefix in ('old', 'fresh'):
        root = tmp_path / prefix
        (root / 'metadata').mkdir(parents=True)
        (root / 'metadata/identity_facts.yaml').write_text('facts: fixture\n')
        spec = {'requests': {key: {'detailed': {'da': 'Mimir fra bunden.', 'en': 'Mimir trained from scratch.'}}
                             for key in evaluation.historical.REGRESSION_REQUESTS.values()}}
        (root / 'metadata/identity_expansion.yaml').write_text(yaml.safe_dump(spec))
        provenance, languages = [], {}
        for lang in ('da', 'en'):
            records = []
            for i in range(50):
                row = {'id': f'{prefix}-{lang}-{i}', 'language': lang,
                       'messages': [{'role': 'user', 'content': f'{prefix} question {lang} {i}'},
                                    {'role': 'assistant', 'content': spec['requests']['name']['detailed'][lang]}]}
                records.append(row)
                provenance.append({'id': row['id'], 'language': lang, 'record_sha256': digest(row),
                                   'split': 'heldout', 'family': prefix,
                                   'turn_references': [{'requests': ['name'], 'answer_forms': ['detailed']}]})
            write_rows(root / f'heldout/{lang}/test.jsonl.gz', records)
            relative = f'inputs/{lang}/train.jsonl.gz'
            write_rows(root / relative, [{'id': f'train-{lang}', 'language': lang,
                                         'messages': [{'role': 'user', 'content': f'training {lang}'},
                                                      {'role': 'assistant', 'content': 'Mimir'}]}])
            languages[lang] = {'input': relative}
        write_rows(root / 'metadata/provenance.jsonl.gz', provenance)
        manifest = dict(assets, profile='xl-full-bp', enable_thinking=False, languages=languages)
        roots[prefix] = (root, seal(root, manifest))
    return roots


def load_fixture(corpora):
    root, sha = corpora['fresh']
    old, old_sha = corpora['old']
    return evaluation.load_cases(root, sha, 'metadata/identity_expansion.yaml', old, old_sha)


def test_explicit_fresh_manifest_fixed_regressions_and_development_policy(corpora):
    cases, manifest, policy = load_fixture(corpora)
    assert len(cases) == 116
    assert [(c['id'], c['language'], c['users'][0]) for c in cases[:16]] == evaluation.historical.QUESTIONS
    assert all(c['id'].startswith('fresh-') for c in cases[16:])
    assert [c['language'] for c in cases[16:]] == ['da', 'en'] * 50
    assert policy['old_heldout_status'] == 'development_only_not_evaluated'
    assert policy['training_files_checked'] == ['inputs/da/train.jsonl.gz', 'inputs/en/train.jsonl.gz']


def test_refuse_old_holdout_as_fresh(corpora):
    root, sha = corpora['old']
    with pytest.raises(ValueError, match='development data'):
        evaluation.load_cases(root, sha, 'metadata/identity_expansion.yaml', root, sha)


def test_pin_and_unlisted_spec_fail_closed(corpora):
    root, sha = corpora['fresh']
    old, old_sha = corpora['old']
    with pytest.raises(ValueError, match='manifest SHA'):
        evaluation.load_cases(root, '0' * 64, 'metadata/identity_expansion.yaml', old, old_sha)
    with pytest.raises(ValueError, match='not listed'):
        evaluation.load_cases(root, sha, '../unlisted.yaml', old, old_sha)
    path = root / 'heldout/da/test.jsonl.gz'
    path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='checksum'):
        load_fixture(corpora)


@pytest.mark.parametrize('overlap', ['old question da 0', 'training da'])
def test_fresh_wording_cannot_overlap_development_or_training(corpora, overlap):
    root, _ = corpora['fresh']
    path = root / 'heldout/da/test.jsonl.gz'
    records = list(evaluation.historical.gzip_rows(path))
    records[0]['messages'][0]['content'] = overlap
    write_rows(path, records)
    corpora['fresh'] = root, seal(root, json.loads((root / 'manifest.json').read_text()))
    with pytest.raises(ValueError, match='overlaps training/development'):
        load_fixture(corpora)


def test_target_requires_frozen_binding_even_if_record_hash_matches(corpora):
    root, _ = corpora['fresh']
    path = root / 'heldout/da/test.jsonl.gz'
    records = list(evaluation.historical.gzip_rows(path))
    records[0]['messages'][1]['content'] = 'Invented target'
    write_rows(path, records)
    pp = root / 'metadata/provenance.jsonl.gz'
    provenance = list(evaluation.historical.gzip_rows(pp))
    provenance[0]['record_sha256'] = digest(records[0])
    write_rows(pp, provenance)
    corpora['fresh'] = root, seal(root, json.loads((root / 'manifest.json').read_text()))
    with pytest.raises(ValueError, match='frozen request bindings'):
        load_fixture(corpora)


def test_new_request_names_and_answer_forms_do_not_change_old_regressions(corpora):
    root, _ = corpora['fresh']
    old, old_sha = corpora['old']
    old_spec = yaml.safe_load((root / 'metadata/identity_expansion.yaml').read_text())
    new_spec = {'requests': {'scratch': {'brief': old_spec['requests']['name']['detailed']}}}
    relative = 'metadata/identity_repair_expansion.yaml'
    (root / relative).write_text(yaml.safe_dump(new_spec))
    path = root / 'metadata/provenance.jsonl.gz'
    provenance = list(evaluation.historical.gzip_rows(path))
    for p in provenance:
        p['turn_references'] = [{'requests': ['scratch'], 'mode': 'brief'}]
    write_rows(path, provenance)
    manifest = json.loads((root / 'manifest.json').read_text())
    manifest['schema'] = 'dfm12-curated-identity-repair-v3'
    sha = seal(root, manifest)
    cases, _, _ = evaluation.load_cases(root, sha, relative, old, old_sha)
    assert cases[0]['requests'] == [['name']]
    assert cases[16]['requests'] == [['scratch']]


@pytest.mark.parametrize('mutation', ['duplicate_provenance', 'system_role', 'turn_references', 'facts_drift'])
def test_malformed_source_contract_fails(corpora, mutation):
    root, _ = corpora['fresh']
    if mutation == 'facts_drift':
        (root / 'metadata/identity_facts.yaml').write_text('changed: true\n')
    elif mutation == 'system_role':
        path = root / 'heldout/da/test.jsonl.gz'
        records = list(evaluation.historical.gzip_rows(path))
        records[0]['messages'][0]['role'] = 'system'
        write_rows(path, records)
    else:
        path = root / 'metadata/provenance.jsonl.gz'
        records = list(evaluation.historical.gzip_rows(path))
        if mutation == 'duplicate_provenance':
            records.append(records[0])
        else:
            records[0]['turn_references'] = []
        write_rows(path, records)
    corpora['fresh'] = root, seal(root, json.loads((root / 'manifest.json').read_text()))
    with pytest.raises(ValueError):
        load_fixture(corpora)


def output(stop='eos'):
    return {'response': 'Mimir was trained from scratch, not from Gemma weights.',
            'generated_token_ids': [42] * (512 if stop == 'length' else 8),
            'generated_token_count': 512 if stop == 'length' else 8,
            'finish_reason': stop, 'truncated': stop == 'length'}


@pytest.mark.parametrize('bad', [None, '', {'response': ''}, {'response': 123},
                               dict(output(), generated_token_ids=[]),
                               dict(output(), finish_reason='cancelled'),
                               dict(output(), truncated=True),
                               dict(output('length'), generated_token_count=511),
                               dict(output(), generated_token_ids=[True] * 8)])
def test_bad_outputs_fail_not_length_stop_acceptance(bad):
    with pytest.raises(evaluation.InvalidGeneration):
        evaluation.validate_generation(bad, 512)


def completed_report(stop='eos'):
    case = {'id': 'one', 'suite': 'heldout', 'language': 'en', 'users': ['Origin?', 'Weights?'],
            'expected_targets': ['from scratch', 'not Gemma weights'], 'requests': [['creator'], ['gemma_weights']]}
    conversation = evaluation.historical.run_conversation(case, lambda _: output(stop))
    return {'status': 'running', 'cases': [case], 'max_new_tokens': 512,
            'dataset_policy': {'old_heldout_status': 'development_only_not_evaluated'},
            'runs': [{'label': label, 'status': 'complete', 'checkpoint': '/fixture', 'tag': tag,
                      'conversations': [copy.deepcopy(conversation)]} for label, tag in (
                          ('previous', 'step_2879261'), ('continued', 'step_2880261'))]}


@pytest.mark.parametrize('stop', ['eos', 'length'])
def test_completed_with_length_stops_operational_zero_but_review_required(tmp_path, stop):
    report = completed_report(stop)
    assert evaluation.finish_report(report) == 0
    assert report['status'] == ('complete' if stop == 'eos' else 'complete_with_length_stops')
    evaluation.save(tmp_path, report)
    summary = json.loads((tmp_path / 'summary.json').read_text())
    assert summary['operational_success'] is True
    assert summary['identity_positive'] is None and summary['full_suite_approved'] is None
    assert summary['review_required'] is True and summary['paired_turns'] == 2
    assert summary['runs']['continued']['heldout/en']['length_stops'] == (2 if stop == 'length' else 0)
    assert 'Old v2-r2 heldouts are development data' in (tmp_path / 'summary.md').read_text()


def test_budget_and_incomplete_coverage_are_not_success():
    report = completed_report()
    report['runs'][0]['status'] = 'budget_exhausted'
    assert evaluation.finish_report(report) == 3 and report['status'] == 'incomplete_budget'
    report = completed_report()
    report['runs'][1]['conversations'][0]['turns'].pop()
    with pytest.raises(ValueError, match='coverage'):
        evaluation.finish_report(report)
    report = completed_report()
    report['runs'][1]['conversations'][0]['turns'][0]['response'] = ''
    with pytest.raises(evaluation.InvalidGeneration):
        evaluation.finish_report(report)


def cli_args(tmp_path, corpora):
    root, sha = corpora['fresh']
    return ['--checkpoint', '/new-checkpoint-not-yet-present', '--heldout-root', str(root),
            '--heldout-manifest-sha256', sha, '--heldout-spec', 'metadata/identity_expansion.yaml',
            '--output', str(tmp_path / 'report')]


def fixture_main(monkeypatch, corpora):
    loader = evaluation.load_cases
    old, old_sha = corpora['old']
    monkeypatch.setattr(evaluation, 'load_cases', lambda r, s, p: loader(r, s, p, old, old_sha))
    monkeypatch.setattr(evaluation.historical, 'tokenizer_lengths', lambda *a: {'fixture': 'CPU'})


def test_cpu_preflight_never_calls_gpu_and_reports_all_pending_targets(tmp_path, corpora, monkeypatch):
    fixture_main(monkeypatch, corpora)
    monkeypatch.setattr(evaluation, 'run_models', lambda *a: pytest.fail('GPU path entered'))
    assert evaluation.main(cli_args(tmp_path, corpora) + ['--preflight-only']) == 0
    report = json.loads((tmp_path / 'report/responses.json').read_text())
    assert report['operational_success'] is False and report['review_required'] is True
    assert [r['tag'] for r in report['runs']] == ['step_2879261', 'step_2880261']
    assert 'fresh question da 49' in (tmp_path / 'report/responses.md').read_text()
    assert 'from scratch' in (tmp_path / 'report/responses.md').read_text()


def test_operational_failure_persisted_for_manual_review(tmp_path, corpora, monkeypatch):
    fixture_main(monkeypatch, corpora)
    def fail(*args):
        raise RuntimeError('bad model load')
    monkeypatch.setattr(evaluation, 'run_models', fail)
    with pytest.raises(RuntimeError, match='bad model load'):
        evaluation.main(cli_args(tmp_path, corpora))
    report = json.loads((tmp_path / 'report/responses.json').read_text())
    assert report['status'] == 'failed' and report['operational_success'] is False
    assert 'bad model load' in report['error']


def test_historical_evaluator_stays_frozen():
    assert file_hash(evaluation.historical.__file__) == evaluation.HISTORICAL_SCRIPT_SHA
    assert file_hash(evaluation.ROOT / 'scripts/smoke_dfm12_identity.py') == evaluation.REGRESSION_SCRIPT_SHA


def test_new_request_names_keep_limited_role_and_history_review_flags():
    turn = {'response': 'Kristoffer Nielbo leads the training team. Both versions use full backpropagation.',
            'expected_target': 'Peter Schneider-Kamp leads the team. v1 used 5 truncated steps.',
            'requests': ['team', 'history']}
    result = evaluation.review_heuristic(turn)
    assert 'organizational_vs_training_team_role_review_required' in result['review_flags']
    assert 'possible_historical_full_backprop_conflation_check_negation' in result['review_flags']
    assert result['semantic_correctness'] == 'not_assessed'
    assert turn['requests'] == ['team', 'history']


FINAL_ROOT = evaluation.ROOT / 'data/dfm12/identity-repair-da-en-20260926-v3'
FINAL_MANIFEST_SHA = 'af0b82b1dfa43012893cd54255923cf15fc5fca67627f16efacfcd0fc6f8bbf1'
FINAL_SPEC_SHA = 'dbfc93916f38adaae9ab0457922ddab904976a142c7fc517cb1dcf66fd7c99b8'


def test_real_fresh_corpus_preflight_contract():
    if not FINAL_ROOT.exists():
        pytest.skip('Sealed v3 identity artifact unavailable locally')
    cases, manifest, policy = evaluation.load_cases(
        FINAL_ROOT, FINAL_MANIFEST_SHA, 'metadata/identity_repair_expansion.yaml')
    assert len(cases) == 116 and sum(len(c['users']) for c in cases) == 206
    lengths = evaluation.historical.tokenizer_lengths(cases, manifest)
    assert lengths['da']['assistant_targets'] == lengths['en']['assistant_targets'] == 95
    assert lengths['da']['max_target_tokens'] == 123
    assert lengths['en']['max_target_tokens'] == 92
    assert policy['old_heldout_status'] == 'development_only_not_evaluated'


def test_reviewed_frozen_target_bank_origin_role_and_history_guards():
    if not FINAL_ROOT.exists():
        pytest.skip('Sealed v3 identity artifact unavailable locally')
    path = FINAL_ROOT / 'metadata/identity_repair_expansion.yaml'
    assert file_hash(path) == FINAL_SPEC_SHA
    requests = yaml.safe_load(path.read_text())['requests']
    assert len(requests) == 28
    names = ['Peter Schneider-Kamp', 'Jacob Nielsen', 'Lukas Galke Poech',
             'Gianluca Barmina', 'Annemette Brok Pirchert', 'Kenneth Enevoldsen']
    for mode in ('brief', 'contrast'):
        for lang, no in (('da', 'Nej,'), ('en', 'No,')):
            assert all(name in requests['roster'][mode][lang] for name in names)
            assert 'Kristoffer' not in requests['roster'][mode][lang]
            assert 'Kristoffer' not in requests['team'][mode][lang]
            assert all(name in requests['leaders'][mode][lang] for name in ('Kristoffer Nielbo', 'Peter Schneider-Kamp'))
            assert requests['gemma_init'][mode][lang].startswith(no)
            assert requests['synthetic_weights'][mode][lang].startswith(no)
            assert all(n in requests['history'][mode][lang] for n in ('5', '8'))
            assert '4096' in requests['context_tokens'][mode][lang]
            assert all(n in requests['reports'][mode][lang] for n in ('65536', 'Gemma 4', 'HRM-Text'))
    assert 'instead of resetting' in requests['continuation']['brief']['en']
    assert 'does not reinitialize' in requests['continuation']['contrast']['en']
