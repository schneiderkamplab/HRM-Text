"""One fresh native retry of twelve generation failures; no successful-row replay."""
import asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
from pathlib import Path
from types import SimpleNamespace
from scripts import dfm13_repochat_student25 as old

b=old.b
ROOT=old.ROOT/'generation-retry12-v1'
SYSTEM=old.SYSTEM+'''
The repository IS mounted and available through these tools; do not ask the user
to upload it. Start list_files with prefix="", after="". Prefix "." or "./"
also means the root. Listings show immediate files and subdirectories, so inspect
useful directories rather than paging through dotfiles. A prefix is a path prefix,
not a filename search. Search source terms to locate relevant lines before reading
long files sequentially. read_file line_count must be at most 30, never 50.
Keep a final-answer budget; use no more than eight tool rounds. Cite only evidence
actually retrieved. A missing search result is not proof a feature is absent.'''


class Tools(old.Tools):
    def execute(self,name,args):
        args=dict(args)
        if name in ('list_files','search_repository'):
            if args.get('prefix') in ('.','./'):args['prefix']=''
            if isinstance(args.get('prefix'),str) and args['prefix'].startswith('./'):args['prefix']=args['prefix'][2:]
        if name=='list_files':
            old.jsonschema.validate(args,old.TOOLS[0]['function']['parameters'])
            prefix=args['prefix'];prefix=prefix if not prefix or prefix.endswith('/') else prefix+'/'
            entries=set()
            for path in self.receipt['files']:
                if path.startswith(prefix):
                    rest=path[len(prefix):];entries.add(prefix+rest.split('/')[0]+('/' if '/' in rest else ''))
            after='' if args['after'] in ('.','./') else args['after']
            entries=sorted(x for x in entries if x>after);page=entries[:20]
            return {'paths':[x for x in page if not x.endswith('/')], 'directories':[x for x in page if x.endswith('/')],
                    'next_after':page[-1] if len(entries)>20 else None,'resolved_prefix':prefix}
        return super().execute(name,args)


def prepare():
    ready=old.prepare();selected=[];diagnosis=[];protected={}
    for record in ready['records']:
        task=record['task'];folder=old.ROOT/'trajectories'/task['id'];outcome=b.load(folder/'outcome.json')
        if outcome['status']!='failed':
            for path in folder.glob('*.json'):protected[str(path)]=b.file_sha(path)
            continue
        trajectory=b.load(folder/'trajectory.json');error=outcome['error']
        calls=[c for m in trajectory['messages'] for c in m.get('tool_calls',[])]
        if 'final_without_repository_evidence' in error:
            bucket='context_absence_response_without_tools' if not calls else 'root_prefix_or_path_misunderstanding'
        elif 'tool_round_budget' in error:bucket='tool_round_exhaustion'
        elif 'student_budget_exhausted' in error:bucket='student_context_exhaustion'
        elif error.startswith('ValidationError: 50'):bucket='read_count_schema_error'
        else:raise ValueError('unapproved retry failure:'+error)
        diagnosis.append({'task':task,'bucket':bucket,'original_error':error,'trajectory_sha256':b.file_sha(folder/'trajectory.json'),
                          'outcome_sha256':b.file_sha(folder/'outcome.json'),'retry_basis':'fixable generation/tool ergonomics; no semantic review rejection','admission':False})
        selected.append(record)
    if len(selected)!=12 or len(protected)==0:raise ValueError('unexpected source population')
    result={'records':selected,'diagnosis':diagnosis,'buckets':dict(Counter(x['bucket'] for x in diagnosis)),
            'infrastructure_failures':0,'output_length_failures':0,'policy_refusals_observed':0,
            'protected_successful_artifacts':protected,'original_ready_sha256':b.file_sha(old.ROOT/'ready.json'),
            'implementation_sha256':b.file_sha(__file__),'attempts_per_case':1,'per_endpoint':8,'admission':False}
    if (ROOT/'ready.json').exists() and b.load(ROOT/'ready.json')!=result:raise ValueError('retry pin drift')
    b.save(ROOT/'ready.json',result);b.save(ROOT/'selection.json',{'tasks':[r['task'] for r in selected],'admission':False})
    return result


