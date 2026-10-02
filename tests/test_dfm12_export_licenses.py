import pytest

from dfm12.export_licenses import DOWNLOADS, constituent_licenses, enrich, evidence


def test_collection_license_not_applied_to_constituents():
    text = "---\nlicense: cc0-1.0\n---\n\n| Source | License |\n|---|---|\n| [wiki] | [CC-BY-SA 4.0] |\n"
    assert constituent_licenses(text) == {"wiki": "CC-BY-SA 4.0"}


def test_linked_lowercase_polish_constituent_table():
    assert constituent_licenses("| source | license |\n|---|---|\n| [govpl](data/govpl.md) | `CC-BY-SA-4.0` |\n") == {"govpl": "CC-BY-SA-4.0"}


@pytest.mark.parametrize("repo,revision,file,label", [
    ("danish-foundation-models/norwegian-dynaword", "2bc33815865fb3d610e2a080b19156db8e98feef", "data/maalfrid/data.parquet", "NLOD 2.0"),
    ("SlayerLab/polish-dynaword", "1564cb054434ba049cbd0d355a9bfaf044b6a852", "data/govpl/govpl.parquet", "CC-BY-SA-4.0"),
    ("BramVanroy/ultrachat_200k_dutch", "6df1277920dc2d1ecdbb614bc673ff0680e1265f", "data/train_sft-00000-of-00002.parquet", "apache-2.0"),
])
@pytest.mark.skipif(not (DOWNLOADS / "dynaword-pl/README.md").exists(), reason="local pinned source evidence")
def test_new_export_license_mappings(repo, revision, file, label):
    result = enrich({"repo": repo, "revision": revision, "file": file}, lambda p: "metadata/" + p.name)
    assert result["license"] == label
    assert result["license_resolution"]["evidence"]


@pytest.mark.skipif(not (DOWNLOADS / "dynaword-no/data/wikipedia-nob/wikipedia-nob.md").exists(), reason="local pinned evidence")
def test_norwegian_wikipedia_does_not_erase_sharealike():
    result, paths = evidence("danish-foundation-models/norwegian-dynaword",
                             "2bc33815865fb3d610e2a080b19156db8e98feef", "wikipedia-nob")
    assert result["source_declared_license"] == "CC-0"
    assert result["status"] == "conflicting_upstream_claims_preserved"
    assert "share-alike" in result["license"] and len(paths) == 3


def test_existing_notice_untouched():
    original = {"license": "CC-BY-SA-3.0", "repo": "example/repo"}
    assert enrich(original, lambda p: pytest.fail("should not bundle")) == original


def test_unsupported_source_not_relicensed():
    original = {"repo": "example/repo", "file": "data/foo/bar.parquet"}
    assert enrich(original, lambda p: pytest.fail("should not bundle")) == original


@pytest.mark.skipif(not (DOWNLOADS / "dynaword-nl/README.md").exists(), reason="local pinned source evidence")
def test_dutch_constituent_resolution():
    result = enrich({"repo": "danish-foundation-models/dutch-dynaword",
                     "revision": "d0158defd949699532e59dea5978c5542afb0400",
                     "file": "data/european_parliament/data.parquet"}, lambda p: "metadata/" + p.name)
    assert result["license"] == "CC-BY 4.0"
    assert result["license_resolution"]["status"] == "source_declared"


@pytest.mark.skipif(not (DOWNLOADS / "dynaword-nl/README.md").exists(), reason="local pinned source evidence")
def test_wrong_revision_rejected():
    with pytest.raises(ValueError, match="revision"):
        evidence("danish-foundation-models/dutch-dynaword", "wrong", "european_parliament")


@pytest.mark.skipif(not (DOWNLOADS / "dyna-instruct-fo/README.md").exists(), reason="local pinned source evidence")
def test_instruct_unknown_not_replaced_by_collection_license():
    result, _ = evidence("danish-foundation-models/faroese-dyna-instruct",
                         "8d56426e98fed42eec75ceba857ab0d0a74cce16", "dynaword-reverse-instruct")
    assert result["status"] == "partially_specified_upstream"
    assert "unspecified" in result["license"]


@pytest.mark.parametrize("constituent,notice", [
    ("aya_collection_language_split", "unresolved"),
    ("muri-it-language-split", "not relicensed"),
    ("Alpaca-Lora-GPT4-Swedish-Refined", "no grant inferred"),
    ("danish-OpenHermes", "not independently established"),
])
@pytest.mark.skipif(not (DOWNLOADS.parent / "scandi-included-20260925-v1/verification.json").exists(), reason="local pinned Scandi evidence")
def test_scandi_not_relicensed(constituent, notice):
    from dfm12.scandi import REPO, REVISION
    result = enrich({"repo": REPO, "revision": REVISION, "constituent": constituent}, lambda p: "metadata/" + p.name)
    assert notice in result["license"]
    assert result["license_resolution"]["license_grant"] is False
    assert result["license_resolution"]["evidence"]
    assert result["constituent"] == constituent


@pytest.mark.parametrize("original", [
    {"repo": "danish-foundation-models/norwegian-dyna-instruct", "constituent": "norquad-wikipedia", "license": "CC-BY-SA-3.0 passages; CC0-1.0 annotations"},
    {"repo": "danish-foundation-models/norwegian-dyna-instruct", "constituent": "fleurs-alpaca-en-no", "license": "CC-BY-SA-4.0 FLORES text; retain Google FLEURS/Ruter CC-BY-4.0 notices"},
    {"source_dataset": "SlayerLab/polish-dynaword", "source_revision": "pinned", "license": "CC-BY-4.0", "author": "author", "url_kind": "upstream_dataset_file_not_original_article"},
])
def test_scoped_norwegian_and_dala_existing_notices_preserved(original):
    assert enrich(original, lambda p: pytest.fail("existing notice must remain unchanged")) == original
