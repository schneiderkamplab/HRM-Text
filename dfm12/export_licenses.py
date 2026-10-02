"""Resolve constituent license metadata without relicensing source content."""
from functools import lru_cache
from pathlib import Path

from markdown_it import MarkdownIt
import yaml

from .io import file_hash, load

DOWNLOADS = Path(__file__).resolve().parents[1] / "data/dfm12/downloads"
SOURCES = {
    "faroese-dynaword": "dynaword-fo",
    "icelandic-dynaword": "dynaword-is",
    "dutch-dynaword": "dynaword-nl",
    "swedish-dynaword": "dynaword-sv",
    "norwegian-dynaword": "dynaword-no",
    "faroese-dyna-instruct": "dyna-instruct-fo",
    "icelandic-dyna-instruct": "dyna-instruct-is",
}
REPOSITORIES = {"danish-foundation-models/" + name: folder for name, folder in SOURCES.items()}
REPOSITORIES["SlayerLab/polish-dynaword"] = "dynaword-pl"

cached_hash = lru_cache(maxsize=64)(file_hash)


@lru_cache(maxsize=4)
def norwegian_evidence(revision):
    root = DOWNLOADS.parent / "norwegian-20260924"
    receipt = load(root / "evidence-receipt.json")
    path = root / "evidence/upstream/reasoning-norwegian/README.md"
    url = f"https://huggingface.co/datasets/pere/reasoning_norwegian/resolve/{revision}/README.md"
    entry = next(e for e in receipt["files"] if e["url"] == url)
    if file_hash(path) != entry["sha256"]:
        raise ValueError("Norwegian source evidence changed")
    return path, url


def constituent_licenses(text):
    """Read source/license columns, never the collection frontmatter license."""
    result, headers, cells, in_row = {}, [], [], False
    for token in MarkdownIt("commonmark", {"html": False}).enable("table").parse(text):
        if token.type == "table_open":
            headers = []
        elif token.type == "tr_open":
            cells, in_row = [], True
        elif token.type == "inline" and in_row:
            cells.append("".join(child.content for child in token.children or []
                                 if child.type in ("text", "code_inline")).strip().strip("[]"))
        elif token.type == "tr_close":
            in_row = False
            if not headers:
                headers = [cell.casefold() for cell in cells]
            elif "source" in headers and "license" in headers:
                name, label = cells[headers.index("source")], cells[headers.index("license")]
                if name.casefold() != "total":
                    if name in result and result[name] != label:
                        raise ValueError("Conflicting constituent license: " + name)
                    result[name] = label
    return result


@lru_cache(maxsize=32)
def evidence(repo, revision, constituent):
    if repo not in REPOSITORIES:
        return None
    root = DOWNLOADS / REPOSITORIES[repo]
    card = root / "README.md"
    pin = root / ".cache/huggingface/download/README.md.metadata"
    if pin.read_text().splitlines()[0] != revision:
        raise ValueError("License card revision differs from source: " + repo)
    label = constituent_licenses(card.read_text())[constituent]
    paths = [card]
    info = {"source_repo": repo, "revision": revision, "constituent": constituent,
            "basis": "pinned_constituent_card_not_collection_license",
            "source_card_url": f"https://huggingface.co/datasets/{repo}/blob/{revision}/README.md",
            "license": label, "status": "source_declared"}
    if repo == "danish-foundation-models/norwegian-dynaword" and constituent in ("wikipedia-nob", "wikipedia-nno"):
        sheet = root / "data" / constituent / (constituent + ".md")
        sheet_pin = root / ".cache/huggingface/download/data" / constituent / (constituent + ".md.metadata")
        if sheet_pin.read_text().splitlines()[0] != revision:
            raise ValueError("Wikipedia datasheet revision differs from source")
        review = DOWNLOADS.parent / "candidates/dynaword-no/receipt.json"
        prior = load(review)["source"]
        if prior["revision"] != revision or "share-alike" not in prior["review_receipt"]["evidence"]:
            raise ValueError("Norwegian Wikipedia preparation restriction missing")
        info.update(license="Wikipedia attribution/share-alike obligations retained; source declares CC0-1.0",
                    status="conflicting_upstream_claims_preserved",
                    source_declared_license=label,
                    preparation_restriction=prior["review_receipt"]["evidence"],
                    caveat="The collection/datasheet CC0 declaration does not erase underlying Wikipedia attribution/share-alike obligations. No replacement license or applicable version is asserted.")
        paths.extend((sheet, review))
    if label.casefold() == "unknown":
        sheet = root / "data" / constituent / "datasheet.md"
        sheet_pin = root / ".cache/huggingface/download/data" / constituent / "datasheet.md.metadata"
        if sheet_pin.read_text().splitlines()[0] != revision:
            raise ValueError("Datasheet revision differs from source")
        text = sheet.read_text()
        section = text.split("### License Information\n", 1)[1].split("\n#", 1)[0].strip()
        info.update(license="Generated instruction license unspecified; underlying passages CC-BY-4.0 / CC-BY-SA-4.0",
                    status="partially_specified_upstream", upstream_license_statement=section,
                    source_use_approval="User approved DynaWord/Dyna-Instruct sources for DFM12; this is not an SPDX license grant.")
        paths.append(sheet)
    return info, tuple(paths)


