from scripts.dfm13_search_targeted_repair_v4 import select_pages

def test_technical_table_retains_context():
    body='Unrelated navigation. '*4000+'\nModel: Example-Base\nMath GSM8K EM 8-shot 89.3\n'+'trailing text '*200
    url='https://example.org/paper'
    pages=select_pages({'data':[dict(url=url,title='Example benchmark',content=body)]},'Example-V3 GSM8K benchmark score')
    assert '8-shot 89.3' in pages[url]['body']
    assert 'Example-Base' in pages[url]['body']
    for chunk in pages[url]['excerpts']:
        assert body[chunk['start']:chunk['end']]==chunk['text']
