"""Two bounded, source-contained CPU drafts; no model calls or admission."""
from copy import deepcopy
from pathlib import Path
import jinja2
from tokenizers import Tokenizer
from scripts import dfm13_search_targeted16 as source

ROOT = Path('data/dfm13/search-targeted-cpu2-20261001')
ANSWERS = {
    'deb701de': (
        'The retrieved evidence does not establish a reliable way to install an India-only app while you remain in Italy. '
        'The [Google Play community thread](https://support.google.com/googleplay/thread/270781585/google-play-country-change-issue?hl=en) '
        'states that setting up another Play country requires being there and having a payment method from that country, '
        'and describes a once-per-year change limit. This is a community-thread excerpt, not proof that these were the official rules on April 15, 2025.\n\n'
        'The [Google Help page](https://support.google.com/googleplay/answer/7431675?hl=en-GB) says the old country balance '
        'cannot be used in the new country; it remains linked to the old country and becomes usable there if you switch back.\n\n'
        'Neither excerpt establishes that creating an account through a VPN will work or satisfy eligibility requirements. '
        'Which app do you need? Its exact country availability and the applicable dated country-change conditions are still missing, '
        'so I would not present a VPN or account-creation procedure as verified.'),
    'e19e0b36': (
        'Уточните, пожалуйста, какую страну вы имеете в виду. В полученных материалах есть документы США:\n\n'
        '1. [NIST SP 800-121 Revision 1, Guide to Bluetooth Security]'
        '(https://csrc.nist.gov/csrc/media/publications/sp/800-121/rev-1/final/documents/draft-sp800-121_rev1.pdf). '
        'Это ссылка на найденный PDF; путь содержит draft, поэтому статус окончательной редакции по этому фрагменту не подтвержден.\n'
        '2. [Draft NIST SP 800-121 Rev. 2, Guide to Bluetooth Security]'
        '(https://csrc.nist.gov/files/pubs/sp/800/121/r2/ipd/docs/sp800_121_r2_draft.pdf). '
        'В названии прямо указан черновик.\n\n'
        'В выдержках также перечислены FIPS 199, NIST SP 800-53 и GAO-05-383. Это библиографические ориентиры, '
        'а не подтверждение конкретных требований к Bluetooth. Полученные фрагменты не устанавливают юридическую '
        'обязательность документов или актуальную редакцию на 6 мая 2025 года. Для нормативного ответа нужны '
        'страна, тип организации и полный текст применимых требований.'),
}


def correct(candidate):
    result = deepcopy(candidate)
    result['messages'][-1]['content'] = ANSWERS[candidate['id'][:8]]
    result['admission_authorized'] = False
    result['provenance']['teacher_generated_final'] = False
    result['correction_provenance'] = dict(author='coding_agent_individually_authored',
        parent_content_sha256=source.base.digest(candidate), original_hold_not_cleared=True,
        evidence_and_history_unchanged=True, scope='Remove unsupported workflow/legal-status assertions; keep explicit evidence limitations.')
    return result


def prepare():
    if ROOT.exists():
        raise ValueError('new root required')
    info = source.read(source.pilot.contract.METADATA)['tokenizer_info']
    tokenizer = Tokenizer.from_file(info['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    jobs = []
    for path in sorted((source.ROOT / 'generation/records').glob('*/candidate.json')):
        if path.parent.name[:8] not in ANSWERS:
            continue
        original = source.read(path)
        candidate = correct(original)
        candidate['correction_provenance']['parent_file_sha256'] = source.base.file_hash(path)
        sample = candidate['provenance']['sample']
        checked, _ = source.pilot.contract.strict_row(candidate, sample['prompt'])
        rendering = source.pilot.contract.rendered_targets(checked, tokenizer, template, info, 4096)
        if not all(r['fits_student_context'] for r in rendering):
            raise ValueError('student context exceeded')
        folder = ROOT / 'records' / candidate['id']
        source.base.atomic(folder / 'candidate.json', candidate)
        source.base.atomic(folder / 'student-render.json', rendering)
        jobs.append(dict(id=candidate['id'], candidate=str(folder / 'candidate.json'),
            candidate_sha256=source.base.file_hash(folder / 'candidate.json'), parent=str(path),
            parent_sha256=source.base.file_hash(path), render=rendering,
            independent_review_pending=True, admission_authorized=False))
    if len(jobs) != 2:
        raise ValueError('both expected candidates required')
    source.base.atomic(ROOT / 'queue.json', dict(cases=jobs, paid_calls=0, model_calls=0,
        admission_authorized=False, pins={str(p.resolve()):source.base.file_hash(p) for p in
            (Path(__file__), source.pilot.contract.METADATA, Path(info['tokenizer_path']), Path(info['chat_template_path']))}))
    print(str(ROOT / 'queue.json'))


if __name__ == '__main__':
    prepare()
