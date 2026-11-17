"""DFM10 additions only: inherited families come from the verified DFM9 union."""
INHERITED_PACKAGES = {
    'dfm10-ai-arena-udtraek-sft', 'dfm10-arxiv-paper-summarization-sft',
    'dfm10-croco-munin-chosen-sft', 'dfm10-glaive-native-tool-use',
    'dfm10-natural-instructions-filtered-sft', 'dfm10-numinamath-valid-sft',
    'dfm10-toolace-native-tool-use', 'dfm10-xlam-native-tool-use',
    *('dfm10-sapient-' + name + '-filtered-sft' for name in (
        'acereason', 'amps-mathematica', 'dmmath', 'flan-cot', 'flan-dialog',
        'flan-flan', 'flan-niv2', 'flan-t0', 'openmathinstruct2', 'openthoughts2',
        'platypus', 'sudoku-extreme', 'synth', 'tasksource', 'textbook-reasoning')),
}


def inherited(repo_id):
    return repo_id.removeprefix('schneiderkamplab/') in INHERITED_PACKAGES
