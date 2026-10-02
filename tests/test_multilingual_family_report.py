import json

import pytest

from scripts.multilingual_family_report import aggregate, binding, escape, render


def checkpoint(tmp_path, name, metrics):
    root = tmp_path / name
    root.mkdir()
    (root / 'merged_metrics.json').write_text(json.dumps({'epoch': 10, 'metrics': metrics}))
    return {'label': name, 'epoch': 10, 'step': 100, 'roots': [str(root)]}


def test_bindings_and_units():
    assert binding('dfm_eval/govreport/chrf3pp/mean')[-1] == 1
    assert binding('dfm_eval/dala/semantic_v1/macro_f1')[-1] == .01
    assert binding('dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1') is None
    assert binding('euroeval/en/instruction-following/valeu-en/instruction_accuracy') is None
    assert binding('euroeval/pt/reading-comprehension/multi-wiki-qa-pt/f1')[1] == 'pt_pt'
    assert binding('euroeval/en/reading-comprehension/squad/f1/lower') is None


def test_mean_range_fixed_membership_and_pages(tmp_path):
    a = checkpoint(tmp_path, 'A', {
        'euroeval/en/summarization/cnn-dailymail/chr_f3pp': 20,
        'dfm_eval/govreport/chrf3pp/mean': 40,
        'dfm_eval/gec_dala/exact_match/mean': .5})
    b = checkpoint(tmp_path, 'B', {
        'euroeval/en/summarization/cnn-dailymail/chr_f3pp': 30,
        'dfm_eval/govreport/chrf3pp/mean': 50,
        'dfm_eval/gec_dala/exact_match/mean': .6})
    report = aggregate([a, b], 1)
    cell = report['families']['summarization']['rows']['en']['cells'][0]
    assert (cell['mean'], cell['min'], cell['max']) == (30, 20, 40)
    assert report['families']['summarization']['rows']['en']['change_pp'] == 10
    tex = render(report)
    assert '30.00 (20.00--40.00)' in tex
    assert tex.count('\\clearpage') == 1
    assert '50.00 (50.00--50.00)' in tex
    assert 'Change (pp)' in tex
    assert '+10.00' in tex
    p = tmp_path / 'B' / 'merged_metrics.json'
    p.write_text(json.dumps({'metrics': {'dfm_eval/govreport/chrf3pp/mean': 50}}))
    report = aggregate([a, b], 1)
    assert report['excluded_families']['summarization'] == 0


def test_joint_language_not_double_counted(tmp_path):
    cp = checkpoint(tmp_path, 'A', {'euroeval/nb_nn_no/summarization/no-sammendrag/chr_f3pp': 30})
    assert aggregate([cp], 1)['families'] == {}


def test_bad_stamp_conflict_and_invalid_value(tmp_path):
    cp = checkpoint(tmp_path, 'A', {'dfm_eval/govreport/chrf3pp/mean': 30})
    cp['epoch'] = 11
    with pytest.raises(ValueError, match='Epoch mismatch'):
        aggregate([cp], 1)
    cp['epoch'] = 10
    extra = tmp_path / 'A' / 'duplicate'
    extra.mkdir()
    path = extra / 'merged_metrics.json'
    path.write_text(json.dumps({'metrics': {'dfm_eval/govreport/chrf3pp/mean': 31}}))
    with pytest.raises(ValueError, match='Conflicting duplicate'):
        aggregate([cp], 1)
    path.write_text(json.dumps({'metrics': {'dfm_eval/govreport/chrf3pp/mean': -1}}))
    with pytest.raises(ValueError, match='Invalid score'):
        aggregate([cp], 1)


def test_latex_escape():
    assert escape('a_b & 50%') == r'a\_b \& 50\%'
