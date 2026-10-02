from pathlib import Path
from scripts import dfm13_repochat_failure_finalization as r


def test_exact_nine_and_all_reads_verified():
    tasks=r.failed_tasks()
    assert len(tasks)==9
    records={x['id']:x for x in r.b.load(r.f.ASSESSMENT)['records']}
    for task in tasks:
        original=r.b.load(r.f.ROOT/'trajectories'/task['id']/'trajectory.json')
        packet=r.evidence_package(task,original)
        assert packet['original_request']==task['query']
        assert packet['retrieved_source']
        assert 'final_answer' not in packet
        record=records[task['id']]
        snapshot=Path(record['snapshot_path'])
        tools=r.f.n.previous.generation.RepositoryTools(snapshot.parent/'files',r.b.load(snapshot))
        for item in record['evidence'][:2]:
            path=str(Path(item['path']).relative_to(snapshot.parent/'files'))
            result=tools.execute('read_file',{'path':path,'start_line':1,'line_count':120})
            assert result.get('lines')
