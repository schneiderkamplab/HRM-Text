from scripts.diagnose_hr_transform_structure import classify


def test_short_real_prose_is_not_heading():
    c = classify('Rod je opisan 1948.\n\nOženio je kćerku Amédée Moucheza.\n\nIzvori')
    assert c['detected_prose_blocks'] == 2


def test_one_prose_plus_furniture():
    c = classify('Rođen je u Zagrebu 1821. godine.\n\nIzvori\n\nHrvatski operni pjevači\nŽivotopisi, Križevci\nEnologija')
    assert c['classification'] == 'below_two_furniture_only_remainder'


def test_unknown_short_lines_are_not_certified_categories():
    c = classify('Neobična taksonomija\nDruga stavka\n\nIzvori')
    assert c['classification'] == 'below_two_with_unresolved_or_list_blocks'


def test_discography_preserved_as_meaningful_list():
    c = classify('Diskografija\nMojim prijateljima (1974)\nAlbum (1980)\n\nIzvori')
    assert c['flags']['meaningful_list_detected']
    assert c['unresolved_or_list_blocks'] == 1


def test_citations_not_prose_but_annotated_references_uncertain():
    c = classify('Vanjske poveznice\nurednik: Pjevač je rođen 1821. prigorski.hr, 2016.')
    assert c['detected_prose_blocks'] == 0
    assert c['blocks'][0]['kind'] == 'reference_furniture'
    assert classify('Izvori\nOva knjiga je opsežna studija.')['blocks'][0]['kind'] == 'uncertain_reference'


def test_only_last_block_can_be_category_tail():
    c = classify('Hrvatski pjesnici\n\nTekst je objavljen jučer.')
    assert c['blocks'][0]['kind'] == 'unresolved'


def test_infobox_is_unresolved_not_prose():
    assert classify('{{Infookvir\n| opis = Ovo je tekst.\n}}')['detected_prose_blocks'] == 0


def test_year_opening_narrative_is_not_numbered_list():
    c = classify('1902. sudjelovao je u mjerenjima. Godine 1904. postao je član akademije.')
    assert c['detected_prose_blocks'] == 1


def test_croatian_day_month_opening_is_not_numbered_list():
    c = classify('1. lipnja 2008. Postiga je potpisao ugovor.\n\n31. kolovoza 2011. kupuje ga novi klub. Igrao je u Španjolskoj.')
    assert c['detected_prose_blocks'] == 2


def test_link_furniture_is_not_category_heading_only():
    c = classify('Vanjske poveznice\nhttps://example.hr/clanak\n\nHrvatski književnici')
    assert c['flags']['recognized_furniture_only']
    assert not c['flags']['recognized_category_heading_only']
