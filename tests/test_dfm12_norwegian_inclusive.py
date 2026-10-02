from copy import deepcopy
import pytest

from dfm12.norwegian_inclusive import adapt, authorized_language
from dfm12.audit_readiness import validate_record, student_views


def reasoning():
    row = {"id": "reasoning-norwegian_0", "source": "reasoning-norwegian", "language": ["nob"],
           "messages": [{"role": "user", "content": "Restore: hallo"}, {"role": "assistant", "content": "Hallo!"}]}
    original = {"corrupt": "hallo", "text_result": "Hallo!", "url": "https://no.wikipedia.org/wiki/Test", "paragraph_number": 0}
    return adapt(row, 0, [original])


def test_unknown_not_false_nb():
    record = reasoning()
    assert record["language"] == "no"
    assert record["norwegian_standard"] == "unknown"
    assert record["provenance"]["source_language"] == ["nob"]
    validate_record(record, ["nb", "nn"])
    assert next(student_views(record)) == {"id": record["id"], "messages": record["messages"]}


@pytest.mark.parametrize("standards", [("bm", "nn"), ("nn", "bm")])
def test_speaker_order_preserved(standards):
    labels = [{"bm": "nob", "nn": "nno"}[s] for s in standards]
    upstream = {"conversation": {"messages": ["Hei!", "Hallo!"], "speakers": [
        {"id": str(i), "orthography": s} for i, s in enumerate(standards)]}}
    row = {"id": "nb-samtale-pairs_conversation_0", "source": "nb-samtale-pairs", "language": labels,
           "messages": [{"role": "user", "content": "Hei!"}, {"role": "assistant", "content": "Hallo!"}]}
    record = adapt(row, 0, upstream)
    assert record["norwegian_standard"] == "mixed"
    assert [s["orthography"] for s in record["speaker_variants"]] == list(standards)
    validate_record(record, ["nb", "nn"])


@pytest.mark.parametrize("field,value", [("norwegian_standard", "nb"), ("message_languages", ["nb", "nb"]),
                                        ("provenance", {}), ("language", "unknown")])
def test_malformed_exception_fails_closed(field, value):
    record = deepcopy(reasoning())
    record[field] = value
    assert not authorized_language(record)
    with pytest.raises(ValueError):
        validate_record(record, ["nb", "nn"])
