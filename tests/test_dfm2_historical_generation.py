from scripts.generate_dfm2_dynaword_tasks import make_rows


def test_historical_targets_are_full_and_default_stays_short():
    text = "En dansk tekst med forskellige ord og saetninger. " * 60
    short = dict(make_rows(text, 20260530, "example.parquet", 0, 0))
    full = dict(make_rows(text, 20260530, "example.parquet", 0, 0, True))
    assert short.keys() == full.keys()
    for name in full:
        if "prefix_continuation" in name:
            assert full[name] == short[name]
        else:
            assert full[name]["response"] == text
            assert len(short[name]["response"]) <= 1390
