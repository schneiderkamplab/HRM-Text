"""Persist individually read, exact-candidate CPU review of ten salvage keeps."""
from pathlib import Path
from scripts import dfm13_search_salvage32 as run

ASSESSMENTS = {
 '454d90e0': ('hold', 'Answer explicitly claims March 2025 availability but uses pages titled 2026, including Qwen3-30B-A3B-Thinking-2507. Current source claims are not evidence of historical availability. Reviewer missed a material date contradiction.'),
 '3e6744b7': ('hold', 'EOIR answer substitutes generic filing/proceedings discussion for Salvadoran eligibility criteria. The official form excerpt ends at "that:" and omits the actual conditions. Acknowledging missing evidence does not make this a complete eligibility answer. Use the existing complete-clause CPU draft for separate assessment, not this automated keep.'),
 'e5913568': ('supported_scoped', 'Read all five observed pages. IE1000 and IE2000/3000/4000/5000 series are explicitly named in the Cisco datasheet; features and qualified management variability are supported. This version corrects prior citation assignment. This is a scoped series overview, not a complete SKU list or historical inventory certification.'),
 '3812a931': ('hold', 'Answer generalizes member-only service to noncommercial/tax-free treatment from simplified secondary excerpts. Municipal observations distinguish affiliation scenarios and the full eligibility conditions are absent. Disclaimer does not restore missing conditions. Do not certify a tax answer from this keep.'),
 '4f8af9d1': ('partial_only', 'Observed official excerpts support 20 mythics, Elspeth and Commander rarity counts. Answer honestly lacks all requested names, so not task-complete. Retrieved article historical availability is not established for March 20. Retain only in an explicitly partial-answer review lane.'),
 'd8174c0d': ('hold', 'March 18 question answered with Guardian March 19 material and NBC text explicitly describing April 2025 dismissals. Also mixes volunteer assessment contributors with government employee firing counts. Concrete temporal/population false accept.'),
 'f911a4e7': ('partial_only', 'Accurately says no MarkText installation-size evidence and limits the comparison to observed VSCode-vs-VisualStudio text. No quantitative answer to requested MarkText-vs-VSCode size comparison. Evidence-gap response, not a successful retrieval answer.'),
 'a9f75ccd': ('hold', '2021 quotation and distinction from the 2023 profile are supported, but answer repeats serious lawsuit allegations while omitting explicit denial available in observations. It also treats the user paraphrase as a literal phrase to locate. Requires balanced, narrowly scoped correction, not automatic keep.'),
 '12490c96': ('supported_scoped', 'Read all four pages. Answer attributes January layoffs and distinguishes organizational context from unknown specific reasons; does not invent internal financial motivation. Facebook reaction is explicitly attributed. Useful scoped explanation of evidence limits, not proof of why the unit was selected.'),
 '70d1096d': ('hold', 'Question may mean diesel share in the manufacturer portfolio, but answer assumes vehicle mass without clarifying. Evidence is a Quora generalization and a 2026 seven-seater page, not diesel-model mass data as of May 2025. Admits missing comparison but does not resolve ambiguity; not a verified substantive answer.'),
}


def main():
    rows=[]
    for job in run.prior.read(run.ROOT/'jobs.json'):
        prefix=job['id'][:8]
        if prefix not in ASSESSMENTS:continue
        folder=run.ROOT/'records'/job['id']
        if run.prior.read(folder/'outcome.json').get('verdict')!='keep':raise ValueError('unexpected disposition')
        decision,reason=ASSESSMENTS[prefix]
        rows.append(dict(id=job['id'],candidate=str(folder/'candidate.json'),candidate_sha256=run.base.file_hash(folder/'candidate.json'),
            automated_outcome_sha256=run.base.file_hash(folder/'outcome.json'),assessment=decision,reason=reason,
            reviewed_against='entire saved final answer, original prompt/as-of and all job pages',admission_authorized=False))
    if len(rows)!=10:raise ValueError('expected ten individually reviewed keeps')
    path=Path('docs/reports/dfm13_search_salvage10_independent_review_20261001.json')
    if path.exists():raise ValueError('immutable receipt exists')
    run.base.atomic(path,dict(rows=rows,summary=dict(supported_scoped=2,partial_only=2,hold=6),
        review_type='CPU agent assessment independent of automated judge; not human certification',
        source_jobs_sha256=run.base.file_hash(run.ROOT/'jobs.json'),original_manual16_unchanged=True,
        existing_holds_not_cleared=True,provider_calls=0,admission_authorized=False))
    print(path)


if __name__=='__main__':main()
