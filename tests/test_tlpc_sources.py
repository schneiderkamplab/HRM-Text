from dfm12.tlpc_sources import clean, normalize, plan


def article():
    return dict(url='https://example.org/article', title='Example',
        category={'textType': 'Formal'}, content=[{'type': 'p', 'text': 'این یک متن فارسی درباره فناوری و هنر است. ' * 35}])


def test_partition_and_boilerplate():
    row = article()
    row['content'].append({'type': 'p', 'text': 'کپی لینک'})
    result, reason = clean(row)
    assert reason is None and result['removed_element_indices'] == [1]
    assert result['shard'] == int(result['id'][:16], 16) % 8
    assert clean(row)[0] == result


def test_fail_closed():
    for change in ({'qa': [1]}, {'category': {'textType': 'Unk'}}, {'title': 'درمان بیماری'}, {'url': None}):
        row = article(); row.update(change)
        assert clean(row)[0] is None


def test_links_preserved_and_hash_normalized():
    row = article(); row['content'][0]['type'] = 'ilink'
    assert clean(row)[0]['elements'][0]['type'] == 'ilink'
    assert normalize('ك ي  الف') == normalize('ک ی الف')


def test_bounded_plan():
    rows = [dict(path=f'{site}/{i}.jsonl.gz', bytes=100000, lfs_sha256='a'*64)
            for site in ('isna', 'zoomit') for i in range(10)]
    selected = plan(rows, 500000, 3)
    assert sum(r['bytes'] for r in selected) <= 500000
    assert len(selected) == 5
    assert selected == plan(rows, 500000, 3)
