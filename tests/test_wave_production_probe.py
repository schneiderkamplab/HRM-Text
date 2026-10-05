import json

import pytest

from dfm12.wave_production_probe import select_specs


def test_selection_is_balanced_and_deterministic(tmp_path):
    source = tmp_path / 'requests.jsonl'
    examples = [dict(spec=dict(language_code=lang, family=family, slot=i))
                for lang in ('lt', 'lv') for family in ('multiturn', 'math-code')
                for i in range(3)]
    source.write_text(''.join(json.dumps(row) + '\n' for row in examples))
    selected = select_specs(source, 2)
    assert len(selected) == 8
    assert all(row['slot'] < 2 for row in selected)
    assert selected == select_specs(source, 2)
    with pytest.raises(ValueError, match='Insufficient'):
        select_specs(source, 4)
    with pytest.raises(ValueError):
        select_specs(source, 0)
