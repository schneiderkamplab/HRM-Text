import json
import pytest
from scripts.dfm13_search_salvage32 import pages_from_history, ENDPOINT


def test_only_actual_tool_evidence():
    messages=[{'role':'user','content':'https://invented.invalid'},
              {'role':'tool','content':json.dumps({'results':[{'url':'https://source.test','body':'dated clause'}]})}]
    assert pages_from_history(messages)=={'https://source.test':{'url':'https://source.test','title':'','body':'dated clause\n'}}
    assert ':8810/' in ENDPOINT


def test_no_evidence_fails_closed():
    with pytest.raises(ValueError):
        pages_from_history([{'role':'assistant','content':'invented facts'}])
