"""Isolated semantic rubric experiment; no production installation or recovery."""
from . import wave_compact_review as baseline

PROMPT = baseline.PROMPT + '''
Decision procedure: identify the actual requested task and assess the whole answer
against the supplied evidence. A material observed mistake, mistranslation, typo,
missing requested element, unsupported concrete assertion or changed qualification
is already assessable: choose repair for a bounded assistant fix, or reject when
the input/task is unusable. Do NOT label an observed defect needs_verification.
Use needs_verification only when a SPECIFIC ESSENTIAL fact is unavailable and
that absence genuinely prevents deciding the answer's correctness; name that fact.
Ordinary uncertainty about fluency, an awkward phrase, or an error you can already
identify is not an essential missing fact. Do not invent an external verification
requirement for a source-bound extraction or rewrite.
Do not demand a complete article summary when the user asks for a selected fact,
or elaboration when a short answer fulfills the task. Harmless source/user typos
that do not obscure the task are not assistant errors. Do not silently correct
material source errors or approve unsupported assistant additions. All material
assertions the assistant actually makes still require appropriate support, even
when not expressly requested. Distinguish stylistic preference from a genuine
language or meaning defect. If no material defect or essential missing fact exists,
keep. A keep is not a promise of independent factual or native-language certification.
'''

schema = baseline.schema
validate = baseline.validate
keeps = baseline.keeps
deterministic_checks = baseline.deterministic_checks


def request(record, model=baseline.MODEL):
    payload = baseline.request(record, model)
    payload['messages'][0]['content'] = PROMPT
    return payload
