from dfm12.wave4_publication_inventory import attribution


def test_wikipedia_snapshot_not_article_revision():
    source = dict(source='wikimedia/wikipedia', document_url='https://xx.wikipedia.org/wiki/A',
                  source_document_id='1', revision='snapshot', source_sha256='hash')
    result, gaps = attribution(dict(provenance=dict(source=source)))
    assert not gaps and result['revision'] == 'snapshot'
    assert 'license' not in result


def test_openhermes_requires_component_and_row():
    result, gaps = attribution(dict(provenance=dict(source=dict(repo='dfm8-openhermes-en', file_sha256='hash'))))
    assert set(gaps) == {'missing_openhermes_source', 'missing_source_row_id'}


def test_unknown_not_synthetic():
    assert attribution({'provenance': {}})[1] == ['missing_source_or_reference']
    assert attribution({'provenance': {'reference': {'answer': 1}}})[1] == []


def test_only_declared_odd_slot_multiturn_is_source_free():
    p = dict(contract_version=4, family='multiturn', slot=3)
    assert attribution({'provenance': p})[0]['kind'] == 'synthetic_multiturn'
    p['slot'] = 2
    assert attribution({'provenance': p})[1] == ['missing_source_or_reference']
