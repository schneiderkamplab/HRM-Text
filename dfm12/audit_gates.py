"""Fail-closed use of frozen overlap evidence; never choose duplicate winners."""
from pathlib import Path
from html.parser import HTMLParser

from .io import file_hash, load, rows
from .records import chat_fingerprint
from .scandi_overlap import text_hash

FILES = ("heldout-quarantine.jsonl", "flagged-chat-rows.jsonl", "source-overlap-groups.jsonl")


def legacy_tool_reasons(record):
    class Tags(HTMLParser):
        found = False
        def handle_starttag(self, tag, attrs):
            if tag in {"functions", "function_calls", "function_call", "tool_call", "tool_calls",
                       "tool_response", "tool_result", "function_result", "invoke", "tools"}:
                self.found = True
    parser = Tags()
    if record.get("tools") or record.get("functions"):
        return ["native_tool_schema_requires_dedicated_audit"]
    for field in ("messages", "reverse_messages"):
        for message in record.get(field, []):
            if message.get("role") in ("tool", "function") or message.get("tool_calls") or message.get("function_call"):
                return ["native_tool_schema_requires_dedicated_audit"]
            parser.feed(message.get("content", ""))
    return ["legacy_xml_tool_flattening_requires_quarantine"] if parser.found else []


class CrossScreen:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.manifest = load(self.path)
        self.scoped = None
        if self.manifest.get("scope") == "user_scoped_inclusion_audit_only":
            from .scoped_inclusion_audit import validate_screen
            scoped = validate_screen(self.path)
            base = CrossScreen(scoped["base_crossscreen"]["path"])
            self.__dict__.update(base.__dict__)
            self.path = Path(path).resolve()
            self.scoped = scoped
            self.evidence = dict(base.evidence, **{str(self.path): file_hash(self.path)})
            return
        m = self.manifest
        if (not m.get("snapshot_stable_at_finalization")
                or m.get("changed_or_missing_inputs_since_scan")):
            raise ValueError("Cross-screen snapshot is not stable")
        self.evidence = {str(self.path): file_hash(self.path)}
        for name, expected in [("coverage.json", m["coverage_sha256"])] + [
                (name, m["outputs"][name]) for name in FILES]:
            candidate = self.path.parent / name
            actual = file_hash(candidate)
            if actual != expected:
                raise ValueError("Cross-screen evidence checksum mismatch: " + name)
            self.evidence[str(candidate)] = actual
        self.coverage = {(str(Path(f["path"]).resolve()), f["sha256"])
                         for f in load(self.path.parent / "coverage.json")["files"]
                         if f.get("state") == "scanned_stable" and f.get("sha256")}
        heldout = list(rows(self.path.parent / FILES[0]))
        self.heldout_ids = {r["source_id"] for r in heldout}
        self.heldout_texts = {f["text_sha256"] for r in heldout for f in r["matching_fields"]}
        self.duplicate_hashes = {r["chat_sha256"] for r in rows(self.path.parent / FILES[1])}
        self.shared_sources = {(c["component"], c["source_id"])
                               for r in rows(self.path.parent / FILES[2]) for c in r["components"]}

    def descriptor(self):
        if self.scoped is not None:
            return {"path": str(self.path), "evidence": self.evidence,
                    "policy": "user_scoped_inclusion_audit_only", "accepted_exports_allowed": False,
                    "full_inherited_coverage": False, "benchmarks_clear": False}
        return {"path": str(self.path), "evidence": self.evidence,
                "policy": "quarantine_all_flagged_no_automatic_duplicate_winner",
                "full_inherited_coverage": self.manifest.get("full_inherited_coverage", False),
                "benchmarks_clear": self.manifest.get("benchmarks_clear", False)}

    def covered(self, source):
        return (str(Path(source["path"]).resolve()), source["sha256"]) in self.coverage

    def reasons(self, record):
        if self.scoped is not None:
            source = self.scoped["sources"].get(record.get("component"))
            origin = record.get("audit_source", {})
            if (not source or origin.get("sha256") != source["sha256"]
                    or origin.get("path") != source["path"]):
                raise ValueError("Record outside pinned user inclusion audit scope")
        reasons = legacy_tool_reasons(record)
        ids = {record.get("id"), record.get("source_record_id")}
        if ids & self.heldout_ids:
            reasons.append("heldout_quarantine_id")
        for field in ("messages", "reverse_messages"):
            messages = record.get(field, [])
            if messages and chat_fingerprint(messages) in self.duplicate_hashes:
                reasons.append("unresolved_duplicate_chat")
            if any(text_hash(m["content"]) in self.heldout_texts for m in messages):
                reasons.append("heldout_quarantine_text")
        context = record.get("audit_context", {})
        if any(isinstance(v, str) and text_hash(v) in self.heldout_texts for v in context.values()):
            reasons.append("heldout_quarantine_reference")
        if any((record.get("component"), value) in self.shared_sources for value in ids):
            reasons.append("unresolved_shared_source_review")
        if record.get("component") == "dynaword-nl" and record.get("task") == "paragraph-reordering":
            reasons.append("legacy_paragraphs_superseded_by_reconciled_integration")
        if "scandi-omitted" == record.get("component"):
            reasons.append("omitted_scandi_release")
        override_heldout = self.scoped is not None
        if override_heldout and self.scoped["family"] == "scandi":
            from .scandi_admission import authorized_muri_heldout
            override_heldout = authorized_muri_heldout(record)
        if override_heldout:
            reasons = [reason for reason in reasons if reason not in {
                "heldout_quarantine_id", "heldout_quarantine_text", "heldout_quarantine_reference"}]
        return sorted(set(reasons))


def pinned_screen(descriptor):
    if not descriptor:
        raise ValueError("Cross-screen gates required before accepted export; refresh readiness")
    screen = CrossScreen(descriptor["path"])
    if screen.descriptor() != descriptor:
        raise ValueError("Cross-screen evidence changed; refresh readiness")
    return screen
