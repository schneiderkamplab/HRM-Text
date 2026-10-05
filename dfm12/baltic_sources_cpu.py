"""Acquire P3 and ParlaMint without admitting unaudited data to training."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request
import xml.etree.ElementTree as ET

from .io import atomic, digest, file_hash, load, lock, rows, write_json
from .prepare import Renderer
from .records import validate_messages

ROOT = Path('data/dfm13/baltic')
P3_REPO = 'matiss/P3-Latvian-translategemma-27b'
P3_REVISION = 'f8d6ecba6fa51521db139c57de9b21870eed9b33'
# One canonical template per original source prevents template multiplication.
P3_CONFIGS = {
    'ai2_arc_ARC_Challenge_pick_the_most_correct_option': 'ARC-Challenge',
    'ai2_arc_ARC_Easy_pick_the_most_correct_option': 'ARC-Easy',
    'openbookqa_main_choices': 'OpenBookQA',
    'quarel_heres_a_story': 'QuaRel',
    'quartz_use_info_from_question_paragraph': 'QuaRTz',
    'glue_mrpc_generate_paraphrase': 'MRPC',
    'web_questions_question_answer': 'WebQuestions',
    'wiki_qa_Direct_Answer_to_Question': 'WikiQA',
}
PARLAMINT = {
    'lt': ('1432', '12', '2.1'),
    'lv': ('2004', '20', '5.0'),
}


def renderer():
    return Renderer(load('data/sampled_dfm11/metadata.json')['tokenizer_info'], 4096)


def p3_messages(row):
    if 'is_correct' in row and row['is_correct'] is not True:
        raise ValueError('incorrect_rank_candidate')
    messages = [dict(role='user', content=row.get('inputs_pretokenized')),
                dict(role='assistant', content=row.get('targets_pretokenized'))]
    validate_messages(messages)
    return messages


def p3(root):
    from huggingface_hub import HfApi, snapshot_download
    directory = root / 'p3'
    with lock(directory / '.lock'):
        files = HfApi().list_repo_files(P3_REPO, repo_type='dataset', revision=P3_REVISION)
        selected = [f for f in files if f.split('/')[0] in P3_CONFIGS
                    and Path(f).name.startswith('train-') and f.endswith('.parquet')]
        if {f.split('/')[0] for f in selected} != set(P3_CONFIGS):
            raise ValueError('Missing selected P3 train configuration')
        write_json(directory / 'selection.json', dict(repo=P3_REPO, revision=P3_REVISION,
            selected=selected, excluded=[f for f in files if f.endswith('.parquet') and f not in selected],
            policy='one canonical template per source; train only; reject incorrect rank targets',
            rights='retain upstream constituent terms; translated repository has no blanket license',
            admission_hold='constituent_rights_review_before_export'))
        snapshot_download(P3_REPO, repo_type='dataset', revision=P3_REVISION,
                          allow_patterns=selected + ['README.md'], local_dir=directory/'download', max_workers=4)
        counts, seen = Counter(), set()
        render = renderer()
        with atomic(directory / 'candidates.jsonl') as out:
            for relative in selected:
                path = directory / 'download' / relative
                sha = file_hash(path)
                family = P3_CONFIGS[relative.split('/')[0]]
                for ordinal, row in enumerate(rows(path)):
                    counts['input'] += 1
                    try:
                        messages = p3_messages(row)
                        fingerprint = digest(messages)
                        if fingerprint in seen:
                            raise ValueError('duplicate')
                        tokens = render.count(messages)
                    except ValueError as exc:
                        counts[str(exc)] += 1
                        continue
                    seen.add(fingerprint)
                    record = dict(id=fingerprint, language='lv', task='instruction', messages=messages,
                        rendered_tokens=tokens, admission_authorized=False,
                        provenance=dict(repo=P3_REPO, revision=P3_REVISION, file=relative,
                            file_sha256=sha, row=ordinal, split='train', family=family),
                        audit_context=dict(instruction='Check translated question and target correctness, '
                            'option-label consistency and missing context. Reject translated ambiguity.'))
                    out.write(json.dumps(record, ensure_ascii=False)+'\n')
                    counts['candidates'] += 1
                    counts[family] += 1
        write_json(directory/'receipt.json', dict(counts=dict(counts), audit='pending',
            admission_hold='constituent_rights_review_before_export',
            sha256=file_hash(directory/'candidates.jsonl')))
        print('P3', dict(counts), flush=True)


def speech_rows(handle, origin):
    ns = '{http://www.tei-c.org/ns/1.0}'
    for _, node in ET.iterparse(handle, events=('end',)):
        if node.tag == ns+'u':
            paragraphs = [' '.join(''.join(seg.itertext()).split()) for seg in node.findall('.//'+ns+'seg')]
            text = '\n\n'.join(p for p in paragraphs if p)
            if text:
                yield dict(id=node.get('{http://www.w3.org/XML/1998/namespace}id'), text=text,
                           speaker=node.get('who'), source=origin)
            node.clear()


def parlamint(root, language):
    record, seq, version = PARLAMINT[language]
    url = f'https://www.clarin.si/repository/xmlui/bitstream/handle/11356/{record}/ParlaMint-{language.upper()}.tgz?sequence={seq}&isAllowed=y'
    directory = root/'parlamint'/language
    with lock(directory/'.lock'):
        archive = directory/'source.tgz'
        if not archive.exists():
            temporary = archive.with_suffix('.partial')
            with urllib.request.urlopen(url, timeout=180) as source, temporary.open('wb') as dest:
                while block := source.read(4*1024*1024):
                    dest.write(block)
            temporary.replace(archive)
        sha = file_hash(archive)
        counts = Counter()
        with tarfile.open(archive, 'r:gz') as bundle, atomic(directory/'documents.jsonl') as out:
            for member in bundle:
                if not member.isfile() or not member.name.endswith('.xml'):
                    continue
                with bundle.extractfile(member) as handle:
                    for row in speech_rows(handle, member.name):
                        row.update(language=language, license='CC-BY-4.0',
                            source_document_id=digest([sha,member.name,row['id']]),
                            provenance=dict(url=url, version=version, archive_sha256=sha, member=member.name))
                        out.write(json.dumps(row, ensure_ascii=False)+'\n')
                        counts['speeches'] += 1
                        counts['characters'] += len(row['text'])
        if not counts['speeches']:
            raise ValueError('No ParlaMint speech segments found')
        write_json(directory/'receipt.json', dict(url=url, version=version, language=language,
            counts=dict(counts), archive_sha256=sha, sha256=file_hash(directory/'documents.jsonl'),
            license='CC-BY-4.0', role='transformation input; never assume parallel alignment'))
        print('ParlaMint',language,dict(counts),flush=True)


def euroblocks(root):
    with lock(root/'euroblocks/.lock'):
        return _euroblocks(root)


def _euroblocks(root):
    import pyarrow.parquet as pq
    previous=Path('data/dfm12/european-expansion-20260926')
    source=load(previous/'sources.lock.json')['sources']['euroblocks']
    directory=root/'euroblocks'
    render=renderer()
    counts,seen=Counter(),set()
    with atomic(directory/'candidates.jsonl') as out:
        for relative in source['files']:
            path=previous/'downloads/euroblocks'/relative
            # Filter via Arrow before materializing the large multilingual chats.
            sha=file_hash(path)
            table=pq.read_table(path,filters=[('language','in',['Lithuanian','Latvian'])])
            for ordinal,row in enumerate(table.to_pylist()):
                lang={'Lithuanian':'lt','Latvian':'lv'}[row['language']]
                messages=row['conversations']
                try:
                    validate_messages(messages)
                    tokens=render.count(messages)
                except ValueError as exc:
                    counts[str(exc)]+=1
                    continue
                key=digest(messages)
                if key in seen:
                    counts['duplicates']+=1
                    continue
                seen.add(key)
                result=dict(id=key,language=lang,task='instruction',messages=messages,
                    rendered_tokens=tokens,admission_authorized=False,
                    provenance=dict(repo=source['repo'],revision=source['revision'],file=relative,
                        file_sha256=sha,filtered_ordinal=ordinal,split='train'))
                out.write(json.dumps(result,ensure_ascii=False)+'\n')
                counts[lang]+=1
    write_json(directory/'receipt.json',dict(counts=dict(counts),sha256=file_hash(directory/'candidates.jsonl'),audit='pending'))
    print('EuroBlocks',dict(counts),flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['p3', 'parlamint-lt', 'parlamint-lv','euroblocks'])
    p.add_argument('--root', type=Path, default=ROOT)
    args = p.parse_args()
    if args.stage == 'p3':
        p3(args.root)
    elif args.stage=='euroblocks':
        euroblocks(args.root)
    else:
        parlamint(args.root, args.stage.rsplit('-',1)[1])


if __name__ == '__main__':
    main()
