"""Zero-shot, evaluation-only Inspect adapter for the pinned Danish semantic suite."""
import hashlib,json
from pathlib import Path
from inspect_ai import Task,task
from inspect_ai.dataset import Sample,MemoryDataset
from inspect_ai.scorer import Score,scorer,mean,stderr
from inspect_ai.solver import generate
FAMILIES=('inference','entailment','danwic','synonymy','similarity','sentiment','dameta')
DEFAULT=Path(__file__).resolve().parent/'data/danish_semantic_reasoning'


def parse_answer(text,labels):
    answer=text.strip().casefold()
    if answer.endswith(('.', '!')):answer=answer[:-1].strip()
    # Exact whole-answer matching: never accept a label mentioned in an explanation.
    return next((label for label in labels if answer==label.casefold()),None)


@scorer(metrics={'accuracy':[mean(),stderr()],'valid_format':[mean()]})
def semantic_score():
    async def score(state,target):
        answer=parse_answer(state.output.completion,state.metadata['labels'])
        return Score(value={'accuracy':int(answer==target.text),'valid_format':int(answer is not None)},answer=answer or '',explanation='Exact allowed-label match; invalid answers count as incorrect.')
    return score


@task
def danish_semantic_reasoning(family:str='inference',subset:str='',data_dir:str=str(DEFAULT),num_shards:int=1,shard_index:int=0):
    if family not in FAMILIES:raise ValueError(f'family must be one of {FAMILIES}')
    if family=='danwic' and not subset:subset='danwic_poly_selection'
    if num_shards<1 or not 0<=shard_index<num_shards:raise ValueError('invalid shard')
    root=Path(data_dir);raw=(root/'records.jsonl').read_bytes();manifest=json.loads((root/'manifest.json').read_text())
    if hashlib.sha256(raw).hexdigest()!=manifest['records_sha256']:raise ValueError('evaluation data hash mismatch')
    records=[json.loads(line) for line in raw.splitlines()]
    records=[r for r in records if r['family']==family and (not subset or r['subset']==subset)]
    if not records:raise ValueError('empty family/subset')
    samples=[Sample(id=r['id'],input=r['input'],target=r['target'],metadata={**r['metadata'],'labels':r['labels'],'family':family,'subset':r['subset'],'upstream_revision':manifest['upstream_revision']}) for r in records[shard_index::num_shards]]
    return Task(dataset=MemoryDataset(samples,name='danish_semantic_'+family),solver=[generate(max_tokens=16,temperature=0)],scorer=semantic_score())
