"""Bounded, file-stratified Baltic text sampling and native transformations."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import heapq
import json
import math
from pathlib import Path
import re
from types import FunctionType

from . import transform as shared
from .io import atomic, digest, file_hash, load, lock, rows, write_json
from .baltic_sources_cpu import ROOT, renderer

PROMPTS = {
    'lt': ('lietuvių kalba', 'Ištaisykite teksto klaidas.',
           'Pratęskite tekstą; pateikite tik trūkstamą tęsinį.',
           'Užpildykite <GAP>; pateikite tik trūkstamą tekstą.',
           'Atkurkite pradinę pastraipų tvarką; pateikite visą tekstą be numeracijos.'),
    'lv': ('latviešu valoda', 'Izlabojiet kļūdas tekstā.',
           'Turpiniet tekstu; sniedziet tikai trūkstošo turpinājumu.',
           'Aizpildiet <GAP>; sniedziet tikai trūkstošo tekstu.',
           'Atjaunojiet rindkopu sākotnējo secību; sniedziet visu tekstu bez numerācijas.'),
}
transform = FunctionType(shared.transform.__code__, dict(shared.transform.__globals__, PROMPTS=PROMPTS),
                         shared.transform.__name__, shared.transform.__defaults__)


def document_ok(row, language, name):
    text = row.get('text')
    if not isinstance(text, str) or not 500 <= len(text) <= 2000000:
        return False
    if 'finepdfs' in name:
        code = {'lt':'lit_Latn','lv':'lvs_Latn'}[language]
        if row.get('full_doc_lid') != code or (row.get('full_doc_lid_score') or 0) < .9:
            return False
        scores = row.get('fw_edu_scores') or []
        if not scores or sum(scores)/len(scores) < 2:
            return False
    return True


def clean_window(text, seed, source):
    if source.startswith(('Wikipedia_', 'Europarl_')):
        text = '\n\n'.join(p.strip() for p in text.splitlines() if p.strip())
    selected = shared.window(text, seed, max_chars=4500)
    if len(selected) < 500 or sum(c.isalpha() for c in selected)/len(selected) < .6:
        raise ValueError('short_or_nonprose')
    if '\ufffd' in selected or any(x in selected for x in ('{gallery}', '<|im_start|>', '<start_of_turn>')):
        raise ValueError('ocr_or_markup')
    # Known corrupt Baltic PDF glyphs; never silently repair unverified originals.
    if source.endswith('finepdfs') and any(x in selected for x in 'ĦĜĥ'):
        raise ValueError('legacy_pdf_glyph_corruption')
    parts = [p.strip() for p in selected.split('\n\n') if p.strip()]
    if len(parts) != len(set(parts)):
        raise ValueError('repeated_paragraphs')
    return selected


def input_rows(path, name):
    for row in rows(path):
        if not name.startswith('Europarl_'):
            yield row
            continue
        # A sitting is hundreds of pages: sample across it, not one window only.
        group, size, index = [], 0, 0
        for paragraph in row['text'].splitlines():
            if group and size + len(paragraph) > 4500:
                yield dict(row, text='\n\n'.join(group), window_group=index)
                group, size, index = [], 0, index+1
            if paragraph.strip():
                group.append(paragraph.strip())
                size += len(paragraph)+2
        if group:
            yield dict(row, text='\n\n'.join(group), window_group=index)


def select_file(job):
    path, name, language, limit, dest = job
    path, dest = Path(path), Path(dest)
    with lock(dest.with_suffix('.lock')):
        sha = file_hash(path)
        receipt = dest.with_suffix('.receipt.json')
        if receipt.exists():
            old = load(receipt)
            if old['input_sha256'] != sha or file_hash(dest) != old['sha256']:
                raise ValueError('Existing text selection changed')
            return old
        heap, counts = [], Counter()
        for ordinal, row in enumerate(input_rows(path,name)):
            counts['scanned'] += 1
            if not document_ok(row, language, name):
                counts['document_screen_rejected'] += 1
                continue
            rank = int(digest([20261003, sha, ordinal])[:16],16)
            if len(heap) >= limit and rank >= -heap[0][0]:
                continue
            try:
                text = clean_window(row['text'], rank, name)
            except ValueError as exc:
                counts[str(exc)] += 1
                continue
            origin = dict(source=name, file=str(path), file_sha256=sha, row=ordinal,
                source_document_id=row.get('source_document_id',row.get('id',ordinal)),
                url=row.get('url'), license=row.get('license'), source_name=row.get('source_name'),
                source_id=row.get('source_id'), document_type=row.get('document_type'),
                window_group=row.get('window_group'),
                window_seed=rank, paragraph_structure='original', source_holdouts_included=True)
            entry = (-rank,ordinal,text,origin)
            if len(heap) < limit:
                heapq.heappush(heap,entry)
            else:
                heapq.heapreplace(heap,entry)
        with atomic(dest) as out:
            for _,_,text,origin in sorted(heap,reverse=True):
                out.write(json.dumps(dict(text=text, language=language, provenance=origin),ensure_ascii=False)+'\n')
        counts['selected'] = len(heap)
        result = dict(source=name, language=language, path=str(dest), counts=dict(counts),
            input_sha256=sha, sha256=file_hash(dest), quota=limit)
        write_json(receipt,result)
        print(name,path.name,dict(counts),flush=True)
        return result


def select(root, workers):
    sources = {}
    for entry in load(root/'local-sources.json'):
        sources[entry['name']] = (entry['language'],[Path(entry['path'])])
    for lang in ('lt','lv'):
        path = root/'parlamint'/lang/'documents.jsonl'
        if not (path.parent/'receipt.json').exists():
            raise ValueError('ParlaMint not ready: '+lang)
        sources['parlamint_'+lang]=(lang,[path])
    cfg = load('config/dfm13_baltic_sources.json')
    for source in cfg['sources']:
        if source['kind']=='text':
            files=sorted((root/'downloads'/source['name']).rglob('*.parquet'))
            if not files:
                raise ValueError('Missing text files')
            sources[source['name']]=(source['language'], files)
    jobs=[]
    for name,(lang,files) in sources.items():
        for index,path in enumerate(files):
            suffix = '-sitting-windows' if name.startswith('Europarl_') else ''
            jobs.append((str(path),name,lang,math.ceil(60000/len(files)),
                         str(root/'text-windows'/name/f'{index:04d}{suffix}.jsonl')))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        receipts=list(pool.map(select_file,jobs))
    write_json(root/'text-windows/manifest.json',receipts)


def make_source(job):
    root,name,lang,files,targets=job
    root=Path(root)
    render=renderer()
    dest=root/'transforms'/name
    with lock(dest/'.lock'):
        receipt=dest/'receipt.json'
        pins={str(p):file_hash(p) for p in files}
        if receipt.exists():
            old=load(receipt)
            if old['inputs']!=pins or old['sha256']!=file_hash(dest/'candidates.jsonl'):
                raise ValueError('Transformation input changed')
            return old
        counts,seen=Counter(),set()
        with atomic(dest/'candidates.jsonl') as out:
            for path in files:
                for row in rows(path):
                    key=digest(row['text'])
                    if key in seen:
                        continue
                    seen.add(key)
                    for task,limit in targets.items():
                        if counts[task]>=limit:
                            continue
                        try:
                            record=transform(row['text'],lang,task,row['provenance'],20261003)
                            record['rendered_tokens']=render.count(record['messages'])
                        except ValueError as exc:
                            counts['rejected:'+str(exc)]+=1
                            continue
                        record.update(admission_authorized=False,audit_status='pending')
                        out.write(json.dumps(record,ensure_ascii=False)+'\n')
                        counts[task]+=1
        result=dict(source=name,language=lang,counts=dict(counts),candidate_targets=targets,
            inputs=pins,sha256=file_hash(dest/'candidates.jsonl'),audit='pending')
        write_json(receipt,result)
        print('TRANSFORMS',name,dict(counts),flush=True)
        return result


def make(root,workers):
    inputs=load(root/'text-windows/manifest.json')
    baseline=load('data/dfm12/baselines.json')
    groups={}
    for entry in inputs:
        groups.setdefault((entry['source'],entry['language']),[]).append(Path(entry['path']))
    jobs=[]
    for (name,lang),files in groups.items():
        n=sum(l==lang for _,l in groups)
        targets={task:math.ceil(v['target_per_language']*1.5/n) for task,v in baseline['tasks'].items()}
        jobs.append((str(root),name,lang,files,targets))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results=list(pool.map(make_source,jobs))
    write_json(root/'transforms/manifest.json',dict(sources=results,baseline='data/dfm12/baselines.json',
        baseline_sha256=file_hash('data/dfm12/baselines.json'),candidate_factor=1.5,
        policy='equal source quotas; shortfalls explicit; no source repeats'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['select','make'])
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--workers',type=int,default=16)
    args=p.parse_args()
    (select if args.stage=='select' else make)(args.root,args.workers)


if __name__=='__main__':
    main()