async def run():
    import aiohttp
    ready=prepare();student=old.Student();gates=[asyncio.Semaphore(8) for _ in range(8)]
    asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=8))
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),connector=aiohttp.TCPConnector(force_close=True)) as session:
        async def case(i,record):
            task=record['task'];out=ROOT/'trajectories'/task['id']
            if (out/'outcome.json').exists():return b.load(out/'outcome.json')
            tools=Tools(Path(record['snapshot']).parent/'files',b.load(record['snapshot']))
            messages=[{'role':'system','content':SYSTEM},{'role':'user','content':task['query']}]
            observations=[];seen=set();evidence=False;result={'status':'failed','admission':False}
            try:
                for turn in range(9):
                    if await asyncio.to_thread(student.count,messages)+768>4096:raise ValueError('student_budget_exhausted_no_truncation')
                    if turn==8 and not evidence:raise ValueError('no_evidence_at_final_round')
                    payload={'model':'dfm13-gemma4','messages':messages,'tools':old.TOOLS,'tool_choice':'none' if turn==8 else 'auto','temperature':0.1,'max_tokens':1024,'chat_template_kwargs':{'enable_thinking':False}}
                    await asyncio.to_thread(b.save,out/f'request-{turn:02}.json',payload)
                    async with gates[i%8]:
                        async with session.post(f'http://localhost:{8800+i%8}/v1/chat/completions',json=payload) as response:
                            response.raise_for_status();raw=await response.json()
                    await asyncio.to_thread(b.save,out/f'response-{turn:02}.json',raw)
                    choice=raw['choices'][0];m=choice['message'];message={'role':'assistant','content':m.get('content') or ''}
                    if m.get('tool_calls'):message['tool_calls']=m['tool_calls']
                    messages.append(message);rendering=await asyncio.to_thread(student.targets,messages)
                    if not all(r['fits_student_context'] for r in rendering):raise ValueError('student_target_oversize_no_truncation')
                    calls=m.get('tool_calls') or []
                    if not calls:
                        if choice['finish_reason']!='stop' or not message['content'].strip():raise ValueError('incomplete_final:'+str(choice['finish_reason']))
                        if not evidence:raise ValueError('final_without_repository_evidence')
                        old.strict(messages);result={'status':'generated_pending_review','admission':False};break
                    if choice['finish_reason'] not in ('stop','tool_calls') or len(calls)>2:raise ValueError('invalid_tool_completion')
                    for call in calls:
                        if call['id'] in seen:raise ValueError('duplicate_call_id')
                        seen.add(call['id']);name=call['function']['name'];args=json.loads(call['function']['arguments'])
                        value=await asyncio.to_thread(tools.execute,name,args);content=b.canonical(value).decode()
                        evidence |= bool(value.get('lines') or value.get('matches'))
                        observations.append({'call_id':call['id'],'name':name,'arguments':args,'result':value,'result_sha256':b.sha(content.encode()),'snapshot_sha256':record['snapshot_sha256']})
                        messages.append({'role':'tool','tool_call_id':call['id'],'content':content})
                else:raise ValueError('tool_round_budget')
                await asyncio.to_thread(b.save,out/'student-render.json',rendering)
                replay=Tools(Path(record['snapshot']).parent/'files',b.load(record['snapshot']))
                for item in observations:
                    if replay.execute(item['name'],item['arguments'])!=item['result']:raise ValueError('source_replay_mismatch')
                await asyncio.to_thread(b.save,out/'candidate.json',{'messages':messages,'tools':old.TOOLS,'target_message_indices':[r['target_message_index'] for r in rendering]})
            except Exception as exc:result={'status':'failed','error':f'{type(exc).__name__}: {exc}','admission':False}
            await asyncio.to_thread(b.save,out/'trajectory.json',{'task':task,'messages':messages,'tools':old.TOOLS,'incomplete':result['status']=='failed','admission':False})
            await asyncio.to_thread(b.save,out/'provenance.json',{'snapshot':record['snapshot'],'snapshot_sha256':record['snapshot_sha256'],'observations':observations,'original_source_index':task['source_index'],'original_ready_sha256':ready['original_ready_sha256'],'student_tools_semantics_sha256':ready['implementation_sha256'],'admission':False})
            await asyncio.to_thread(b.save,out/'outcome.json',result);print(json.dumps({'id':task['id'],**result}),flush=True);return result
        outcomes=await asyncio.gather(*(case(i,r) for i,r in enumerate(ready['records'])))
    b.save(ROOT/'summary.json',{'selected':12,'statuses':dict(Counter(o['status'] for o in outcomes)),'errors':dict(Counter(o.get('error') for o in outcomes if o['status']=='failed')),'admission':False})
    await old.audit.run(SimpleNamespace(source=ROOT,root=ROOT/'whole-answer-review',ids=None,thinking=True))
    for path,digest in ready['protected_successful_artifacts'].items():
        if b.file_sha(path)!=digest:raise ValueError('protected successful artifact changed')
    b.save(ROOT/'completion.json',{'summary_sha256':b.file_sha(ROOT/'summary.json'),'review_sha256':b.file_sha(ROOT/'whole-answer-review/summary.json'),'protected_13_unchanged':True,'admission':False})


if __name__=='__main__':
    ROOT.mkdir(parents=True,exist_ok=True)
    with (ROOT/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);asyncio.run(run())