@lru_cache(maxsize=4)
def ultrachat_evidence(repo, revision):
    if repo != "BramVanroy/ultrachat_200k_dutch":
        return None
    root = DOWNLOADS / "ultrachat-nl"
    card = root / "README.md"
    if (root / ".cache/huggingface/download/README.md.metadata").read_text().splitlines()[0] != revision:
        raise ValueError("UltraChat card revision differs from source")
    frontmatter = yaml.safe_load(card.read_text().split("---", 2)[1])
    if frontmatter.get("license") != "apache-2.0":
        raise ValueError("Unexpected UltraChat license declaration")
    return ({"license": "apache-2.0", "status": "source_declared",
             "source_repo": repo, "revision": revision, "basis": "pinned_single_source_card",
             "source_card_url": f"https://huggingface.co/datasets/{repo}/blob/{revision}/README.md"}, (card,))


@lru_cache(maxsize=8)
def scandi_evidence(repo, revision, constituent):
    from .scandi import REPO, REVISION
    if repo != REPO:
        return None
    if revision != REVISION:
        raise ValueError("Scandi license evidence revision mismatch")
    root = DOWNLOADS.parent / "scandi-included-20260925-v1"
    mapping_path = root / "license-evidence-map.json"
    proof = load(root / "verification.json")
    if file_hash(mapping_path) != proof["license_evidence_map_sha256"]:
        raise ValueError("Scandi license evidence map changed")
    mapping = load(mapping_path)
    item = mapping["constituents"][constituent]
    labels = {
        "aya_collection_language_split": "Apache-2.0 umbrella claim; original constituent terms and attribution unresolved",
        "muri-it-language-split": "Apache-2.0 umbrella claim; underlying Wikipedia/CulturaX/SNI rights retained, not relicensed",
        "Alpaca-Lora-GPT4-Swedish-Refined": "License unspecified in pinned Swedish Alpaca card; no grant inferred",
        "danish-OpenHermes": "MIT claim in pinned Danish precursor; direct upstream license/pin not independently established",
    }
    entries = load(root / "source-evidence.json")
    required = {item["evidence_sha256"], mapping["release"]["card_sha256"]}
    selected = [e for e in entries if e["sha256"] in required]
    if {e["sha256"] for e in selected} != required:
        raise ValueError("Missing pinned Scandi constituent cards")
    if constituent == "aya_collection_language_split":
        selected.append(mapping["supplemental_aya_mixture_evidence"])
    for entry in selected:
        if file_hash(entry["path"]) != entry["sha256"]:
            raise ValueError("Scandi constituent license card changed")
    return ({"license": labels[constituent], "status": "claims_and_limitations_preserved",
             "source_repo": repo, "revision": revision, "constituent": constituent,
             "underlying_evidence": item, "license_grant": False,
             "basis": "Explicit accepted-export authorization does not invent constituent license grants"},
            tuple([mapping_path] + [Path(e["path"]) for e in selected]))


def enrich(provenance, bundle):
    """Only enrich missing licenses; retain raw audit records independently."""
    if provenance.get("license") and not str(provenance["license"]).startswith("unknown"):
        return provenance
    repo, revision = provenance.get("repo", ""), provenance.get("revision", "")
    parts = Path(provenance.get("file", "")).parts
    resolved = scandi_evidence(repo, revision, provenance.get("constituent", provenance.get("source_metadata", {}).get("source")))
    if resolved is None:
        resolved = evidence(repo, revision, parts[1]) if len(parts) >= 3 else None
    if resolved is None:
        resolved = ultrachat_evidence(repo, revision)
    if resolved is None and provenance.get("upstream_repo") == "pere/reasoning_norwegian":
        path, url = norwegian_evidence(provenance["upstream_revision"])
        resolved = ({"license": "CC-BY-SA-3.0 upstream; CC-BY-SA-4.0 composite claim retained",
                     "status": "multiple_upstream_claims_preserved", "source_card_url": url,
                     "license_claims": provenance["license_claims"],
                     "basis": "Do not silently replace upstream share-alike notice with composite license"}, (path,))
    if resolved is None:
        return provenance
    info, paths = resolved
    details = dict(info, evidence=[{"file": bundle(p), "sha256": cached_hash(p)} for p in paths])
    return dict(provenance, license=info["license"], license_resolution=details)
