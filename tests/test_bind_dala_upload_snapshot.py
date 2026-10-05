import copy
import pytest
from scripts.bind_dala_upload_snapshot import verify


def fixture():
    items=[dict(integration=dict(path=str(i),sha256='hash'+str(i)),
        train_components=[dict(name=str(i)+t,rows=2,tokens=10) for t in ('la','gec')]) for i in range(9)]
    return (dict(items=items),dict(success=True,group_integrations={str(i):'hash'+str(i) for i in range(9)}),
            dict(additions=[c for i in items for c in i['train_components']]))


def test_exact_binding():
    result=verify(*fixture())
    assert result['components']==18 and result['training_rows']==36


@pytest.mark.parametrize('mutation',['pin','component','duplicate'])
def test_changed_snapshot_refused(mutation):
    q,c,r=[copy.deepcopy(x) for x in fixture()]
    if mutation=='pin':c['group_integrations']['0']='changed'
    elif mutation=='component':r['additions'][0]['tokens']+=1
    else:r['additions'].append(r['additions'][0])
    with pytest.raises(ValueError):verify(q,c,r)
