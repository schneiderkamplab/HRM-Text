"""Source-specific gates: no generic-Norwegian fallback or held constituents."""
import pytest

from dfm12.norwegian import DECISIONS, adapt, exact_text, verify_files, verify_upstream, reasoning_language_evidence


def row(name="nb-samtale-pairs", language=None):
    return {"id": name + "_nb-1_0000", "source": name,
            "language": ["nob"] if language is None else language,
            "messages": [{"role": "user", "content": "Hei"},
                         {"role": "assistant", "content": "Hallo"}]}


@pytest.mark.parametrize("label,expected", [(["nob"], "nb"), (["nno"], "nn")])
def test_explicit_variants_stay_unaudited(label, expected):
    result = adapt(row(language=label), "nb-samtale-pairs", 0)
    assert result["language"] == expected
    assert result["accepted"] is False
    assert result["audit_status"] == "unaudited"
    assert result["provenance"]["source_language"] == label


@pytest.mark.parametrize("label", [["no"], ["nor"], ["nob", "nno"], [], ["eng"]])
def test_ambiguous_and_unapproved_variants_rejected(label):
    with pytest.raises(ValueError):
        adapt(row(language=label), "nb-samtale-pairs", 0)


@pytest.mark.parametrize("name", ["reasoning-norwegian", "norquad-wikipedia", "fleurs-alpaca-en-no"])
def test_held_and_excluded_sources_rejected(name):
    with pytest.raises(ValueError, match="hold_or_excluded"):
        adapt(row(name), name, 0)


def test_magpie_nynorsk_not_supported():
    with pytest.raises(ValueError, match="unsupported_magpie_variant"):
        adapt(row("magpie-qwen3-bokmaal", ["nno"]), "magpie-qwen3-bokmaal", 0)


def test_upstream_orthography_and_content_checked():
    upstream = {"nb-1": {"messages": ["Hei", "Hallo"], "speakers": [
        {"id": "a", "orthography": "bm"}, {"id": "b", "orthography": "bm"}]}}
    verify_upstream(row(), "nb-samtale-pairs", upstream)
    upstream["nb-1"]["speakers"][1]["orthography"] = "nn"
    with pytest.raises(ValueError, match="language_mismatch"):
        verify_upstream(row(), "nb-samtale-pairs", upstream)


def test_checksum_tampering_rejected(tmp_path):
    (tmp_path / "file").write_text("changed")
    with pytest.raises(ValueError, match="checksum_mismatch"):
        verify_files(tmp_path, {"files": [{"path": "file", "sha256": "wrong"}]})


def test_screen_is_exact_whitespace_only():
    assert exact_text("a\n  b ") == "a b"
    assert exact_text("A b") != exact_text("a b")


def test_tools_never_flattened():
    r = row()
    r["messages"][1]["tool_calls"] = [{"name": "test"}]
    with pytest.raises(ValueError, match="native_tool"):
        adapt(r, "nb-samtale-pairs", 0)


def test_authorization_removes_license_blockers_preserves_metadata():
    assert all(d["license_blocker"] is False for d in DECISIONS.values())
    assert DECISIONS["reasoning-norwegian"]["license_claims"] == {
        "upstream": "CC-BY-SA-3.0", "composite": "CC-BY-SA-4.0"}
    assert DECISIONS["reasoning-norwegian"]["decision"] == "hold"


@pytest.mark.parametrize("record", [{}, {"language": "no"}, {"language": ["en", "no"]},
                                   {"url": "https://no.wikipedia.org/wiki/Example"}])
def test_authorization_does_not_invent_variant(record):
    assert reasoning_language_evidence(record) is None


@pytest.mark.parametrize("label,expected", [("nob", "nb"), (["nno"], "nn")])
def test_supported_upstream_variant_recognized(label, expected):
    assert reasoning_language_evidence({"language": label}) == expected
