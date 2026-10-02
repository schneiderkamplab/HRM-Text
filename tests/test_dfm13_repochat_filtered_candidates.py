import json
from scripts import dfm13_repochat_filtered_candidates as c


def test_excludes_manual_hash_and_nonpass(tmp_path,monkeypatch):
    campaign=tmp_path/'campaign'; output=campaign/'filtered'
    monkeypatch.setattr(c.f.n,'ROOT',campaign)
    monkeypatch.setattr(c,'ROOT',output)
    records=[];hold=None
    for i,passed in enumerate([True,True,False]):
        trajectory=tmp_path/f't{i}.json'; review=tmp_path/f'r{i}.json'
        c.b.save(trajectory,{'messages':[{'role':'user','content':'Q'},{'role':'assistant','content':f'A{i}'}]})
        c.b.save(review,{'quality_pass':passed})
        digest=c.b.file_sha(trajectory)
        records.append({'trajectory':str(trajectory),'trajectory_sha256':digest,'review':str(review),
            'review_sha256':c.b.file_sha(review),'review_pass':passed,'task':{'id':str(i),'repository':'repo/test','query':'Q'}})
        if i==1:hold={'trajectory_sha256':digest,'answer_sha256':c.b.sha(b'A1')}
    c.b.save(campaign/'readiness/summary.json',{'records':records})
    c.b.save(campaign/'manual-claim-repairs/holds.json',{'holds':[hold]})
    c.build();c.build()
    rows=[json.loads(x) for x in (output/'candidates.jsonl').read_text().splitlines()]
    assert [x['id'] for x in rows]==['0']
    assert rows[0]['admission'] is False
    assert len(c.b.load(output/'manifest.json')['excluded'])==2
