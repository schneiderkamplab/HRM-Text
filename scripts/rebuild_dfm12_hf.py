"""Isolated HF-only DFM12 reconstruction and exact historical comparison."""
import argparse,fcntl,gzip,json,os,shutil,subprocess,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import numpy as np
import yaml
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.acquire_dfm10_hf import save,sha
from scripts.replay_dfm_serial import equal_arrays
from scripts.dfm_hf_gate import require_dfm10,digest
QUEUE=ROOT/'data/rebuild_hf_dfm/serial-queue';WORK=QUEUE/'dfm12'
CONFIG=ROOT/'config/data/dfm12_hf_rebuild.json'
FIELDS=('inst_start','inst_len','resp_start','resp_len')
STAGES=('acquire','materialize','tokenize','verify-tasks','sample-additions','combine','compare')


def require_dfm11(queue=QUEUE):
    require_dfm10(queue)
    w=queue/'dfm11';r=json.loads((w/'verified.json').read_text())
    cfg=ROOT/'config/data/dfm11_hf_rebuild.json'
    inp=json.loads((w/'inputs-verified.json').read_text());tok=json.loads((w/'all-token-comparison.json').read_text())
    if (r.get('version')!=11 or r.get('status')!='matched' or r.get('verified_files')!=41
        or r.get('input_policy')!='HF-only plus lexdk/DBC' or inp.get('config_sha256')!=digest(cfg)
        or inp.get('predecessor')!=require_dfm10(queue) or tok.get('status')!='matched' or tok.get('tasks')!=290):
        raise ValueError('DFM11 exact HF-only gate failed')
    if not (w/'sampled/metadata.json').is_file():raise ValueError('DFM11 sampled base missing')
    return {'receipt_sha256':sha(w/'verified.json'),'config_sha256':sha(cfg),'sampled':str(w/'sampled')}


def source_files(component,package):
    expected=[Path(p).name.split('__',1)[1] for p in component['tokenized_parts']]
    if package['repo_id'].split('/')[-1].startswith('dala-'):
        task=component['name'].rsplit('-',1)[1]
        files=sorted(k for k in package['files'] if k.startswith('data/'+task+'/train-'))
        if not files:raise ValueError('Missing DaLA train files')
        return files,'pair-order-50000'
    selected=[]
    for name in expected:
        found=[k for k in package['files'] if k.startswith('data/') and Path(k).name==name]
        if len(found)!=1:raise ValueError('Ambiguous/missing HF training file '+component['name']+'/'+name)
        selected.append(found[0])
    return selected,'copy'


