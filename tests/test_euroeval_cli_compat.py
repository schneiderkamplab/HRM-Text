from scripts.euroeval_cli_compat import dataset_only_selectors


def test_dataset_preserves_explicit_selection_without_languages():
    assert dataset_only_selectors(['--language', 'da', '--language=en',
                                  '--dataset', 'angry-tweets', '--model', 'test']) == [
                                      '--dataset', 'angry-tweets', '--model', 'test']


def test_language_only_selection_is_unchanged():
    args = ['--language', 'da', '--language', 'en']
    assert dataset_only_selectors(args) == args


def test_multiple_datasets_are_preserved():
    assert dataset_only_selectors(['--dataset=a', '--dataset', 'b', '--language=da']) == [
        '--dataset=a', '--dataset', 'b']
