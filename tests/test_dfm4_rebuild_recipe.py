from pathlib import Path

from scripts import generate_dfm4_tasks as generator
from scripts import queue_dfm_hf_rebuild as queue
from scripts.rebuild_dfm4_additions import paragraph_rows


def test_common_pile_uses_leading_single_window():
    text = '\n\n'.join((str(i) + ' A fairly long English paragraph. ' * 5) for i in range(12))
    rel = Path('common_pile_example/input.parquet')
    rows = paragraph_rows(text, 'common_pile', rel, 0)
    assert len(rows) == 1
    expected = generator.split_paragraphs(generator.trim_text(text, 1370))[:8]
    assert rows[0]['response'] == '\n\n'.join(expected)


def test_dynaword_keeps_multiwindow_algorithm():
    text = '\n\n'.join((str(i) + ' En lang dansk tekst. ' * 6) for i in range(30))
    rel = Path('data/example.parquet')
    assert paragraph_rows(text, 'dynaword', rel, 12) == generator.paragraph_reorder_rows(
        text, 'da', 20260601, 4, 'dynaword', rel, 12)


def test_dfm4_uses_safe_tokenizer_and_five_epochs(tmp_path):
    command = queue.dfm4_command(tmp_path, 'tokenize-paragraph')
    assert any('tokenize_hrm_hf.py' in value for value in command)
    assert command[command.index('--workers') + 1] == '64'
    sample = queue.dfm4_command(tmp_path, 'sample')
    assert 'epochs=5' in sample
    assert 'concat_workers=1' in sample
    assert f'output_path={tmp_path / "dfm4/sampled"}' in sample
