"""Materialize the attributed ManyThings Slovak bridge and native pivot pairs."""
from concurrent.futures import ProcessPoolExecutor
import io
import json
from pathlib import Path
import sqlite3
import zipfile

from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from dfm14.parallel_expand import eligible, pivot, texts
from dfm14.parallel_report import run as report


def run():
    original=Path('data/dfm14/parallel-v1').resolve()
    previous=Path('data/dfm14/parallel-expansion-v3').resolve()
    root=Path('data/dfm14/parallel-expansion-v4').resolve()
    archive=Path('data/dfm14/translation-gap-search-v1/slk-eng.zip').resolve()
    evidence=load(archive.parent/'report.json')['manythings']
    if file_hash(archive)!=evidence['sha256']:raise ValueError('Changed source ZIP')
    with lock(root/'.controller.lock'):
        cfg=load(previous/'config.json');write_json(root/'config.json',cfg)
        for kind in ('candidates','pivots'):
            (root/kind).mkdir(exist_ok=True)
            for source in (previous/kind).iterdir():
                if (kind=='pivots' and 'sk' in source.name.split('-')) or source.name=='opus-en-sk':continue
                target=root/kind/source.name
                if not target.exists():target.symlink_to(source,target_is_directory=True)
        bridge=root/'candidates/opus-en-sk/candidates.jsonl'
        if not bridge.exists():
            seen=set()
            with zipfile.ZipFile(archive) as z, atomic(bridge) as out:
                if 'creativecommons.org/licenses/by/2.0' not in z.read('_about.txt').decode():
                    raise ValueError('License mismatch')
                for line in io.TextIOWrapper(z.open('slk.txt'),encoding='utf-8'):
                    en,sk,attribution=line.rstrip('\n').split('\t')
                    if 'CC-BY 2.0' not in attribution:raise ValueError('Missing attribution')
                    key=digest(dict(en=en,sk=sk))
                    if key in seen:continue
                    seen.add(key)
                    def conversation(src,dst,text,translation):
                        return [dict(role='user',content=f'Translate from {cfg["languages"][src]} into {cfg["languages"][dst]}. Output only the translation.\n\n{text}'),dict(role='assistant',content=translation)]
                    row=dict(id=key,language='sk',reverse_language='en',pair='en-sk',task='translation',
                        messages=conversation('en','sk',en,sk),reverse_messages=conversation('sk','en',sk,en),
                        rendered_tokens=0,bridge_only=True,training_ready=False,admission_authorized=False,
                        provenance=dict(url=evidence['url'],archive_sha256=evidence['sha256'],license='cc-by-2.0',attribution=attribution))
                    out.write(json.dumps(row,ensure_ascii=False)+'\n')
            write_json(bridge.parent/'receipt.json',dict(rows=len(seen),sha256=file_hash(bridge),bridge_only=True))
        if not (root/'legs-ready.json').exists():
            with sqlite3.connect(f'file:{previous/"legs.sqlite"}?mode=ro',uri=True) as src:
                with sqlite3.connect(root/'legs.sqlite') as dst:
                    src.backup(dst);count=0
                    for row in rows(bridge):
                        values=texts(row)
                        if not eligible(values['en']):continue
                        proof=json.dumps(dict(id=row['id'],provenance=row['provenance'],input=str(bridge)))
                        dst.execute('''INSERT INTO legs(language,anchor,text,evidence) VALUES(?,?,?,?)
                            ON CONFLICT(language,anchor) DO UPDATE SET ambiguous=MAX(legs.ambiguous,legs.text != excluded.text)''',
                            ('sk',values['en'],values['sk'],proof));count+=1
                    dst.commit()
            write_json(root/'legs-ready.json',dict(new_input_legs=count,predecessor=str(previous)))
        pairs=['-'.join(p) for p in cfg['requested_pairs'] if 'sk' in p]
        with ProcessPoolExecutor(max_workers=16) as pool:
            receipts=list(pool.map(pivot,[(root,original,p,cfg) for p in pairs]))
        write_json(root/'slovak-bridge.json',dict(pivots=receipts,training_ready=False))
        report(original=original,expanded=root)


if __name__=='__main__':run()
