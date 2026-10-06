import ast
from tests.test_schedule_dfm13_v2_population_workspace import s as population
from tests.test_schedule_dfm13_wave34_baseline import fixture
from scripts import schedule_dfm13_wave34_baseline as base
from scripts import schedule_dfm13_dala_v2_additions as v2
from scripts import schedule_expanded_dala_v2_averages as avg
from scripts import schedule_expanded_workspace as s


def test_serialized_workspace_and_real_epoch_predicate(tmp_path,monkeypatch):
    jobs,r=fixture();r['dfm'][0]['name']='dala_lt';jobs=base.build(jobs,r)
    tasks=[dict(name='dala_v2_da',suite='dala_v2_da',config='/new',language='da',max_tokens=32,shards=4)]
    jobs=v2.build(jobs,tasks,tmp_path/'p')
    monkeypatch.setattr(population,'file_hash',lambda p:'sha')
    monkeypatch.setattr(avg,'file_hash',lambda p:'sha')
    monkeypatch.setattr(s,'file_hash',lambda p:'sha')
    jobs=population.build(jobs);jobs=avg.build(jobs);out=s.build(jobs);by={j.job_id:j for j in out}
    assert by[s.ID].deps==(s.BASELINE,population.ID)
    assert s.ID in by['old-3200000-wait'].deps
    assert str(population.MAPPING) in by[population.ID].metadata['source_pins']
    # Evaluate the actual installed segment's filter, not a copied approximation.
    tree=ast.parse((s.ROOT/'scripts/schedule_dfm13_xl_handoff.py').read_text())
    segment=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='segment')
    expr=next(n.test for n in ast.walk(segment) if isinstance(n,ast.IfExp) and 'startswith' in ast.unparse(n.test))
    predicate=compile(ast.Expression(expr),'segment-filter','eval')
    for j in out:
        if j.metadata.get(avg.FLAG) and base.boundary(j)>=3200000:
            assert eval(predicate,{'j':j,'PREFIX':'dfm13-xl-','tag':j.metadata['ckpt_tag'],'Action':s.Action})
