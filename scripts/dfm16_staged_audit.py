"""One named target per verdict, aggregated only at whole-conversation level."""
from audit_pipeline import review
from scripts.dfm16_role_pilot import BASE, RULES as ROLE_RULES
RULES=dict(ROLE_RULES,answer_coherence='Inspect ONLY the indicated answer for internally contradictory facts, incoherent chronology, or unintelligible meaning. Respect deliberate changes authorized by the current request. Fictional events are allowed when intelligible.')
from scripts.dfm16_staged_stories import decode
from scripts.dfm16_story_calibration import FocusedAudit


def checks(row):
    messages=row['messages']
    common=dict(language=row['language'],background_seed=row.get('background_seed'),
        authoritative_source=row['source']['text'])
    def make(criterion,target,turn,obligation=None):
        identifier=f'{row["id"]}/{criterion}/{turn}/{obligation or "default"}'
        return dict(id=identifier,audit_id=identifier,parent_id=row['id'],language=row['language'],task=row['task'],criterion=criterion,
            evidence=dict(common,target=target,current_request=messages[turn-1]['content'] if turn is not None and turn%2 else messages[turn]['content'] if turn is not None else None,
                preceding_answers=[m['content'] for m in messages[:turn] if m['role']=='assistant'] if turn is not None else [],
                conversation=messages[:turn+1] if turn is not None else messages,
                obligation=obligation))
    for criterion in ('source_language','source_coherence'):
        yield make(criterion,dict(field='authoritative_source'),None)
    for i,m in enumerate(messages):
        if m['role']=='user':
            yield make('request_validity',dict(field='conversation',turn=i),i)
        else:
            for criterion in ('answer_language','answer_fidelity','answer_coherence'):
                yield make(criterion,dict(field='conversation',turn=i),i)
            obligations = list(row.get('obligations',{}).get(str(i),[]))
            if row['task']=='rewrite':
                obligations.append('Carry out the explicitly requested transformation or correction; an unchanged answer is not valid when a real change is requested.')
            if row['task']=='summary':
                obligations.append('Summarize the main events rather than copying the entire source or answering a different question.')
            if row['task']=='qa':
                obligations.append('Answer the exact current question with information supported by the authoritative source.')
            if row['task']=='creative' or row['task']=='revision' and i==1:
                obligations.append('The story must address the topic explicitly requested by the user.')
            if row['task']=='revision' and i>1:
                obligations.append('Carry out the specific paragraph modification or undo requested in the current user turn.')
            for obligation in obligations:
                yield make('answer_constraint',dict(field='conversation',turn=i),i,obligation)


class StagedAudit(FocusedAudit):
    def prepare(self,row):
        payload=review.payload(row['evidence'],self.model)
        payload['messages'][0]['content']=BASE+'\n'+RULES[row['criterion']]+'''
The authoritative_source is the reviewed source for this task. background_seed
is provenance only: never substitute it for the authoritative source. Target is
exactly the named field/turn. Current requests may legitimately supersede earlier
facts. Intentionally defective correction inputs are not accidental user defects.
Assess all definite grammar errors, not merely severe corruption.'''
        if self.model=='odin-2-large':
            payload.pop('max_tokens');payload.pop('chat_template_kwargs')
            payload.update(reasoning_effort='none',include_reasoning=False,max_completion_tokens=32)
        return payload

    @staticmethod
    def parse_review(body):
        decode(body)  # Reject incomplete or thinking output before strict verdict parsing.
        if body.get('usage',{}).get('completion_tokens',0)>32:raise ValueError('review completion budget exceeded')
        return review.verdict(body)

    async def process(self,item,http,cpu,disk):
        import httpx
        from scripts.dfm16_staged_stories import StagedGenerate,POLICY
        row=item[1];request=await cpu.call(self.prepare,row)
        result=dict(audit_id=row['audit_id'],input_id=row['id'],policy=POLICY,status='unresolved',attempts=[])
        for attempt in range(2):
            record=await disk.call(StagedGenerate.begin,self,row,'review',attempt,request)
            if record is None:
                try:record=dict(response=await http.post(request))
                except httpx.HTTPError as exc:
                    status=exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None
                    record=dict(error=type(exc).__name__,retryable=status is None or status in (408,429,500,502,503,504))
                await disk.call(StagedGenerate.finish_stage,self,row,'review',attempt,request,record)
            result['attempts'].append(record)
            if 'response' not in record:
                if not record.get('retryable'):break
                continue
            try:
                verdict=await cpu.call(self.parse_review,record['response'])
                result.update(status='reviewed',review=verdict);break
            except (ValueError,KeyError,TypeError,IndexError):
                continue
        await disk.call(self.commit,item,result)

    def stage_path(self,row,stage,attempt):
        from scripts.dfm16_staged_stories import StagedGenerate
        return StagedGenerate.stage_path(self,row,stage,attempt)

    def receipt(self,state):
        from scripts.dfm16_staged_stories import POLICY
        from dfm12.io import rows,file_hash
        from scripts.dfm16_story_calibration import sha
        value=super().receipt(state)
        value.update(policy=POLICY,stage_artifacts={str(p.relative_to(self.output)):file_hash(p)
            for r in rows(self.root/state['job']['input'])
            for p in (self.output/'stages'/sha(r['id'])).glob('*.json')})
        return value

    def verify_receipt(self,job,folder):
        from scripts.dfm16_staged_stories import POLICY
        from dfm12.io import load,file_hash
        super().verify_receipt(job,folder)
        receipt=load(folder/'receipt.json')
        if receipt.get('policy')!=POLICY:raise ValueError('changed staged policy')
        for relative,digest in receipt['stage_artifacts'].items():
            if file_hash(self.output/relative)!=digest:raise ValueError('changed completed review stage')
