from dfm12.wave4_publication_notices import notice


def test_oh_unknown_is_disclosed_not_excluded_or_relicensed():
    text=notice({'sources':{'schneiderkamplab/dfm8-openhermes-en':1}})
    assert 'Empty component labels remain unknown' in text
    assert 'no row is excluded' in text
    assert 'not represented as an upstream SPDX' in text


def test_wiki_attribution_license_and_changes():
    text=notice({'sources':{'wikimedia/wikipedia':1}})
    assert 'CC BY-SA 4.0' in text and 'document_url' in text
    assert 'CC BY-SA 3.0' in text and 'retained source text keeps its original notice' in text
    assert 'not exact article revision IDs' in text and 'Changes include' in text


def test_synthetic_not_claimed_external_source():
    text=notice({'sources':{'synthetic_reference':1}})
    assert 'fictional' in text and 'No external source identity is fabricated' in text
    assert 'CC BY-SA' not in text
