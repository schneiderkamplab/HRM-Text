"""Apply independent candidate-hash holds and prepare CPU-only repair evidence."""
from pathlib import Path
from collections import Counter
from scripts import dfm13_repochat_student25 as cohort

b=cohort.b
REVIEW=Path('docs/reports/dfm13_repochat_native25_manual8_assessment_20261001.json')
ROOT=cohort.ROOT/'independent-disposition-v1'
READS={
 'shamith09/pygyat':[('README.md',75,30),('pygyat/__init__.py',1,30)],
 'selimsef/dfdc_deepfake_challenge':[('README.md',65,30),('training/pipelines/train_classifier.py',20,45)],
 'KhoomeiK/LlamaGym':[('llamagym/agent.py',85,45),('examples/blackjack.py',85,30)],
 'Doomsy1/LIDAR-Car':[('README.md',1,60),('Hardware Programming/main32/platformio.ini',1,60),('Hardware Programming/main8266/platformio.ini',1,60),('Hardware Programming/main8266/src/Lidar8266.cpp',1,100)],
}


def disposition(assessment):
    if assessment.startswith('hard_hold_'):return 'independent_hard_hold'
    if assessment.startswith('useful_partial_'):return 'independent_repair_hold'
    if assessment.startswith('useful_supported'):return 'supported_core_not_admitted'
    raise ValueError('unknown independent assessment')


def verify(pins):
    for pin in pins:
        if b.file_sha(pin['path'])!=pin['sha256']:raise ValueError('independent input pin drift: '+pin['path'])


def sealed(path,document):
    if path.exists() and b.load(path)!=document:raise ValueError('sealed disposition drift')
    if not path.exists():b.save(path,document)


def run():
    receipt=b.load(REVIEW);verify(receipt['pins'])
    dispositions={};evidence=[]
    for row in receipt['rows']:
        verify(row['pins']);state=disposition(row['assessment'])
        candidate_pin=next(p for p in row['pins'] if p['path'].endswith('/candidate.json'))
        snapshot_pin=next(p for p in row['pins'] if p['path'].endswith('/snapshot.json'))
        candidate=b.load(candidate_pin['path']);answer=candidate['messages'][-1]['content']
        dispositions[row['id']]={'id':row['id'],'repository':row['repository'],'candidate':candidate_pin['path'],
             'candidate_sha256':candidate_pin['sha256'],'answer_sha256':b.sha(answer.encode()),'status':state,
             'finding':row['evidence'],'remedy_or_limit':row['correction_or_limit'],'admission':False}
        if state.endswith('_hold'):
            snapshot=Path(snapshot_pin['path']);runtime=cohort.Tools(snapshot.parent/'files',b.load(snapshot));reads=[]
            for path,start,count in READS[row['repository']]:
                lines=runtime.read(path)
                reads.append({'path':path,'file_sha256':b.load(snapshot)['files'][path],
                              'start_line':start,'lines':[f'{i+1}: {lines[i]}' for i in range(start-1,min(len(lines),start-1+count))]})
            evidence.append({'id':row['id'],'repository':row['repository'],'held_candidate_sha256':candidate_pin['sha256'],
                             'snapshot':str(snapshot),'snapshot_sha256':snapshot_pin['sha256'],'reads':reads,
                             'remedy':row['correction_or_limit'],'diagnostic_only':True,'not_retroactively_added_to_student_context':True})
    retry_root=cohort.ROOT/'generation-retry12-v1'
    retry_packet=b.load(retry_root/'manual-packet.json')
    local={r['id']:r for r in retry_packet['additional_local_holds']}
    all_candidates=list(cohort.ROOT.glob('trajectories/*/candidate.json'))+list(retry_root.glob('trajectories/*/candidate.json'))
    for path in all_candidates:
        key=path.parent.name
        if key in dispositions:continue
        candidate=b.load(path);answer=candidate['messages'][-1]['content']
        if key in local and b.sha(answer.encode())!=local[key]['answer_sha256']:raise ValueError('retry hold hash drift')
        dispositions[key]={'id':key,'candidate':str(path),'candidate_sha256':b.file_sha(path),'answer_sha256':b.sha(answer.encode()),
                           'status':'local_review_hold' if key in local else 'independent_review_pending',
                           'finding':local[key]['reason'] if key in local else None,'admission':False}
    if len(dispositions)!=17 or len(all_candidates)!=17:raise ValueError('unexpected candidate population')
    report={'review':str(REVIEW),'review_sha256':b.file_sha(REVIEW),'retry_packet_sha256':b.file_sha(retry_root/'manual-packet.json'),
            'implementation_sha256':b.file_sha(__file__),'counts':dict(Counter(r['status'] for r in dispositions.values())),
            'candidate_count':17,'records':list(dispositions.values()),'admitted':0,'expansion_allowed':False}
    sealed(ROOT/'dispositions.json',report)
    sealed(ROOT/'cpu-repair-evidence.json',{'dispositions_sha256':b.file_sha(ROOT/'dispositions.json'),'cases':evidence,
            'purpose':'Source-verified evidence for four manual findings; no new answer generation or native training-row mutation.',
            'new_gpu_calls':0,'admission':False})
    print(report['counts'])


if __name__=='__main__':run()