def prepare():
    d=json.loads((WORK/'discovery.json').read_text());assert not d['errors']
    components=[];packages={}
    for t in d['components']:
        package=next(p for p in d['packages'].values() if t['name'] in p['components'])
        files,mode=source_files(t,package)
        p=packages.setdefault(package['repo_id'],{'revision':package['revision'],'files':{}})
        for f in files:p['files'][f]=package['files'][f]
        components.append(dict(t,repo_id=package['repo_id'],files=files,mode=mode))
    if len(components)!=381 or sum(len(c['tokenized_parts']) for c in components)!=1325:raise ValueError('Inventory drift')
    code=WORK/'code';code.mkdir(exist_ok=True)
    for rel,name,repo,rev in [('scripts/tokenize_chat_template.py','adapter.py',ROOT,'f9b588f'),('sample_tokenized.py','sampler.py',ROOT/'data_io','1f52b10')]:
        (code/name).write_bytes(subprocess.check_output(['git','show',rev+':'+rel],cwd=repo))
    # Freeze the deterministic historical composition implementation; no acquisition code is executed from it.
    shutil.copyfile(ROOT/'dfm12/build_training.py',code/'combine.py')
    from huggingface_hub import HfApi
    for repo,p in packages.items():
        if repo.split('/')[-1].startswith('dala-'):
            info=HfApi().dataset_info(repo,revision=p['revision'],files_metadata=True)
            f=next(x for x in info.siblings if x.rfilename=='provenance/train.pairs.jsonl.gz')
            p['files'][f.rfilename]={'bytes':f.size,'sha256':f.lfs.sha256,'git_blob':f.blob_id}
    cfg={'recipe':'dfm12-hf-v1','epochs':3,'components':components,'packages':packages,
         'registry_sha256':sha(ROOT/'data/sampled_dfm12/source-registry.json'),
         'reference_metadata':json.loads((ROOT/'data/sampled_dfm12/metadata.json').read_text()),
         'tokenizer_info':json.loads((ROOT/'data/dfm14/inheritance-reconciliation/dfm12_tokenized/tokenizer_info.json').read_text()),
         'code':{p.name:sha(p) for p in code.glob('*.py')},
         'tokenizer_sha256':sha(QUEUE/'dfm11/tokenizer/tokenizer.json'),
         'template_sha256':sha(ROOT/'data_io/chat_templates/gemma4_native_chat.jinja')}
    if CONFIG.exists() and json.loads(CONFIG.read_text())!=cfg:raise ValueError('Refuse to replace frozen DFM12 lock')
    save(CONFIG,cfg)
    print('Prepared',len(packages),'HF packages, 381 components, 1325 tasks',flush=True)


def checked_config():
    cfg=json.loads(CONFIG.read_text())
    for n,h in cfg['code'].items():
        if sha(WORK/'code'/n)!=h:raise ValueError('Frozen code changed '+n)
    if sha(QUEUE/'dfm11/tokenizer/tokenizer.json')!=cfg['tokenizer_sha256']:raise ValueError('Tokenizer changed')
    if sha(ROOT/'data_io/chat_templates/gemma4_native_chat.jinja')!=cfg['template_sha256']:raise ValueError('Template changed')
    return cfg


def acquire(cfg):
    from huggingface_hub import hf_hub_download
    def fetch(repo,p,rel,item):
        dest=WORK/'downloads'/repo.split('/')[-1]
        path=dest/rel
        if path.exists() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256']:
            return
        path=Path(hf_hub_download(repo,rel,repo_type='dataset',revision=p['revision'],local_dir=dest))
        if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:raise ValueError('HF file digest mismatch '+repo+'/'+rel)
    with ThreadPoolExecutor(max_workers=16) as pool:
        fs=[pool.submit(fetch,r,p,k,v) for r,p in cfg['packages'].items() for k,v in p['files'].items()]
        for i,f in enumerate(as_completed(fs),1):
            f.result()
            if i%100==0:print('Acquired',i,'/',len(fs),flush=True)
    save(WORK/'inputs-verified.json',{'config_sha256':sha(CONFIG),'packages':len(cfg['packages'])})


