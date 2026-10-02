from scripts import dfm13_search_cpu_corrections_v3 as correction


def test_complete_table_row_without_neighboring_irrelevant_rows():
    body = '| noise | x |\n| target | the complete documented option |\n| unrelated | y |'
    value = correction.evidence_window(body, 'documented option')
    assert value['text'] == '| target | the complete documented option |'
    assert value['text'] == body[value['start']:value['end']]
