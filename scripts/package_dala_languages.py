"""One deduplicated DaLA v2 publication per language, never one per pool."""
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
import sqlite3
import time
from dfm12.io import atomic, digest, file_hash, load, lock, write_json
from scripts.package_dala_completed import ROOTS


def identity(row):
    return digest(dict(task=row['task'], messages=row['messages'],
                       tools=row.get('tools', []), target_message_index=row['target_message_index']))


def select(db, row, split, pool):
    key = identity(row)
    old = db.execute('SELECT split,pool FROM seen WHERE id=?', (key,)).fetchone()
    if old:
        if old[0] != split:
            raise ValueError('Exact conversation crosses publication splits')
        return False, key, old[1]
    db.execute('INSERT INTO seen VALUES(?,?,?)', (key, split, pool))
    return True, key, None


def package(language, groups, output):
    required = {'baseline', 'recovery'} if language in ('nl', 'fa') else {'baseline'}
    if set(groups) != required:
        raise ValueError('Incomplete language pools')
    pins = {pool: dict(path=str(path/'integration.json'), sha256=file_hash(path/'integration.json'))
            for pool, path in groups.items()}
    name = 'dfm13-dala-v2-'+language+'-compact'; root = output/name
    with lock(output/(name+'.lock')):
        if (root/'ready.json').exists():
            result = load(root/'ready.json')
            if result['integration_pins'] != pins: raise ValueError('Language package input drift')
            return result
        stage = root.with_name(root.name+'.building')
        if stage.exists(): raise ValueError('Interrupted package requires explicit recovery: '+str(stage))
        stage.mkdir(parents=True)
        db = sqlite3.connect(stage/'dedup.sqlite')
        db.execute('CREATE TABLE seen(id TEXT PRIMARY KEY,split TEXT,pool TEXT) WITHOUT ROWID')
        inputs = defaultdict(list); exports = {}; counts = {}; duplicates = 0
        # Recovery already won training overlap selection; preserve that precedence.
        for pool in sorted(groups, key=lambda x: x != 'recovery'):
            result = load(groups[pool]/'integration.json')
            if result['status'] != 'complete_train_only': raise ValueError('Unfinished group')
            pin = result['export']
            if file_hash(pin['path']) != pin['sha256']: raise ValueError('Export drift')
            export = load(pin['path']); exports[pool] = export
            for item in export['files']:
                parts = Path(item['relative']).parts
                if len(parts)==3 and parts[0]=='exports' and parts[1] in ('acceptability','correction'):
                    inputs[(parts[1], parts[2].removesuffix('.jsonl.gz'))].append((pool,item))
        files = {}
        with (stage/'dedup-provenance.jsonl').open('w') as evidence:
            for (task, split), sources in sorted(inputs.items()):
                path = stage/'data'/task/(split+'.jsonl.gz'); path.parent.mkdir(parents=True,exist_ok=True)
                count = 0
                with gzip.open(path,'wt',encoding='utf-8',compresslevel=1) as out:
                    for pool, item in sources:
                        if file_hash(item['path']) != item['sha256']: raise ValueError('Source shard drift')
                        with gzip.open(item['path'],'rt') as stream:
                            for ordinal,line in enumerate(stream):
                                row=json.loads(line)
                                if row['language']!=language or row['task']!=task or row['split']+'_'+row['view']!=split:
                                    raise ValueError('Task/language/split mismatch')
                                keep,key,owner=select(db,row,split,pool)
                                if not keep:
                                    duplicates+=1
                                    evidence.write(json.dumps(dict(fingerprint=key,task=task,split=split,pool=pool,
                                        retained_pool=owner,source=item['path'],ordinal=ordinal,
                                        provenance=row.get('provenance')),ensure_ascii=False)+'\n')
                                    continue
                                row['publication_pool']=pool
                                out.write(json.dumps(row,ensure_ascii=False)+'\n');count+=1
                db.commit();counts[task+':'+split]=count;files[str(path.relative_to(stage))]=file_hash(path)
        db.close()
        write_json(stage/'source-receipts.json',exports)
        with atomic(stage/'README.md') as out:
            out.write('---\nlanguage: ['+('pt' if language=='pt-PT' else language)+']\ntask_categories: [text-generation]\nconfigs:\n')
            for task in ('acceptability','correction'):
                out.write('- config_name: '+task+'\n  data_files:\n')
                for t, split in sorted(inputs):
                    if t==task:
                        out.write('  - split: '+('train' if split=='train_representative' else split)+'\n    path: data/'+task+'/'+split+'.jsonl.gz\n')
            out.write('---\n\n# '+name+'\n\nOne language dataset combining accepted baseline and recovery pools where available. '
                'Exact native conversations are deduplicated within each task/split; split conflicts fail closed. '
                'Full native messages, target indices and source provenance are preserved; publication_pool records origin. '
                'Task configs separate acceptability and correction; heldout views never become train. '
                'Automated compact audits are not native-speaker or producer per-edit certification. '
                'Source-specific terms and attribution remain in row provenance; no blanket relicensing.\n')
        for filename in ('README.md','source-receipts.json','dedup-provenance.jsonl'):
            files[filename]=file_hash(stage/filename)
        result=dict(name=name,hf_repo_id='schneiderkamplab/'+name,language=language,pools=sorted(groups),
            integration_pins=pins,files=files,counts=counts,duplicates_removed=duplicates,
            local_package_ready=True,uploaded=False,one_dataset_per_language=True)
        write_json(stage/'ready.json',result);stage.rename(root)
        return result


def run(output, watch):
    languages=sorted({s['language'] for s in load('data/dfm13/dala-v2-audit34-with-recovery-v1/manifest.json')['sources']})
    with lock(output/'.controller.lock'):
        while True:
            available=defaultdict(dict)
            for root in ROOTS:
                for path in (root/'groups').glob('*/integration.json'):
                    language,pool=path.parent.name.rsplit('-',1)
                    if pool in available[language]:raise ValueError('Ambiguous group owner')
                    available[language][pool]=path.parent
            queue=[dict(language=language,hf_repo_id='schneiderkamplab/dfm13-dala-v2-'+language+'-compact',
                        status='waiting',uploaded=False) for language in languages]
            packages=[];errors=[]
            write_json(output/'queue.json',dict(policy='one_dataset_per_language',expected=34,items=queue,uploaded=False))
            for item in queue:
                language=item['language']
                required={'baseline','recovery'} if language in ('nl','fa') else {'baseline'}
                item['missing_pools']=sorted(required-set(available[language]))
                if not item['missing_pools']:
                    try:
                        result=package(language,available[language],output);packages.append(result);item['status']='local_ready'
                    except Exception as exc:
                        item['status']='error';item['error']=repr(exc);errors.append(item)
                write_json(output/'queue.json',dict(policy='one_dataset_per_language',expected=34,items=queue,uploaded=False))
                write_json(output/'inventory.json',dict(packages=packages,errors=errors,expected_packages=34,
                    complete=False,uploaded=False,one_dataset_per_language=True))
            write_json(output/'inventory.json',dict(packages=packages,errors=errors,expected_packages=34,
                complete=len(packages)==34 and not errors,uploaded=False,one_dataset_per_language=True))
            print('LANGUAGE_PACKAGES',len(packages),'ERRORS',errors,flush=True)
            if not watch or len(packages)==34 and not errors:break
            time.sleep(60)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('exports_dfm13_dala_languages'))
    p.add_argument('--watch',action='store_true');a=p.parse_args();run(a.output,a.watch)
