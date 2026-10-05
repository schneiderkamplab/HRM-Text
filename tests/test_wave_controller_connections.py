"""Exercise the actual controller connection context expressions on both exits."""
import ast
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('filename,count', [('scripts/advance_wave4_transforms.py', 1),
    ('scripts/advance_wave4_selections.py', 1), ('scripts/select_baltic_translations.py', 1),
    ('scripts/monitor_dfm13_wave_campaign.py', 3), ('dfm12/wave4_gemma31_transition.py', 2)])
@pytest.mark.parametrize('failed', [False, True])
def test_read_connection_always_closed(filename, count, failed, tmp_path):
    tree = ast.parse((Path(__file__).parents[1] / filename).read_text())
    contexts = [item.context_expr for node in ast.walk(tree) if isinstance(node, ast.With)
                for item in node.items if 'sqlite3.connect' in ast.unparse(item.context_expr)]
    assert len(contexts) == count
    for expression in contexts:
        assert isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name)
        assert expression.func.id == 'closing'
        calls = []
        connection = SimpleNamespace(close=lambda: calls.append('closed'))
        context = eval(compile(ast.Expression(expression), filename, 'eval'),
                       dict(closing=closing, sqlite3=SimpleNamespace(connect=lambda *a, **k: connection),
                            root=tmp_path, ledger=tmp_path, baltic=tmp_path, wave4=tmp_path,
                            database=tmp_path, path=tmp_path, Path=Path))
        try:
            with context as db:
                assert db is connection
                if failed:
                    raise RuntimeError('query failed')
        except RuntimeError:
            assert failed
        assert calls == ['closed']
