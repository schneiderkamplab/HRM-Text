import pytest
from scripts import dfm13_repochat_repair_finalization_once as m


@pytest.mark.parametrize('error,finish,allowed', [('non_stop:length', 'length', True), ('semantic_reject', 'stop', False), ('non_stop:length', 'stop', False)])
def test_selection(tmp_path, error, finish, allowed):
    m.p.b.save(tmp_path / 'outcome.json', {'error': error})
    m.p.b.save(tmp_path / 'response.json', {'choices': [{'finish_reason': finish}]})
    m.p.b.save(tmp_path / 'request.json', {'model': 'test'})
    if allowed:
        assert m.validate(tmp_path)['model'] == 'test'
    else:
        with pytest.raises(ValueError):
            m.validate(tmp_path)


def test_existing_output_refused(tmp_path):
    with pytest.raises(ValueError):
        m.run(tmp_path / 'old', tmp_path)
