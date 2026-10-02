"""Hash-bound manual holds and narrow CPU claim corrections; never admission."""
from pathlib import Path
from scripts import dfm13_repochat_qa_filtered as f

b=f.n.b
MANUAL=Path('data/dfm13/repoqa-pass-manual8-20261001-v1')
ROOT=f.n.ROOT/'manual-claim-repairs'
FIXES={
 'agnaistic/agnai': [
  ('*   **`model/server.py`**: The entry point for the Python service.',
   '*   **`model/app.py`**: Starts the Python service with `app.run` (line 40); `model/server.py` defines the Flask app. `package.json:52-53` launches `model/app.py`.')],
 'NikiFe/IDSHV-router': [
  ('*   **Algorithms:** Breadth-First Search (BFS) implemented for both shortest-path (by station count) and least-transfer routing.',
   '*   **Algorithms:** Station-count routing uses FIFO BFS; least-transfer routing is cost-prioritized (Dijkstra-like), sorting the queue by accumulated `transferCount` in `server.js:140`. The function name/comment alone does not make it ordinary BFS.'),
  ('*   **Data Format:** The API is designed to be compliant with OpenAPI 3.1.0 specifications.',
   '*   **Data Format:** A source comment describes OpenAPI 3.1.0 compliance; this inspection does not validate that claim.')],
 'rockharshitmaurya/OneCode': [
  ('*   **Configuration:** It configures specific connection behaviors, such as forcing a new connection, setting infinite reconnection attempts, and specifying `websocket` as the transport method.',
   '*   **Configuration:** `src/socket.js:5-6` contains malformed keys (`force new connection true` and `reconnectionAttempt`), so those lines do not establish effective forced-new-connection or retry configuration. The documented Socket.IO v4 keys are `forceNew` and `reconnectionAttempts`; infinite attempts are already the documented default. The `websocket` transport setting is present. See https://socket.io/docs/v4/client-options/.')],
}
FILES={
 'agnaistic/agnai':['model/server.py','model/app.py','package.json'],
 'NikiFe/IDSHV-router':['server.js'],
 'rockharshitmaurya/OneCode':['src/socket.js','package.json'],
 'IlanVinograd/OS_32Bit':['Code/Kernel/Sources/paging.c','Code/Kernel/Sources/PCB.c','Code/Kernel/Sources/tasksw.asm'],
 'facebookresearch/dinov2':['dinov2/models/vision_transformer.py'],
}


def prepare():
    report=b.load(MANUAL/'manual-review.json')
    selection=b.load(MANUAL/'selection.json')
    if b.file_sha(f.ROOT/'selection.json')!=selection['source_selection_sha256']:
        raise ValueError('manual population drift')
    samples={s['task']['id']:s for s in selection['samples']}
    holds=[];repairs=[]
    for decision in report['reviews']:
        if decision['recommendation']=='retain':
            continue
        sample=samples[decision['id']]
        for kind in ['trajectory','outcome']:
            if b.file_sha(sample[kind+'_path'])!=sample[kind+'_sha256']:
                raise ValueError('manual candidate drift')
        trajectory=b.load(sample['trajectory_path'])
        answer=f.n.previous.audit.probe.package(trajectory['messages'])['final_answer']
        repo=f.n.ROOT/'repositories'/decision['repository'].replace('/','--')
        snap=b.load(repo/'snapshot.json')
        tools=f.n.previous.generation.RepositoryTools(repo/'files',snap)
        evidence=[]
        for path in FILES[decision['repository']]:
            text=tools.read(path)
            evidence.append({'path':path,'sha256':b.file_sha(repo/'files'/path),'text':text})
        hold={**decision,'trajectory_sha256':sample['trajectory_sha256'],
              'answer_sha256':b.sha(answer.encode()), 'snapshot_sha256':b.file_sha(repo/'snapshot.json'),
              'evidence':evidence, 'hold':True, 'admission':False}
        holds.append(hold)
        if decision['repository'] in FIXES:
            corrected=answer
            for old,new in FIXES[decision['repository']]:
                if corrected.count(old)!=1:
                    raise ValueError('exact localized replacement not unique')
                corrected=corrected.replace(old,new,1)
            repairs.append({'id':decision['id'],'original_answer_sha256':hold['answer_sha256'],
                'corrected_answer':corrected,'corrected_answer_sha256':b.sha(corrected.encode()),
                'claim_edits':FIXES[decision['repository']], 'evidence':evidence,
                'status':'manual_localized_draft_requires_claim_verification',
                'remaining_issue':'Agnai Redis-location review rejection is independent of this entrypoint correction.' if decision['repository']=='agnaistic/agnai' else None,
                'hold_cleared':False,'admission':False})
    if len(holds)!=5 or len(repairs)!=3:
        raise ValueError('expected five holds and three localized corrections')
    pins={str(p):b.file_sha(p) for p in [MANUAL/'manual-review.json',MANUAL/'selection.json',Path(__file__)]}
    b.save(ROOT/'holds.json',{'pins':pins,'holds':holds,'further_scale_allowed':False,'admission':False})
    b.save(ROOT/'localized-repairs.json',{'pins':pins,'repairs':repairs,'admission':False})
    b.save(ROOT/'claim-verification-handoff.json',{'status':'ready_for_claim_to_source_pilot_not_general_positive_review',
        'holds_sha256':b.file_sha(ROOT/'holds.json'),'repairs_sha256':b.file_sha(ROOT/'localized-repairs.json'),
        'required':'Compare each edited claim against exact implementation evidence and official Socket.IO options; test original false claims and corrected claims alongside fresh retain controls. Do not clear whole-answer holds from a claim-level pass.',
        'grounding_concerns_held':['IlanVinograd/OS_32Bit','facebookresearch/dinov2'],'admission':False})
    print({'holds':len(holds),'localized_drafts':len(repairs),'scale':False})


if __name__=='__main__':
    prepare()