def materialize_component(c):
    stage=WORK/'inputs'/c['name'];stage.mkdir(parents=True,exist_ok=True)
    receipt=WORK/'materialized'/ (c['name']+'.json');receipt.parent.mkdir(parents=True,exist_ok=True)
    if receipt.exists():
        for n,h in json.loads(receipt.read_text()).items():
            if sha(stage/n)!=h:raise ValueError('Staged source changed')
        return
    sources=[WORK/'downloads'/c['repo_id'].split('/')[-1]/f for f in c['files']]
    expected=[Path(p).name.split('__',1)[1] for p in c['tokenized_parts']]
    if c['mode']=='copy':
        for src,n in zip(sources,expected):
            p=stage/n
            if not p.exists():p.symlink_to(src.resolve())
    else:
        # HF chat shards are shuffled. Restore the producer provenance pair order,
        # emitting clean then corrupted, using published chat values unchanged.
        import sqlite3
        import tempfile
        fd,temporary=tempfile.mkstemp(prefix=c['name']+'-',suffix='.sqlite')
        os.close(fd);dbpath=Path(temporary)
        db=sqlite3.connect(dbpath);db.execute('PRAGMA journal_mode=OFF');db.execute('PRAGMA synchronous=OFF')
        db.execute('CREATE TABLE rows(pair TEXT, variant TEXT, payload TEXT, PRIMARY KEY(pair,variant)) WITHOUT ROWID')
        for src in sources:
            with gzip.open(src,'rt',encoding='utf-8') as f:
                for line in f:
                    row=json.loads(line);meta=row['metadata']
                    if meta['split']!='train':raise ValueError('Heldout row in train input')
                    db.execute('INSERT INTO rows VALUES (?,?,?)',(meta['pair_id'],meta['variant'],line))
        db.commit();handles=None;count=0
        provenance=WORK/'downloads'/c['repo_id'].split('/')[-1]/'provenance/train.pairs.jsonl.gz'
        try:
            with gzip.open(provenance,'rt',encoding='utf-8') as pairs:
                for line in pairs:
                    pair=json.loads(line)
                    for variant in ('clean','corrupted'):
                        found=db.execute('SELECT payload FROM rows WHERE pair=? AND variant=?',(pair['pair_id'],variant)).fetchone()
                        if found is None:raise ValueError('Missing published pair variant '+variant)
                        if count%50000==0:
                            if handles:handles.close()
                            index=count//50000
                            if index>=len(expected):raise ValueError('Too many DaLA rows')
                            handles=gzip.open(stage/expected[index],'wt',encoding='utf-8',compresslevel=1)
                        handles.write(found[0]);count+=1
        finally:
            if handles:handles.close()
            db.close()
            dbpath.unlink()
        if count!=c['rows']:raise ValueError(f'DaLA row count {count} != {c["rows"]}')
    if {p.name for p in stage.iterdir()}!=set(expected):raise ValueError('Source shard inventory mismatch')
    save(receipt,{n:sha(stage/n) for n in expected})


def materialize(cfg):
    with ThreadPoolExecutor(max_workers=16) as pool:
        for f in as_completed([pool.submit(materialize_component,c) for c in cfg['components']]):f.result()
    shutil.copyfile(QUEUE/'dfm11/tokenizer/tokenizer.json',WORK/'tokenizer.json')
    shutil.copyfile(ROOT/'data_io/chat_templates/gemma4_native_chat.jinja',WORK/'template.jinja')
    save(WORK/'prefix.json',[{'prefix':c['name']+'__','repeat':c['repeat'],'long_context':'drop'} for c in cfg['components']])


def tokenize(cfg):
    subprocess.run([sys.executable,str(WORK/'code/adapter.py'),str(WORK/'inputs'),'-o',str(WORK/'tokenized'),
        '--tokenizer-path',str(WORK/'tokenizer.json'),'--chat-template',str(WORK/'template.jinja'),
        '--max-seq-len','4096','--workers','32'],check=True)
    save(WORK/'tokenized/tokenizer_info.json',cfg['tokenizer_info'])


def verify_tasks(cfg):
    done=0
    for c in cfg['components']:
        for reference in c['tokenized_parts']:
            ref=ROOT/reference;name=ref.name
            for field in ('tokens',)+FIELDS:
                equal_arrays(np.load(WORK/'tokenized'/name/(field+'.npy'),mmap_mode='r'),np.load(ref/(field+'.npy'),mmap_mode='r'),name+'/'+field)
            done+=1
            if done%100==0:print('Compared DFM12 additions',done,'/1325',flush=True)
    save(WORK/'all-token-comparison.json',{'status':'matched','tasks':done,'config_sha256':sha(CONFIG)})


def sample_additions(cfg):
    subprocess.run([sys.executable,str(WORK/'code/sampler.py'),f'tokenized_path={WORK/"tokenized"}',
        f'output_path={WORK/"sampled_additions"}',f'prefix_config_path={WORK/"prefix.json"}',
        'epochs=3','seed=0','concat_workers=4','skip_unmatched=true','default_long_context=drop','context_size=4097','min_resp_length=1'],check=True)


