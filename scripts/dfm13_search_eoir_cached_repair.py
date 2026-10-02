"""One CPU-authored EOIR draft using complete cached USCIS clauses."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import jinja2
from tokenizers import Tokenizer

from scripts import dfm13_search_targeted16 as parent

ROOT = Path('data/dfm13/search-eoir-cached-repair-20261001-v2')
KEY = '3e6744b772096d0d9ab76d8054e8a55dcf8687bd86e031ef3fa25ad8eae63e0a'
URL = 'https://www.uscis.gov/sites/default/files/document/forms/i-881instr.pdf'
SOURCE = parent.ROOT / 'retrieval' / KEY / 'full-cache.json'
CANDIDATE = parent.ROOT / 'generation/records' / KEY / 'candidate.json'
ASSESSMENT = Path('docs/reports/dfm13_search_targeted16_keeps_review_20261001.json')

SECTIONS = (
    ('purpose_and_non_nacara_forms', '# What Is the Purpose of Form I-881?', 'WARNING:'),
    ('salvadoran_abc_class_and_forum', '# Who May File Form I-881?', '2.  A Guatemalan national who:'),
    ('alternative_asylum_class_and_forum', '3.  A Guatemalan or Salvadoran national', '4.  An alien who:'),
    ('court_only_clause_complete_scope', '6.  An alien who has been battered', '# Who May Be Eligible to Be Granted Relief?'),
    ('substantive_standards_and_exceptions', '# Who May Be Eligible to Be Granted Relief?', '# Who Is Not Eligible for Relief by USCIS?'),
    ('uscis_eoir40_legacy_exception', 'Form EOIR-40, Application for Suspension of Deportation, will not be accepted', 'If you are filing Form I-881 or Form EOIR-40 with USCIS'),
    ('court_eoir40_legacy_exception', 'If you filed Form EOIR-40, Application for Suspension of Deportation, before June 21, 1999, you do not need', '# Employment Authorization'),
)

ANSWER = """Nationality alone does not establish eligibility, and it is important to distinguish **EOIR-40** from the **NACARA Form I-881** route. The cached [USCIS I-881 instructions](https://www.uscis.gov/sites/default/files/document/forms/i-881instr.pdf), marked 01/20/25, make these distinctions:

**Which form?** For NACARA section 203 relief, the instructions generally call for I-881. They say the Immigration Court will not accept EOIR-40 for NACARA applications after June 21, 1999, except that someone who filed EOIR-40 before that date need not file I-881. The USCIS exception differs: an otherwise eligible applicant with a pre-June-21-1999 EOIR-40 may submit that form together with the first page of I-881. Outside NACARA, the purpose section distinguishes EOIR-40 in deportation proceedings from EOIR-42B in removal proceedings; it does not supply every eligibility requirement for those separate routes.

**For the Salvadoran NACARA categories described here**, the instructions require no aggravated-felony conviction and identify, among other categories:
- Entry by September 19, 1990, ABC registration by October 31, 1991 (directly or through a TPS application), and no apprehension at entry after December 19, 1990.
- Alternatively, a Guatemalan or Salvadoran national who applied for asylum by April 1, 1990.

These category descriptions are not sufficient by themselves for a grant. For the specified Part 2 categories, the instructions describe seven years of continuous presence, good moral character during those years, and extreme hardship to the applicant or specified US-citizen/permanent-resident family members. They also describe different or higher standards for some cases. Filing with USCIS versus the court depends on the category and procedural history; the court-only clause in the excerpt concerns the specified battered-spouse/child category, not every NACARA applicant.

So the next facts to clarify are whether this is a NACARA claim, whether an EOIR-40 was filed before June 21, 1999, and whether the person is in deportation or removal proceedings. This is a limited explanation of the supplied instructions, not a determination of anyone's eligibility. An immigration lawyer or accredited representative should assess the complete history and applicable requirements before filing."""


def extract(body):
    chunks = []
    for name, start_anchor, end_anchor in SECTIONS:
        if body.count(start_anchor) != 1:
            raise ValueError('missing or ambiguous section: '+name)
        start = body.index(start_anchor)
        end = body.find(end_anchor, start + len(start_anchor))
        if end < 0:
            raise ValueError('missing section end: '+name)
        chunks.append(dict(section=name, start=start, end=end, text=body[start:end],
            url=URL, full_content_sha256=hashlib.sha256(body.encode()).hexdigest()))
    marker = 'Form I-881 Instructions 01/20/25 Page 10 of 12'
    if marker not in body:
        raise ValueError('source edition marker absent')
    start = body.index(marker)
    chunks.append(dict(section='source_edition_marker', start=start, end=start+len(marker), text=marker,
        url=URL, full_content_sha256=hashlib.sha256(body.encode()).hexdigest()))
    return chunks


def prepare():
    if ROOT.exists():
        raise ValueError('new isolated root required')
    original = parent.read(CANDIDATE)
    review = next(x for x in parent.read(ASSESSMENT)['rows'] if x['id'] == KEY)
    if parent.base.file_hash(CANDIDATE) != review['candidate_sha256']:
        raise ValueError('reviewed candidate changed')
    payload = parent.read(SOURCE)
    page = next(p for p in payload['data'] if p['url'] == URL)
    chunks = extract(page['content'])
    candidate = deepcopy(original)
    observation = parent.base.strict_json(candidate['messages'][-2]['content'])
    observation.update(provider='jina_cached_complete_clause_selection',
        note='Complete cached sections selected with headings and exceptions; omissions between sections. No new search. Not the complete legal eligibility framework.',
        results=[dict(url=URL, title=page['title'], body='\n\n[Omitted material between selected sections]\n\n'.join(c['text'] for c in chunks))],
        source_edition_marker='Form I-881 Instructions 01/20/25',
        evidence_scope='Distinguish NACARA I-881 from EOIR-40; preserve limited exceptions and category-specific jurisdiction.',
        publication_dates_not_verified=True)
    candidate['messages'][-2]['content'] = json.dumps(observation, ensure_ascii=False)
    candidate['messages'][-1]['content'] = ANSWER
    candidate['provenance']['teacher_generated_final'] = False
    evidence = ROOT / 'evidence.json'
    parent.base.atomic(evidence, dict(chunks=chunks, full_cache=str(SOURCE), full_cache_sha256=parent.base.file_hash(SOURCE),
        source_url=URL, source_asof=original['provenance']['sample']['original_timestamp'],
        existing_query=observation['query'], source_edition_marker='01/20/25',
        raw_cache_reused=True, new_paid_calls=0, no_hidden_teacher_facts=True,
        source_edition_is_not_independent_historical_snapshot_verification=True))
    candidate['provenance'].update(evidence=str(evidence), evidence_sha256=parent.base.file_hash(evidence))
    candidate['correction_provenance'] = dict(author='coding_agent_individually_authored', parent=str(CANDIDATE),
        parent_sha256=parent.base.file_hash(CANDIDATE), assessment_sha256=parent.base.file_hash(ASSESSMENT),
        original_hold_not_cleared=True, original_user_and_native_call_unchanged=True,
        new_branch='replace last controller observation with complete cached clauses, then CPU-authored final',
        paid_calls=0, model_calls=0, admission_authorized=False)
    info = parent.read(parent.pilot.contract.METADATA)['tokenizer_info']
    tokenizer = Tokenizer.from_file(info['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    checked, _ = parent.pilot.contract.strict_row(candidate, original['provenance']['sample']['prompt'])
    rendering = parent.pilot.contract.rendered_targets(checked, tokenizer, template, info, 4096)
    if not all(r['fits_student_context'] for r in rendering):
        raise ValueError('complete evidence plus answer exceeds student context; no truncation')
    folder = ROOT / 'records' / KEY
    parent.base.atomic(folder / 'candidate.json', candidate)
    parent.base.atomic(folder / 'student-render.json', rendering)
    pins = {str(p.resolve()):parent.base.file_hash(p) for p in
        (Path(__file__), SOURCE, CANDIDATE, ASSESSMENT, evidence, folder / 'candidate.json',
         parent.pilot.contract.METADATA, Path(parent.pilot.contract.__file__),
         Path(info['tokenizer_path']), Path(info['chat_template_path']))}
    parent.base.atomic(ROOT / 'queue.json', dict(cases=[dict(id=KEY, candidate=str(folder / 'candidate.json'),
        candidate_sha256=parent.base.file_hash(folder / 'candidate.json'), evidence=str(evidence), render=rendering,
        independent_review_pending=True, admission_authorized=False)], pins=pins, paid_calls=0, model_calls=0,
        review_instructions='Check form/relief distinctions, category scope, legacy exceptions and complete evidence. No automatic keep; no legal eligibility determination.'))
    print(json.dumps(dict(queue=str(ROOT / 'queue.json'), render=rendering)))


if __name__ == '__main__':
    prepare()
