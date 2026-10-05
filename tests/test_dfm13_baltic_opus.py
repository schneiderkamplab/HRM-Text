from dfm12.baltic_opus import configuration


def test_mesh_and_inherited_budgets():
    cfg = configuration()
    assert len(cfg['languages']) == 23
    assert len(cfg['requested_pairs']) == 43
    assert cfg['pair_budgets']['en-lv']['fraction'] == 0.25
    assert cfg['pair_budgets']['en-lt']['fraction'] == 0.25
    assert cfg['pair_budgets']['es-lv']['fraction'] == 0.0625
    assert cfg['pair_budgets']['lt-lv']['fraction'] == 0.0625
    assert all(x['directions'] == 'combined' for x in cfg['pair_budgets'].values())
    assert all(sorted(['en', lang]) in [list(p) for p in cfg['opus_pairs']]
               for lang in cfg['languages'] if lang != 'en')