def combine(cfg):
    import importlib.util
    spec=importlib.util.spec_from_file_location('dfm12.hf_frozen_combine',WORK/'code/combine.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    # Isolated metadata wrappers make historical path checks use verified HF tokenizer/template bytes.
    for label,src in [('base',QUEUE/'dfm11/sampled'),('extra',WORK/'sampled_additions')]:
        dest=WORK/('combine-'+label);dest.mkdir(exist_ok=True)
        for p in src.iterdir():
            if p.name=='tokens.npy' or p.name.startswith('epoch_'):
                t=dest/p.name
                if not t.exists():t.symlink_to(p.resolve())
        meta=json.loads((src/'metadata.json').read_text());meta['tokenizer_info']['tokenizer_path']=str(WORK/'tokenizer.json');meta['tokenizer_info']['chat_template_path']=str(WORK/'template.jinja');save(dest/'metadata.json',meta)
    if not (WORK/'sampled/metadata.json').exists():
        m.combine(WORK/'combine-base',WORK/'combine-extra',WORK/'sampled',3)
    p=WORK/'sampled/metadata.json';meta=json.loads(p.read_text());meta['tokenizer_info']=cfg['reference_metadata']['tokenizer_info'];save(p,meta)


def compare(cfg):
    files=[Path('tokens.npy')]+[Path(f'epoch_{i}')/(f+'.npy') for i in range(3) for f in FIELDS]
    for f in files:
        print('Comparing',f,flush=True);equal_arrays(np.load(WORK/'sampled'/f,mmap_mode='r'),np.load(ROOT/'data/sampled_dfm12'/f,mmap_mode='r'),str(f))
    if json.loads((WORK/'sampled/metadata.json').read_text())!=cfg['reference_metadata']:raise ValueError('Final metadata differs')
    save(WORK/'verified.json',{'version':12,'status':'matched','verified_files':13,'input_policy':'HF-only plus lexdk/DBC','config_sha256':sha(CONFIG),'predecessor':require_dfm11()})


def run():
    schedule=json.loads((WORK/'schedule.json').read_text());state_path=WORK/'scheduled-progress.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else {'completed':[]}
    with (WORK/'scheduled-runner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            cfg=checked_config()
            for name,expected in schedule['runtime_sha256'].items():
                if sha(ROOT/name)!=expected:raise ValueError('Scheduled runtime changed: '+name)
            if sha(CONFIG)!=schedule['config_sha256']:raise ValueError('Scheduled lock changed')
            while True:
                try:parent=require_dfm11();break
                except FileNotFoundError:
                    state.update(status='waiting',phase='DFM11 exact HF-only verification');save(state_path,state);time.sleep(30)
            if 'predecessor' in state and state['predecessor']!=parent:raise ValueError('Predecessor changed')
            state['predecessor']=parent
            for stage in STAGES:
                checked_config()
                if require_dfm11()!=parent:raise ValueError('Predecessor changed')
                if stage in state['completed']:continue
                state.update(status='running',phase=stage);state.pop('error',None);save(state_path,state)
                globals()[stage.replace('-','_')](cfg)
                state['completed'].append(stage);save(state_path,state)
            state.update(status='matched',phase='complete');save(state_path,state)
        except Exception as e:
            state.update(status='blocked',error=str(e));save(state_path,state);raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('prepare','preflight','run'));a=parser.parse_args()
    if a.stage=='prepare':prepare()
    elif a.stage=='preflight':
        c=checked_config();print(json.dumps({'packages':len(c['packages']),'components':len(c['components']),'tasks':sum(len(t['tokenized_parts']) for t in c['components']),'stages':STAGES,'config_sha256':sha(CONFIG)},indent=2))
    else:run()
