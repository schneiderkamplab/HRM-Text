from scripts import dfm13_repochat_manual_claim_repairs as r


def test_hash_bound_holds_and_localized_drafts():
    holds=r.b.load(r.ROOT/'holds.json')
    repairs=r.b.load(r.ROOT/'localized-repairs.json')
    assert len(holds['holds'])==5 and holds['further_scale_allowed'] is False
    assert len(repairs['repairs'])==3
    assert all(x['hold'] and not x['admission'] for x in holds['holds'])
    for row in repairs['repairs']:
        assert r.b.sha(row['corrected_answer'].encode())==row['corrected_answer_sha256']
        assert row['hold_cleared'] is False
