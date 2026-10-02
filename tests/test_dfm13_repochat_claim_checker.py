from scripts import dfm13_repochat_claim_checker as c


def test_fixed_claim_pairs():
    assert len(c.CLAIMS)==3
    assert all(len(pair)==2 and pair[0]!=pair[1] for pair in c.CLAIMS.values())
    assert 'insufficient_evidence' in c.SYSTEM
