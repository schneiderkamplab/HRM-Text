"""External successor for excerpt attribution under the captured EP reuse notice."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import shutil
import zipfile

from dfm12.io import atomic, digest, file_hash, load, lock, write_json
from scripts.package_baltic_source_attribution import verify

PRIOR = Path('exports_dfm13/baltic-source-attribution-20261004-v1')
OUTPUT = Path('exports_dfm13/baltic-source-attribution-20261004-v2')
EVIDENCE = Path('docs/reports/baltic-source-rights-20261003/evidence-europarl')
NOTICE = '''# Source-specific reuse and attribution decision, 2026-10-04

This successor supersedes the project's extra requirement that each sitting
have a successfully fetched official Parliament URL before these six synthetic
packages could be published. It does not change the sealed dataset or grant
a new license. The European Parliament legal notice permits attributed reuse,
including commercial dissemination, and requires a link to the complete item
or the webpage used as source for partial reproduction. It does not require
a fresh HTTP200 response for every official per-sitting webpage.

For these packets, unchanged source excerpts are bound to complete local sitting
texts, exact OPUS archive SHA256s and original XML member paths. The actual
source distribution URL and corpus webpage accompany each Europarl attribution.
The original Parliament legal-notice URL and captured text are preserved.
Archive attribution/citation and source indications remain present. These
conditions are substantive; a separate guessed official URL is not substituted
for them. No inferred official link is labelled verified.

Generated questions, answers, summaries and rewrites are clearly labelled
independently generated model output, not official Parliament statements,
authorized official translations or endorsed reproductions. The original
source excerpt remains unchanged in row provenance. The prior concern about
deliberately corrupted denoising/reordering source exercises does not establish
a blanket prohibition for these excerpt-grounded synthetic tasks. We rely on
the stated reuse/use permission for this scoped publication, not an invented
unlimited adaptation or CC grant. This is an operational evidence assessment,
not a legal certification; item-specific conditions and third-party rights
continue to apply. No separate item restriction was identified in the pinned
OPUS source evidence; absence of a notice is not a universal rights guarantee.

Attribution: European Union / European Parliament, sitting year/date indicated
per row; Europarl corpus compiled by Philipp Koehn; distributed via OPUS.
Cite Philipp Koehn, Europarl: A Parallel Corpus for Statistical Machine
Translation (MT Summit 2005), and J. Tiedemann, Parallel Data, Tools and
Interfaces in OPUS (LREC 2012). No trademarks/logos are included or licensed.

Primary URLs:
- https://www.europarl.europa.eu/legal-notice/en
- https://www.statmt.org/europarl/
- https://opus.nlpl.eu/datasets/Europarl

Europarl is not declared CC, public domain or unrestricted. Wikipedia and
other source terms remain unchanged. No DynaWord/DynaInstruct authorization
is being used as a substitute Parliament grant.
'''


def bind(source, language, documents, members, archives):
    sid = source['source_document_id']
    text = ' '.join(source['text'].split())
    original = documents.get((language, sid))
    if not text or original is None or text not in original:
        raise ValueError('Excerpt does not match complete pinned sitting')
    paths = members[language].get(sid)
    if not paths:
        raise ValueError('Sitting lacks original archive members')
    return dict(sitting_id=sid, source_language=language,
        source_page_url='https://www.statmt.org/europarl/',
        source_distribution_url=f'https://object.pouta.csc.fi/OPUS-Europarl/v8/raw/{language}.zip',
        archive_sha256=archives[language]['sha256'], archive_members=paths,
        excerpt_sha256=digest(source['text']), complete_sitting_normalized_sha256=digest(original),
        excerpt_matches_complete_sitting=True, official_per_sitting_link_verified=False,
        permission_basis='European Parliament legal notice: attributed reuse and linked partial reproduction',
        attribution=f'European Union / European Parliament; sitting {sid}; Europarl / Philipp Koehn; OPUS / J. Tiedemann',
        generated_content_not_official=True, blanket_cc_license=False)


def prepare(output=OUTPUT):
    output = Path(output)
    with lock(str(output)+'.lock'):
        if output.exists(): raise ValueError('Fresh successor required')
        prior = load(PRIOR/'handoff.json')
        archive_receipt = load(EVIDENCE/'receipt.json')
        pins = {}; documents = {}; members = {}
        local = {r['name']:r for r in load('data/dfm13/baltic/local-sources.json')}
        for name,sha in archive_receipt['files'].items():
            if file_hash(EVIDENCE/name)!=sha:raise ValueError('Captured terms drift')
        for lang, archive in archive_receipt['archives'].items():
            if file_hash(archive['path'])!=archive['sha256']:raise ValueError('Archive hash changed')
            pins[archive['path']]=archive['sha256']; by_date=defaultdict(list)
            with zipfile.ZipFile(archive['path']) as z:
                for name in z.namelist():
                    match=re.search(r'ep-(\d{2}-\d{2}-\d{2})-.*\.xml$',name)
                    if match:by_date[match[1]].append(name)
            members[lang]={k:sorted(v) for k,v in by_date.items()}
            doc=local['Europarl_'+lang]
            if file_hash(doc['path'])!=doc['sha256']:raise ValueError('Complete sitting file changed')
            pins[doc['path']]=doc['sha256']
            for line in Path(doc['path']).open():
                row=json.loads(line); documents[(lang,row['source_document_id'])]=' '.join(row['text'].split())
        output.mkdir(parents=True); results=[]
        for item in prior['packages']:
            if item['upload_ready']:continue
            old=Path(item['path']); original=verify(old)
            if file_hash(old/'publication-manifest.json')!=item['manifest_sha256']:raise ValueError('Prior manifest changed')
            folder=output/old.name; shutil.copytree(old,folder)
            lang=item['name'].split('_')[3]; counts=Counter()
            with (old/'attribution.jsonl').open() as rows, atomic(folder/'attribution.jsonl') as out:
                for line in rows:
                    row=json.loads(line)
                    if row['source'].startswith('Europarl_'):
                        row['europarl_reuse_evidence']=bind(row['source_binding'],lang,documents,members,archive_receipt['archives'])
                        row['publication_evidence_ready']=True
                        row['attribution']=row['europarl_reuse_evidence']['attribution']
                        counts[row['source']]+=1
                    out.write(json.dumps(row,ensure_ascii=False)+'\n')
            (folder/'EUROPARL_REUSE_DECISION.md').write_text(NOTICE)
            text=(folder/'README.md').read_text()
            text=text.replace('verified official sitting links and adaptation scope remain\nunresolved in the existing rights review.',
                'complete-sitting/archive-member attribution is bound in attribution.jsonl.\nSee EUROPARL_REUSE_DECISION.md for the scoped reuse basis and dated supersession.')
            text=text.replace(f'Europarl unresolved rows: {item["unresolved_europarl_rows"]}. Whole-package upload-ready: False.',
                f'Europarl source-bound excerpt rows: {sum(counts.values())}. Whole-package upload-ready: True.\n'
                'Official per-sitting HTTP verification is not claimed or required by this scoped decision.')
            (folder/'README.md').write_text(text)
            manifest=dict(original,upload_ready=True,unresolved_europarl_rows=0,
                europarl_source_bound_rows=sum(counts.values()),prior_manifest_sha256=item['manifest_sha256'],
                decision='EUROPARL_REUSE_DECISION.md',official_per_sitting_link_verified=False,
                source_specific_terms_retained=True)
            manifest['files']={str(p.relative_to(folder)):file_hash(p) for p in folder.rglob('*')
                if p.is_file() and p.name!='publication-manifest.json'}
            write_json(folder/'publication-manifest.json',manifest); verify(folder)
            results.append(dict(name=item['name'],path=str(folder),hf_repo_id=item['hf_repo_id'],
                rows=item['rows'],upload_ready=True,uploaded=False,source_counts=item['source_counts'],
                europarl_source_bound_rows=sum(counts.values()),manifest_sha256=file_hash(folder/'publication-manifest.json')))
        for path,sha in prior['source_pins'].items():
            if file_hash(path)!=sha:raise ValueError('Original sealed release changed')
        receipt=dict(packages=results,evidence_pins=pins,prior_handoff_sha256=file_hash(PRIOR/'handoff.json'),
            sealed_release_unchanged=True,uploaded=False,registry_changed=False,
            supersession='Extra official-per-sitting-fetch gate superseded by actual source-link requirement; scoped attributed reuse, no new license',
            openhermes_ready_packets_remain_at=str(PRIOR))
        write_json(output/'handoff.json',receipt);return receipt


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
