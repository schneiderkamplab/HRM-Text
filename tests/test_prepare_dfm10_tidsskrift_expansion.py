from xml.etree import ElementTree as ET

import requests

from scripts.prepare_dfm10_tidsskrift_expansion import (
    classify_license,
    parse_record,
    remove_exact_abstract,
    target_leaks_into_prompt,
    request_xml,
)


def test_license_classification_is_fail_closed() -> None:
    assert classify_license("https://creativecommons.org/licenses/by/4.0", "") == "cc-by"
    assert classify_license("https://creativecommons.org/licenses/by-sa/4.0", "") == "cc-by-sa"
    assert classify_license("https://creativecommons.org/licenses/by-nc-nd/4.0", "") == "restricted-cc"
    assert classify_license("", "free access") == "unknown"


def test_parse_jats_record_preserves_rights_and_links() -> None:
    record = ET.fromstring(
        """
        <record xmlns:xlink="http://www.w3.org/1999/xlink">
          <header><identifier>oai:test:1</identifier><datestamp>2026-01-01</datestamp><setSpec>journal:ART</setSpec></header>
          <metadata><article xml:lang="da">
            <journal-meta><journal-id>journal</journal-id><journal-title>Et tidsskrift</journal-title></journal-meta>
            <article-meta>
              <article-id pub-id-type="publisher-id">1</article-id>
              <title-group><article-title>En titel</article-title></title-group>
              <contrib-group><contrib><name><given-names>Anne</given-names><surname>Andersen</surname></name></contrib></contrib-group>
              <permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0"><license-p>CC BY</license-p></license></permissions>
              <self-uri xlink:href="https://tidsskrift.dk/journal/article/view/1?x=1" />
              <self-uri content-type="application/pdf" xlink:href="https://tidsskrift.dk/journal/article/download/1/2" />
              <abstract><p>Et dækkende resumé.</p></abstract>
            </article-meta>
          </article></metadata>
        </record>
        """
    )
    row = parse_record(record)
    assert row is not None
    assert row["oai_id"] == "oai:test:1"
    assert row["license_class"] == "cc-by"
    assert row["article_url"] == "https://tidsskrift.dk/journal/article/view/1"
    assert row["pdf_url"].endswith("/article/download/1/2")
    assert row["authors"] == ["Anne Andersen"]
    assert row["abstract"] == "Et dækkende resumé."


def test_exact_abstract_is_removed_from_pdf_text() -> None:
    abstract = (
        "Dette er et tilstrækkeligt langt resumé med mange ord som skal fjernes "
        "fra selve artiklens tekst uden at fjerne brødteksten omkring det."
    )
    article = f"Titel\n\nResumé\n{abstract}\n\nIndledning\nDette er brødteksten."
    cleaned, removed = remove_exact_abstract(article, abstract)
    assert removed
    assert abstract not in cleaned
    assert "Dette er brødteksten" in cleaned


def test_abstract_removal_tolerates_pdf_punctuation_changes() -> None:
    abstract = " ".join(f"ord{i}" for i in range(30))
    rendered = ", ".join(f"ord{i}" for i in range(30))
    article = f"Titel\n\nAbstract: {rendered}\n\nBrødtekst følger her."
    cleaned, removed = remove_exact_abstract(article, abstract)
    assert removed
    assert "Brødtekst følger her" in cleaned
    assert not target_leaks_into_prompt(cleaned, abstract)


def test_residual_abstract_span_is_detected() -> None:
    abstract = " ".join(f"ord{i}" for i in range(50))
    article = "Indledning " + " ".join(f"ord{i}" for i in range(10, 45)) + " afslutning"
    assert target_leaks_into_prompt(article, abstract)


def test_no_records_match_is_a_valid_empty_oai_page(monkeypatch) -> None:
    response = requests.Response()
    response.status_code = 200
    response._content = (
        b'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
        b'<error code="noRecordsMatch">No matching records</error></OAI-PMH>'
    )
    response.url = "https://tidsskrift.dk/index/oai"
    session = requests.Session()
    monkeypatch.setattr(session, "get", lambda *args, **kwargs: response)
    root = request_xml(session, {"verb": "ListRecords"}, retries=0)
    assert root is not None
