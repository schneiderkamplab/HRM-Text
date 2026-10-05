import pytest
from dfm12.wave4_topup_policy import plan
from dfm12.wave4_topup_seeds import passages


def groups():
    return [dict(language=l,family=f,target=t,accepted=0,active=0,attempts=0)
        for l in ['lb','sq','bs','bg','be','fa','hr','hu','sk','sl','sr']
        for f,t in [('grounded',20000),('multi',15000),('oh',15000),('summary',10000),('math',6000),('tools',4000)]]


def test_targets_and_original_attempt_ceiling():
    rows=groups()
    row=next(r for r in rows if r['language']=='lb' and r['family']=='tools')
    row.update(accepted=4000,attempts=22000)
    row=next(r for r in rows if r['language']=='lb' and r['family']=='math')
    row.update(accepted=527,attempts=36000)
    result=plan(rows)
    assert sum(r['target'] for r in result)==735000
    lb=[r for r in result if r['language']=='lb']
    assert sum(r['target'] for r in lb)==35000
    assert next(r for r in lb if r['family']=='tools')['target']==4000
    assert next(r for r in lb if r['family']=='tools')['attempt_limit']==24000
    assert next(r for r in lb if r['family']=='math')['attempt_limit']==72000
    assert all(r['target']>=r['accepted'] for r in result)


def test_active_or_excess_floor_fails_closed():
    rows=groups();rows[0]['active']=1
    with pytest.raises(ValueError):plan(rows)


def test_lb_redistributes_toward_available_recoveries_without_new_gpu():
    rows=groups()
    eligible={(r['language'],r['family']):r['target'] for r in rows}
    eligible[('lb','grounded')]=3000
    result=plan(rows,eligible)
    assert sum(r['target'] for r in result if r['language']=='lb')==35000
    assert all(r['target']<=eligible[(r['language'],r['family'])] for r in result)
    rows=groups()
    for row in rows:
        if row['language']=='lb':row['accepted']=row['target']
    with pytest.raises(ValueError):plan(rows)


def test_passages_preserve_exact_nonoverlapping_text():
    text=('A'*600)+'\n\n'+('B'*700)+'\n\n'+('C'*800)
    selected=list(passages(text,[(0,600)]))
    assert len(selected)==2
    for value,start in selected:
        assert text[start:start+len(value)]==value and start>=600
    assert list(passages('x'*2500,[]))==[]
