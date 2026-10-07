"""Evidence extension for new languages/tools; preserve the running v1 contract."""
import json
from dfm14.audit_protocol import POLICY, SYSTEM, validate_review
from dfm14.catalog import LANGUAGES


def messages(row):
    names = dict(LANGUAGES, en='English', fo='Faroese', pl='Polish', fa='Persian')
    payload = dict(language=names[row['language']], task=row['task'],
                   conversation=row['messages'], evidence=row.get('audit_context'))
    if row.get('tools'):
        payload['tools'] = row['tools']
    return [dict(role='system',content=SYSTEM),dict(role='user',content=json.dumps(payload,ensure_ascii=False))]
