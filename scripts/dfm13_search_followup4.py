"""One cached-only attempt for three new format failures and one content reject."""
import argparse
import asyncio
from copy import deepcopy
import fcntl
from pathlib import Path

from scripts import dfm13_search_cached_recovery36 as runner

base, prior, pilot = runner.base, runner.prior, runner.pilot
SOURCE = runner.ROOT
ROOT = Path('data/dfm13/search-followup4-20261001')
NOTES = {
 '122a56cc': 'Return normal nonempty final prose. The user asks which service a specific linked article recommends; do not substitute the other linked article or claim the article was read unless its content is in observations. If absent, identify exactly that evidence gap with the relevant observed source URL.',
 'fab29a16': 'Return normal nonempty final prose. Distinguish a described feature from measured user ratings or a verified ranking. Give only supported bookmark/file organization options, cite the supporting observed pages, and state missing rating/privacy/automation details rather than inventing them.',
 'f526f25f': 'Return normal nonempty final prose. Do not promise current sub-$10000 listings, title clearance, safety, renovation profitability or exact drive times without evidence. Separate dated program terms from property-specific facts. Identify missing constraints and cite actual observations. Do not treat a search date filter as historical verification.',
 'b0d5dab9': 'Stay within the requested textbook/grade and exact observed sentences. Do not invent classical quotations or textbook membership to fill every grammar category. A missing category can be marked unverified. Do not infer a classical word meaning from its modern meaning or blindly copy a prior reviewer correction. Support translations and grammar classifications from the excerpts, and cite exact observed URLs. Distinguish sourced examples from unavailable evidence.',
}


def prepare():
    if ROOT.exists():raise ValueError('new isolated root required')
    config=prior.read(SOURCE/'manifest.json')
    jobs=[];pins=dict(config['pins'])
    assessment=[]
    for job in prior.read(SOURCE/'jobs.json'):
        if job['id'][:8] not in NOTES:continue
        outcome_path=SOURCE/'records'/job['id']/'outcome.json'
        outcome=prior.read(outcome_path)
        expected='reject' if job['id'].startswith('b0d5dab9') else 'error'
        if outcome.get('verdict',outcome['status'])!=expected:raise ValueError('unexpected prior outcome')
        evidence=ROOT/'evidence'/(job['id']+'.json')
        base.atomic(evidence,dict(original_evidence=job['evidence'],original_evidence_sha256=base.file_hash(Path(job['evidence'])),
            original_outcome=str(outcome_path),original_outcome_sha256=base.file_hash(outcome_path),
            learner_history_and_observations_unchanged=True,teacher_only_instruction=NOTES[job['id'][:8]],
            original_hold_not_cleared=True,paid_calls=0,provider_calls=0))
        jobs.append(dict(job,evidence=str(evidence)))
        assessment.append(dict(id=job['id'],prior_outcome=outcome,instruction=NOTES[job['id'][:8]]))
        for p in (outcome_path,evidence):pins[str(p.resolve())]=base.file_hash(p)
    if len(jobs)!=4:raise ValueError('four scoped jobs required')
    base.atomic(ROOT/'jobs.json',jobs)
    base.atomic(ROOT/'assessment.json',dict(cases=assessment,
        caution='Chinese reviewer rejection rationale is not an authoritative correction; the answer also invents examples and curriculum claims. Repair targets source support, not replacing an ancient meaning with a modern one.',
        max_attempts=1,paid_calls=0,provider_calls=0,admission_authorized=False))
    for p in (Path(__file__),Path(runner.__file__),ROOT/'jobs.json',ROOT/'assessment.json'):
        pins[str(p.resolve())]=base.file_hash(p)
    base.atomic(ROOT/'manifest.json',dict(config,pins=pins,total=4,max_attempts=1,paid_calls_allowed=0,provider_calls_allowed=0))
    print(str(ROOT/'jobs.json'))


OriginalSession=runner.source.GenerationSession
class FollowupSession(OriginalSession):
    def post(self,*args,**kwargs):
        request=deepcopy(kwargs['json'])
        request['messages'][0]['content']+='\nBounded cached repair: '+NOTES[self.folder.parent.name[:8]]
        request['temperature']=0.35
        kwargs['json']=request
        return super().post(*args,**kwargs)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','run']);args=parser.parse_args()
    if args.command=='prepare':prepare()
    else:
        runner.ROOT=ROOT;runner.source.GenerationSession=FollowupSession
        with (ROOT/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);asyncio.run(runner.run())
