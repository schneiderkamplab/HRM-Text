"""One scoped claim-support repair for six first-audit failures; cache only."""
import argparse
import asyncio
from copy import deepcopy
import fcntl
from pathlib import Path

from scripts import dfm13_search_cached_recovery36 as runner

base, prior, pilot = runner.base, runner.prior, runner.pilot
ROOT = Path('data/dfm13/search-citation-repair6-20261001')
NOTES = {
 'ee694ce0': 'Do not blend different dated tariff snapshots into one current rate. Use only facts applicable by the original date. Cite the actually delivered source URL, not a Reuters or Bloomberg page merely linked inside it. Do not invent a publication date for CSIS. Explain uncertainty rather than predict a certain winner.',
 '6b416b17': 'The prior archive.org/web link was a browsing suggestion, not a source actually retrieved. Do not label it retrieved evidence or a verified historical feature claim. Recommend destinations explicitly supported in delivered excerpts and cite the page that supports the description. Remove unsupported found-footage, Wayback, Sketchfab, or feature claims instead of adding cosmetic citations. Clearly distinguish a linked destination from a page actually read.',
 '99fe14a8': 'Do not transfer Vivo X100 or Meizu 21 Pro capabilities to Meizu 21. Attribute dated reporting as reporting, not a verified current closure or support policy. Do not claim chipset current-generation, emulator performance, inferior camera quality, security-update duration or cheapest price unless supplied evidence establishes it. The price in the user question is a premise, not a verified market comparison.',
 '247e1f93': 'The observations do not establish which Russian FSO number governs these technical conditions. Do not invent mandatory standards, automatically assign exclusive-rights ownership, or apply a Belarus vehicle-valuation code or Russian real-estate standard as the required rule for this sale. Distinguish examples from governing law; state the exact jurisdiction/object/evidence gaps and cite only what the excerpts support.',
 'b528d937': 'All constraints must hold together: Taipei, formerly selected Bib Gourmand, absent in 2024, price below TWD200, and selection year. Do not infer a dish price from cheap-cuisine reputation or recommend a newly selected 2024 restaurant as meeting the exclusion condition. If the cached passages cannot establish a matching restaurant, say so with source links; do not invent names or prices.',
 '64b59e0d': 'Distinguish a third-party claimed score from an official measured score. Do not relabel base-model results as Instruct, infer latest at the historical cutoff, or invent shot settings absent from delivered evidence. Table captions without rows do not establish the numerical result. Cite the actual observed page for every quoted number; explicitly state what remains unverified.',
}


def prepare():
    if ROOT.exists():raise ValueError('new isolated root required')
    config=prior.read(runner.source.ROOT/'manifest.json')
    jobs=[];pins={}
    for path in sorted((runner.source.ROOT/'records').glob('*/candidate.json')):
        key=path.parent.name
        if key[:8] not in NOTES:continue
        outcome=prior.read(path.parent/'outcome.json')
        if outcome.get('verdict')!='needs_verification':raise ValueError('unexpected original outcome')
        candidate=prior.read(path)
        pages={}
        for message in candidate['messages'][:-1]:
            if message['role']=='tool':
                for page in base.strict_json(message['content'])['results']:
                    target=pages.setdefault(page['url'],dict(page,body=''))
                    target['body']+='\n\n'+page['body']
        evidence=ROOT/'evidence'/(key+'.json')
        base.atomic(evidence,dict(original_evidence=candidate['provenance']['evidence'],
            original_evidence_sha256=candidate['provenance']['evidence_sha256'],
            parent_candidate=str(path),parent_candidate_sha256=base.file_hash(path),
            original_history_and_observations_unchanged=True,repair_instruction=NOTES[key[:8]],
            correction_instruction_author='coding_agent_evidence_review',teacher_only_instruction=True,
            instruction_adds_no_answer_facts=True,paid_calls=0,admission_authorized=False))
        jobs.append(dict(id=key,sample=candidate['provenance']['sample'],messages=candidate['messages'][:-1],
            pages=pages,evidence=str(evidence)))
        for p in (path,path.parent/'outcome.json',Path(candidate['provenance']['evidence']),evidence):
            pins[str(p.resolve())]=base.file_hash(p)
    if len(jobs)!=6:raise ValueError('exact six reviewed failures required')
    base.atomic(ROOT/'jobs.json',jobs)
    for p in (Path(__file__),Path(runner.__file__),Path(runner.source.__file__),Path(base.__file__),
        Path(pilot.contract.__file__),Path(pilot.mode.__file__),Path(pilot.bounded.__file__),Path(prior.temporal.__file__),
        ROOT/'jobs.json',pilot.contract.METADATA,Path(config['student_tokenizer_info']['tokenizer_path']),
        Path(config['student_tokenizer_info']['chat_template_path'])):
        pins[str(p.resolve())]=base.file_hash(p)
    base.atomic(ROOT/'manifest.json',dict(**{k:config[k] for k in ('model','endpoints','tokenizer_dir','context_tokens','student_tokenizer_info')},
        pins=pins,total=6,paid_calls_allowed=0,provider_calls_allowed=0,concurrency_per_endpoint=32,
        max_attempts=1,admission_authorized=False,teacher_only_repair_instructions=NOTES))
    print(str(ROOT/'jobs.json'))


OriginalSession=runner.source.GenerationSession
class RepairSession(OriginalSession):
    def post(self,*args,**kwargs):
        request=deepcopy(kwargs['json'])
        key=self.folder.parent.name
        request['messages'][0]['content']+='\nScoped evidence repair: '+NOTES[key[:8]]
        kwargs['json']=request
        return super().post(*args,**kwargs)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','run']);args=parser.parse_args()
    if args.command=='prepare':prepare()
    else:
        runner.ROOT=ROOT
        runner.source.GenerationSession=RepairSession
        with (ROOT/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);asyncio.run(runner.run())
