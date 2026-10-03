"""CPU-only reconstruction of existing OpenHermes English repair evidence.

Never calls a model or the Hub. SQLite and generated artifacts stay in output.
Input files are read-only. Last record wins in sorted filename/line order,
matching the historical builder (not an inferred timestamp ordering).
"""
import argparse
import ast
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(compact(value).encode()).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def disposition(source, audit, repair, verdict, published):
    if published:
        return 'accepted_repaired' if published['kind'].endswith('_repaired') else 'accepted_original'
    if not audit:
        return 'missing_source_audit'
    if audit.get('row_failure'):
        return 'source_audit_operational_failure'
    if audit.get('exclude'):
        return 'source_excluded_by_existing_judge'
    if audit.get('repair_needed'):
        if not repair:
            return 'repair_missing'
        if repair.get('ok') is not True:
            return 'repair_generation_failure'
        if not verdict:
            return 'repair_audit_missing'
        if verdict.get('row_failure'):
            return 'repair_audit_operational_failure'
        if verdict.get('keep') is not True:
            return 'repair_rejected_by_existing_judge'
        return 'accepted_repair_missing_from_package'
    return 'unexplained_omission'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    pub = out / 'upload_candidate'
    pub.mkdir()
    root = Path('data/dfm8_openhermes_repaired')
    package = Path('export-upload-dfm8-openhermes-repaired/dfm8-openhermes-en')
    inventory = []
    stats = {}
    db = sqlite3.connect(out / 'join.sqlite')
    db.execute('pragma journal_mode=WAL')
    db.execute('pragma cache_size=-65536')
    db.execute('pragma temp_store=FILE')
    for table in ('source', 'audit', 'repair', 'verdict', 'published'):
        db.execute(f'create table {table} (id text primary key, data text not null)')

    def rows(path):
        # Hash the original bytes, including compressed package bytes.
        h = hashlib.sha256()
        with path.open('rb') as raw:
            stream = gzip.GzipFile(fileobj=raw) if path.suffix == '.gz' else raw
            for line_no, line in enumerate(stream, 1):
                if path.suffix != '.gz':
                    h.update(line)
                if line.strip():
                    yield json.loads(line), {'path': str(path), 'line': line_no}
        inventory.append(dict(path=str(path), bytes=path.stat().st_size,
                              sha256=sha_file(path) if path.suffix == '.gz' else h.hexdigest()))

    def load(table, paths, convert):
        n = 0
        for path in paths:
            for row, loc in rows(path):
                key, value = convert(row, loc)
                db.execute(f'insert or replace into {table} values (?,?)', (key, compact(value)))
                n += 1
                if n % 10000 == 0:
                    db.commit()
                if n % 100000 == 0:
                    print(table, n, flush=True)
        db.commit()
        unique = db.execute(f'select count(*) from {table}').fetchone()[0]
        stats[table] = dict(records=n, unique_keys=unique, overwritten_records=n-unique)
        print(table, stats[table], flush=True)

    load('source', [root/'requests/source_audit_requests.jsonl'],
         lambda r, loc: (r['source_row_id'], dict(source_row_id=r['source_row_id'],
             original_messages_sha256=digest(r['original']['messages']), location=loc,
             source_file=r.get('source_file'), request_id=r['request_id'])))
    load('audit', sorted((root/'source_audits').glob('shard_*.jsonl')),
         lambda r, loc: (r['source_row_id'], dict(r, location=loc)))
    load('repair', sorted((root/'english_repaired').glob('shard_*.jsonl')),
         lambda r, loc: (r['request_id'], dict(request_id=r['request_id'],
             source_row_id=r.get('source_row_id'), ok=r.get('ok'),
             messages_sha256=digest(r.get('messages')),
             original_messages_sha256=digest((r.get('original') or {}).get('messages')),
             metadata=r.get('metadata'), error=r.get('error'), budget=r.get('budget'),
             source_audit=r.get('source_audit'), location=loc)))
    load('verdict', sorted((root/'english_repair_audits').glob('shard_*.jsonl')),
         lambda r, loc: (r['request_id'], dict(r, location=loc)))
    load('published', sorted((package/'data').glob('*.jsonl.gz')),
         lambda r, loc: (r['source_row_id'], dict(row_id=r['row_id'],
             kind=r['dfm8_synthetic_family'], messages_sha256=digest(r['messages']),
             location=loc, defect_type=r.get('defect_type'))))

    def get(table, key):
        row = db.execute(f'select data from {table} where id=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None

    counts, issues, defects, repair_reasons = Counter(), Counter(), Counter(), Counter()
    examples = []
    example_groups = Counter()
    overlaps = 0
    for table in ('audit', 'published'):
        issues[f'{table}_without_source'] = db.execute(
            f'select count(*) from {table} left join source using(id) where source.id is null').fetchone()[0]
    with gzip.open(pub/'row_provenance.jsonl.gz', 'wt', encoding='utf-8', compresslevel=1) as dest:
        for sid, source_text in db.execute('select id,data from source order by id'):
            source = json.loads(source_text)
            audit = get('audit', sid)
            rid = hashlib.blake2b(('openhermes_english_repair\0'+sid).encode(), digest_size=12).hexdigest()
            repair, verdict, published = get('repair', rid), get('verdict', rid), get('published', sid)
            state = disposition(source, audit, repair, verdict, published)
            counts[state] += 1
            row_issues = []
            if published:
                repaired = state == 'accepted_repaired'
                expected = repair if repaired else source
                key = 'messages_sha256' if repaired else 'original_messages_sha256'
                if not expected or published['messages_sha256'] != expected[key]:
                    row_issues.append('published_content_mismatch')
                if repaired:
                    if not repair or repair.get('ok') is not True or not verdict or verdict.get('keep') is not True:
                        row_issues.append('missing_positive_repair_evidence')
                    if repair and repair['original_messages_sha256'] != source['original_messages_sha256']:
                        row_issues.append('repair_original_mismatch')
                    if published['row_id'] != rid:
                        row_issues.append('published_request_id_mismatch')
                    judge = (repair or {}).get('source_audit', {}) or audit or {}
                    judge = judge.get('judge') or {}
                    factual, style = judge.get('source_answer_defective'), judge.get('reasoning_style_defective')
                    bucket = ('answer_and_style' if factual is True and style is True else
                              'answer_only' if factual is True else 'style_only' if style is True else 'other_or_unspecified')
                    repair_reasons[bucket] += 1
                    defects[str(judge.get('defect_type'))] += 1
                    overlaps += int(bool(audit and audit.get('clean') is True))
                elif not audit or audit.get('clean') is not True:
                    row_issues.append('missing_positive_original_evidence')
            issues.update(row_issues)
            evidence = dict(source_row_id=sid, disposition=state, source=source,
                            source_audit=audit, repair=repair, repair_audit=verdict,
                            published=published, linkage_issues=row_issues)
            dest.write(compact(evidence)+'\n')
            # Mechanical selection only: no new quality assessment.
            group = state + ':' + str((published or {}).get('defect_type'))
            if published and len(examples) < 20 and example_groups[group] < 2:
                examples.append(evidence)
                example_groups[group] += 1
            if sum(counts.values()) % 100000 == 0:
                print('joined', sum(counts.values()), dict(counts), flush=True)

    # Retrieve only selected original/generated texts in single sequential passes.
    wanted = {}
    for example in examples:
        for key in ('source', 'repair'):
            loc = (example.get(key) or {}).get('location')
            if loc:
                wanted.setdefault(loc['path'], {})[loc['line']] = (example, key)
    for path, lines in wanted.items():
        with Path(path).open() as f:
            for n, line in enumerate(f, 1):
                if n in lines:
                    example, key = lines[n]
                    r = json.loads(line)
                    example[key+'_messages'] = r['original']['messages'] if key == 'source' else r.get('messages')
                if n >= max(lines):
                    break
    (pub/'examples.jsonl').write_text(''.join(compact(e)+'\n' for e in examples))

    failures = Counter()
    for path in sorted((root/'row_failures').rglob('*.jsonl')):
        if path.parent.name not in ('source_audit', 'english_repair', 'english_repair_audit'):
            continue
        for r, loc in rows(path):
            failures[path.parent.name+':'+str((r.get('error') or {}).get('type'))] += 1
    # Inventory exact request payloads and operational evidence without publishing raw logs.
    more = list((root/'english_repair_request_shards').glob('*.jsonl'))
    more += [root/'requests/english_repair_requests.jsonl', root/'request_manifest.json']
    more += list(Path('logs').glob('dfm8_openhermes_repaired*/workers/*'))
    more += list(Path('logs').glob('dfm8_openhermes_repaired*/servers/*'))
    more += [package/'README.md', package/'manifest.json', package.parent/'build_summary.json']
    for path in sorted(set(more)):
        if path.is_file():
            inventory.append(dict(path=str(path), bytes=path.stat().st_size, sha256=sha_file(path)))
    (pub/'input_inventory.jsonl').write_text(''.join(compact(r)+'\n' for r in inventory))
    summary = dict(inputs=stats, disposition=dict(counts), linkage_issues=dict(issues),
                   accepted_repair_reason_flags=dict(repair_reasons),
                   accepted_repair_defect_types=dict(defects),
                   actual_clean_and_accepted_repair_overlap=overlaps,
                   archived_failure_events=dict(failures),
                   warning='Reason flags and defect types are existing model judgments, not newly verified facts.',
                   package_revision_recorded_in_wiki='157a1488d453aef9e827bddabc77d78c0bfd57ef',
                   remote_reverified=False, git_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
    (pub/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    implementation = Path('dfm8_openhermes_repaired/dfm8_openhermes_repaired/cli.py')
    code = implementation.read_text()
    prompts = [ast.get_source_segment(code, node) for node in ast.parse(code).body
               if isinstance(node, ast.FunctionDef) and node.name in
               ('audit_source_messages', 'repair_english_messages', 'audit_repair_messages')]
    (pub/'prompts.py').write_text('\n\n'.join(prompts)+'\n')
    snapshots = pub/'code_snapshot'
    snapshots.mkdir()
    for path in (implementation, Path(__file__),
                 Path('dfm8_openhermes_repaired/scripts/run_openhermes_repair_8gpu.sh'),
                 Path('dfm8_openhermes_repaired/scripts/resume_openhermes_repair_from_stage_8gpu.sh')):
        (snapshots/path.name).write_bytes(path.read_bytes())
    (pub/'README.md').write_text(f'''# OpenHermes English repair evidence (draft)

CPU-only reconstruction from retained local records. No new judgments, model
calls, regeneration, or uploads. Counts describe existing decisions, not an
independent correctness evaluation. The data package is unchanged.

## Pipeline

OpenHermes 2.5 conversations were audited with Gemma 4 31B IT, classified as
clean, repairable, or excluded. Flagged conversations were regenerated with
the same model using a repair-specific prompt, then judged against their
originals with a separate prompt. Accepted original rows and accepted repairs
were combined by source ID, with accepted repairs taking precedence.

Repairs addressed answer defects, instruction following, broken code, structure,
and reasoning style. Prompts also requested concise visible explanations,
removal of unnecessary hidden-CoT/step-by-step boilerplate, and one final boxed
answer for determinate math tasks. These are instructions, not proven universal
properties of the resulting data. Role/content messages are published; Gemma
native chat templating is a downstream training operation.

The retained runner specifies audit temperature 0.0, repair temperature 0.2,
8192 context, and dynamic completion budgeting. The server log at
logs/dfm8_openhermes_repaired_20260712T085219/servers/gpu0.log confirms the local
gemma-4-31B-it-fresh-20260604 checkpoint and 8192 context. Exact Hub model/source
revision pins and historical code revision remain unverified. Code snapshots
are the files present at evidence-build time, not a claim of historical identity.

## Counts

{json.dumps(dict(counts), indent=2)}

See summary.json for linkage failures, duplicate-record counts, existing-judge
defect categories, and archived operational failures. Record order is sorted
filename then line, with last record winning, matching the original builder.
Archived failures count attempts, not unique defective source rows.

## Files and interpretation

- row_provenance.jsonl.gz: all source IDs, dispositions, existing verdicts,
  repair metadata, message hashes and exact local file/line references.
- examples.jsonl: mechanically selected original/repaired texts with judgments;
  illustrative only, not a representative quality estimate.
- input_inventory.jsonl: SHA256 checksums of source evidence, requests, logs,
  and local published-package files. Full logs remain local.
- prompts.py and code_snapshot/: exact current prompt definitions and code.

Published source_answer_defective is hardcoded true for repaired rows, including
style-only repairs; use original judge flags instead for descriptive statistics.
The old clean_rows_shadowed_by_repair counter is the number of repaired IDs,
not their overlap with clean verdicts; the true overlap is recomputed here.
The same model generated and judged repairs, so correlated errors remain.
No human review, independent code execution, or factual verification is claimed.

## Publication proposal

Review this package first. Add a detailed methodology card to the existing
schneiderkamplab/dfm8-openhermes-en repository without changing training shards.
Put evidence in a separate repository/config or non-training evidence directory,
with explicit dataset data-file patterns so it cannot be loaded as training data.
Do not publish join.sqlite or raw server logs. Remote package hashes have not
been compared in this preparation step. Licensing, privacy/content review and
credential-pattern findings must be checked before upload.
''')
    # Advisory only; does not remove or redact evidence or print matched strings.
    patterns = {'hf_token': re.compile(r'hf_[A-Za-z0-9]{25,}'),
                'wandb_key': re.compile(r'wandb_v1_[A-Za-z0-9_-]{30,}'),
                'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')}
    findings = Counter()
    for path in pub.rglob('*'):
        if not path.is_file():
            continue
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf-8') as f:
            for line in f:
                for name, pattern in patterns.items():
                    if pattern.search(line):
                        findings[str(path.relative_to(pub))+':'+name] += 1
    manifest = dict(uploaded=False, approved=False, credential_pattern_findings=dict(findings),
                    files=[dict(path=str(p.relative_to(pub)), bytes=p.stat().st_size, sha256=sha_file(p))
                           for p in sorted(pub.rglob('*')) if p.is_file()],
                    review_required=['Remote shard checksum comparison', 'Dataset-card review',
                                     'Existing-text privacy/license review; no new quality judgments'])
    (out/'proposed_upload_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    db.close()
    print(json.dumps(summary, indent=2), flush=True)
    print('Prepared locally; NOT uploaded:', out, flush=True)


if __name__ == '__main__':
    main()
