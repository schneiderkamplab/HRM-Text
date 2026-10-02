"""V5 scopes tool rubric to tool trajectories; text retains frozen v3 criteria."""
from . import multilingual_review_structured as text_review
from . import multilingual_review_tools as tool_review

VERSION = 'scoped-tool-router-v5'
BULLETS = '\nHyphen bullet lines are valid bullet points unless the request explicitly specifies a different marker.\n'
LITERALS = '''
For numeric evidence, back_translation must be a short English sentence stating
the literal number and relevant request comparison, not bare digits. For JSON,
code or identifiers, describe the literal value, operation or identifier role;
do not merely copy the symbol. This explanation belongs to the REVIEW, not the
candidate. Do not require extra prose in the candidate tool response.
'''


def uses_tools(record):
    return any(message.get('tool_calls') for message in record['messages'])


def request(record):
    if uses_tools(record):
        payload = tool_review.request(record)
        payload['messages'][0]['content'] += LITERALS
    else:
        payload = text_review.request(record)
        payload['messages'][0]['content'] += BULLETS
    return payload


def deterministic_checks(record):
    return (tool_review if uses_tools(record) else text_review).deterministic_checks(record)


def keeps(review, record, deterministic=True):
    if uses_tools(record):
        return tool_review.keeps(review, record, deterministic=deterministic)
    decision = text_review.keeps(review, record)
    # The v3 checker returns only booleans after evidence validation; bypass its
    # structural veto solely for the explicitly labeled reviewer-only report.
    if not deterministic:
        return all(review[key] for key in text_review.FLAGS)
    return decision
