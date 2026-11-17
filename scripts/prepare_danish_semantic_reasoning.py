"""Prepare local evaluation-only records from pinned upstream archives; no training export."""
import argparse,ast,collections,csv,hashlib,io,json,re,subprocess,zipfile
from pathlib import Path
REVISION='dea3cb506c3d68ebb3e70b04320f094b93320607'
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'evaluation/data/danish_semantic_reasoning_upstream'
OUT=ROOT/'evaluation/data/danish_semantic_reasoning'


def choice(values,gold):
    assert len(values)==len(set(values)) and values.count(gold)==1,'ambiguous answer choices'
    assert 2<=len(values)<=26
    labels='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    return '\n'.join(f'{labels[i]}. {v}' for i,v in enumerate(values)),labels[values.index(gold)],list(labels[:len(values)])


def convert(family,member,row,header):
    meta={};notes=[]
    if family in ('inference','entailment'):
        fields=[x.strip() for x in row if x.strip()]
        if len(fields)<3:raise ValueError('missing premise, statement or gold label')
        raw=fields[2].lower()
        if member.endswith('inference_constitutive_wholePart.txt'):
            assert re.fullmatch(r'(true|false) holo_member',raw)
            raw=raw.split()[0];notes.append('split documented label/relation field')
        assert raw in ('true','false','neutral'),'invalid/missing truth label'
        gold={'true':'sandt','false':'falsk','neutral':'ukendt'}[raw]
        labels=['sandt','falsk','ukendt'] if family=='entailment' else ['sandt','falsk']
        intro='Situation' if family=='entailment' else 'Eksempler på sande udsagn'
        prompt=f'{intro}: {fields[0]}\n\nUdsagn: {fields[1]}\n\n'
        prompt+=('Vurder udsagnet ud fra situationen. Svar ukendt, hvis sandhedsværdien ikke kan afgøres. ' if family=='entailment' else 'Vurder om det sidste udsagn er sandt eller falsk ud fra ordenes betydning. ')
        prompt+='Svar kun med '+', '.join(labels)+'.'
        if len(fields)>3:meta['relation']=fields[3]
        if any(not x.strip() for x in row):notes.append('ignored empty TSV fields')
    else:
        if family=='similarity':
            assert len(row)==6
            values=ast.literal_eval(row[0]);gold=row[1];position=int(row[2]);assert values[position]==gold
            options,gold,labels=choice(values,gold)
            prompt='Hvilket ord passer betydningsmæssigt dårligst sammen med de øvrige ord?\n'+options+'\nSvar kun med bogstavet.'
            meta.update(group_id=row[3],chapter=row[4],section=row[5])
        else:
            assert len(row)==len(header),'column count mismatch'
            d=dict(zip(header,row))
            if family=='synonymy':
                options,gold,labels=choice(ast.literal_eval(d['candidates']),d['label'])
                prompt=f'Hvilket ord er det nærmeste synonym til "{d["target"]}"?\n{options}\nSvar kun med bogstavet.'
                meta['section']=d['section']
            elif family=='danwic':
                assert d['label'] in ('same_sense','different_sense')
                gold='ja' if d['label']=='same_sense' else 'nej';labels=['ja','nej']
                prompt=f'Ordet er "{d["target"]}".\n1: {d["first_context"]}\n2: {d["second_context"]}\nHar ordet samme betydning i begge sætninger? Svar kun ja eller nej.'
                meta['source_id']=d['idx']
            elif family=='sentiment':
                gold=str(int(d['label']));labels=[str(i) for i in range(-3,4)];assert gold in labels
                prompt=f'Tekst: {d["context"]}\nMålord: {d["target"]} (formen "{d["form"]}").\nVurder målordets sentiment i denne kontekst fra -3 (mest negativt) til 0 (neutralt) til 3 (mest positivt). Svar kun med tallet.'
            elif family=='dameta':
                gold=d['label'].strip();labels=list('ABCD');assert gold in labels
                assert sorted([gold,d['lit_dis'],d['fig_dis'],d['con_dis']])==labels,'distractor labels do not form a permutation'
                prompt=f'Hvad betyder "{d["word"]}" i denne sætning?\n{d["sentence"]}\nVælg den korrekte omskrivning:\n'+'\n'.join(f'{k}. {d[k]}' for k in labels)+'\nSvar kun med bogstavet.'
                meta.update({k:d[k] for k in ['lit_dis','fig_dis','con_dis','type','domain','source']})
            else:raise ValueError(family)
    return prompt,gold,labels,meta,notes


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=SOURCE);p.add_argument('--out',type=Path,default=OUT);args=p.parse_args()
    rev=subprocess.check_output(['git','-C',str(args.source),'rev-parse','HEAD'],text=True).strip();assert rev==REVISION,'unexpected upstream revision'
    assert not args.out.exists(),'Refusing to overwrite a prepared evaluation'
    records=[];excluded=[];files=[];notes=[]
    for archive in sorted(args.source.rglob('*.zip')):
        family={'metaphor_benchmark':'dameta'}.get(archive.parent.name,archive.parent.name)
        with zipfile.ZipFile(archive) as basic:
            aes=any(i.compress_type==99 for i in basic.infolist())
        if aes:
            import pyzipper
            opener=pyzipper.AESZipFile
        else:opener=zipfile.ZipFile
        files.append({'path':str(archive.relative_to(args.source)),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
        with opener(archive) as z:
            for member in sorted(z.namelist()):
                if member.startswith('__MACOSX') or not member.endswith(('.txt','.tsv')):continue
                rows=list(csv.reader(io.StringIO(z.read(member,pwd=b'benchmark').decode('utf-8-sig')),delimiter='\t'))
                header=None
                if family not in ('inference','entailment'):header=rows[0]
                for line,row in enumerate(rows,1):
                    if (header is not None and line==1) or row==['a','b','c','d']:continue
                    identity=f'{archive.relative_to(args.source)}:{member}:{line}'
                    if not any(x.strip() for x in row):
                        excluded.append({'id':identity,'reason':'blank row','family':family});continue
                    try:prompt,gold,labels,meta,normalizations=convert(family,member,row,header)
                    except (AssertionError,ValueError,KeyError,IndexError,SyntaxError) as e:
                        excluded.append({'id':identity,'reason':str(e) or type(e).__name__,'family':family});continue
                    subset=Path(member).stem
                    records.append({'id':identity,'family':family,'subset':subset,'input':prompt,'target':gold,'labels':labels,'metadata':meta})
                    if normalizations:notes.append({'id':identity,'normalizations':normalizations})
    args.out.mkdir(parents=True)
    data=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records)
    (args.out/'records.jsonl').write_text(data)
    report={'upstream_revision':rev,'archives':files,'counts':dict(collections.Counter(r['family'] for r in records)),'subsets':dict(collections.Counter(r['subset'] for r in records)), 'excluded':excluded,'normalizations':notes,'records_sha256':hashlib.sha256(data.encode()).hexdigest(),'evaluation_only':True,'protocol':'local zero-shot v1; not a reproduction of published prompting'}
    (args.out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:report[k] for k in ['counts','excluded']},ensure_ascii=False))
if __name__=='__main__':main()
