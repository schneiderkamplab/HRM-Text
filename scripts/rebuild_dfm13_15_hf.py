"""HF-only DFM13–15 serial execution; exact receipts gate every successor."""
import argparse,fcntl,gzip,importlib.util,json,os,shutil,subprocess,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor,as_completed
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import rebuild_dfm12_hf as common
from scripts.acquire_dfm10_hf import save,sha
from scripts.replay_dfm_serial import equal_arrays
Q=common.QUEUE;FIELDS=common.FIELDS

def work(v):return Q/f'dfm{v}'
def config(v):return ROOT/f'config/data/dfm{v}_hf_rebuild.json'
def load(p):return json.loads(Path(p).read_text())
def refsample(v):return ROOT/(f'data/sampled_dfm{v}' if v<15 else 'data/dfm15/native-reasoning-v2/sampled_dfm15')
def require(v):
 if v==11:return common.require_dfm11()
 parent=require(v-1);w=work(v);r=load(w/'verified.json');c=config(v)
 if r.get('version')!=v or r.get('status')!='matched' or r.get('verified_files')!=13 or r.get('input_policy')!='HF-only plus lexdk/DBC' or r.get('config_sha256')!=sha(c) or r.get('predecessor')!=parent:
  raise ValueError(f'DFM{v} exact HF gate failed')
 return {'receipt_sha256':sha(w/'verified.json'),'config_sha256':sha(c),'sampled':str(w/'sampled')}

def files_for(v,c,p):
 files=sorted(k for k in p['files'] if k.startswith(('data/','train/')))
 if 'dala' in c['name']:
  task='acceptability' if c['name'].endswith('acceptability') else 'correction'
  files=[f for f in files if f.startswith('data/'+task+'/train_representative')]
 else:files=[f for f in files if 'train' in Path(f).name and f.endswith(('.parquet','.jsonl','.jsonl.gz'))]
 if not files:raise ValueError('No train files '+c['name'])
 return files

def tokenization_policy(v,name,nonwave):
 full=v==13 and (name in nonwave or '_synthetic_' in name or
     name.startswith('dfm13_tlpc_grounded_') or name in ('setur_fo_instruct','hendrycks_math_worked'))
 cap=None if full else 4096
 rows=None if v==14 else (25000 if 'dala' in name else (2000 if full else 5000))
 return cap,rows


def prepare(v):
 w=work(v);w.mkdir(exist_ok=True);code=w/'code';code.mkdir(exist_ok=True)
 for n in ('adapter.py','sampler.py','combine.py'):shutil.copyfile(work(12)/'code'/n,code/n)
 cfg={'recipe':f'dfm{v}-hf-v1','version':v,'epochs':3,'reference_metadata':load(refsample(v)/'metadata.json'),
      'tokenizer_info':load(work(12)/'tokenized/tokenizer_info.json'),'code':{p.name:sha(p) for p in code.glob('*.py')},
      'runtime':{p:sha(ROOT/p) for p in ['scripts/rebuild_dfm13_15_hf.py','scripts/rebuild_dfm12_hf.py','dfm12/io.py']}}
 if v<15:
  d=load(w/'discovery.json');assert not d['errors'];cfg['components']=d['components'];packages={}
  nonwave=set(__import__('dfm12.nonwave_assembly',fromlist=['NAMES']).NAMES)
  for c in cfg['components']:
   p=d['packages'][c['hf_repo_id']];files=files_for(v,c,p);c['files']=files
   pp=packages.setdefault(c['hf_repo_id'],{'revision':p['revision'],'files':{}})
   for f in files:pp['files'][f]=p['files'][f]
   c['tasks']=[Path(x).name if v==13 else c['name']+f'__part-{i:06d}.jsonl' for i,x in enumerate(c['tokenized_parts'])]
   c['cap'],c['part_rows']=tokenization_policy(v,c['name'],nonwave)
  cfg['packages']=packages
 else:
  cfg['components']=[];cfg['packages']={}
  cfg['repair_runtime']={p:sha(ROOT/p) for p in ['dfm14/build_native_reasoning.py','dfm14/native_reasoning.py','dfm14/repair_reasoning.py','dfm12/build_training.py','dfm14/reconcile_inheritance.py']}
  cfg['repair_inventory_reference']=load(ROOT/'data/dfm15/native-reasoning-v2/inventory.json')
 if config(v).exists() and load(config(v))!=cfg:raise ValueError('Frozen recipe changed')
 save(config(v),cfg);print('Prepared DFM',v,'packages',len(cfg['packages']),flush=True)

def checked(v):
 c=load(config(v));w=work(v)
 for n,h in c['code'].items():
  if sha(w/'code'/n)!=h:raise ValueError('Frozen code changed')
 for p,h in {**c['runtime'],**c.get('repair_runtime',{})}.items():
  if sha(ROOT/p)!=h:raise ValueError('Frozen runtime changed '+p)
 return c

def acquire(v,c):
 w=work(v)
 def fetch(repo,p,rel,item):
  path=w/'downloads'/repo.replace('/','--')/rel;path.parent.mkdir(parents=True,exist_ok=True)
  if path.exists() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256']:return
  tmp=path.with_suffix(path.suffix+'.download');url=f'https://huggingface.co/datasets/{repo}/resolve/{p["revision"]}/{rel}?download=true'
  subprocess.run(['curl','--fail','--location','--silent','--show-error','--connect-timeout','30','--max-time','600','--retry','3','--retry-delay','3','-o',str(tmp),url],check=True,timeout=2500)
  if tmp.stat().st_size!=item['bytes'] or sha(tmp)!=item['sha256']:raise ValueError('HF digest mismatch '+repo+'/'+rel)
  tmp.replace(path)
 with ThreadPoolExecutor(max_workers=16) as pool:
  futures=[pool.submit(fetch,r,p,k,i) for r,p in c['packages'].items() for k,i in p['files'].items()]
  for i,f in enumerate(as_completed(futures),1):
   f.result()
   if i%100==0:print('Acquired',i,'/',len(futures),flush=True)
 save(w/'inputs-verified.json',{'config_sha256':sha(config(v)),'predecessor':require(v-1)})

def rows(path):
 if path.suffix=='.parquet':
  import pyarrow.parquet as pq
  for batch in pq.ParquetFile(path).iter_batches(batch_size=256):yield from batch.to_pylist()
 else:
  opener=gzip.open if path.name.endswith('.gz') else open
  with opener(path,'rt',encoding='utf-8') as f:
   for line in f:
    if line.strip():yield json.loads(line)

def materialize_one(v,c):
 w=work(v);receipt=w/'materialized'/(c['name']+'.json');receipt.parent.mkdir(parents=True,exist_ok=True)
 folder=w/('inputs-capped' if c['cap'] else 'inputs-full');folder.mkdir(exist_ok=True)
 if receipt.exists():
  for n,h in load(receipt)['files'].items():
   if sha(folder/n)!=h:raise ValueError('Materialized input changed')
  return
 files=[w/'downloads'/c['hf_repo_id'].replace('/','--')/f for f in c['files']]
 handles=None;count=0;index=-1;parts={};nfiles=len(files)
 try:
  for file_i,src in enumerate(files):
   for row in rows(src):
    if 'messages_json' in row:
     row=dict(row,messages=json.loads(row['messages_json']),tools=json.loads(row.get('tools_json') or '[]'))
     row['target_message_index']=max(i for i,m in enumerate(row['messages']) if m['role']=='assistant')
    if 'dala' in c['name']:
     if row.get('split')!='train':raise ValueError('Heldout DaLA row')
     if v==13:
      desired='recovery' if '_recovery_' in c['name'] else 'baseline'
      if row.get('publication_pool','baseline')!=desired:continue
    if c['name']=='setur_fo_instruct':
     row={'messages':[{'role':'user','content':row['instruction']},{'role':'assistant','content':row['output']}],'target_message_index':1}
    new=(file_i if v==14 else count//c['part_rows'])
    if c['name'] in ('setur_fo_instruct','hendrycks_math_worked'):new=0
    if new!=index:
     if handles:handles.close()
     index=new
     if index>=len(c['tasks']):raise ValueError('More source shards than reference '+c['name'])
     path=folder/c['tasks'][index];opener=gzip.open if path.name.endswith('.gz') else open
     handles=opener(path,'wt',encoding='utf-8');parts[path.name]=path
    handles.write(json.dumps(row,ensure_ascii=False)+'\n');count+=1
 finally:
  if handles:handles.close()
 if set(parts)!=set(c['tasks']):raise ValueError('Missing source shards '+c['name'])
 save(receipt,{'rows':count,'files':{n:sha(p) for n,p in parts.items()}})

def materialize(v,c):
 with ThreadPoolExecutor(max_workers=16) as pool:
  for f in as_completed([pool.submit(materialize_one,v,x) for x in c['components']]):f.result()

def tokenize(v,c):
 w=work(v)
 for group,extra in [('capped',['--max-seq-len','4096']),('full',[])]:
  source=w/('inputs-'+group)
  if not source.exists():continue
  subprocess.run([sys.executable,str(w/'code/adapter.py'),str(source),'-o',str(w/'raw-tokenized'),
    '--tokenizer-path',str(work(12)/'tokenizer.json'),'--chat-template',str(work(12)/'template.jinja'),'--workers','32']+extra,check=True)
 # Historical assembly removes complete overlength rows, retaining order and repacking tokens.
 out=w/'tokenized';out.mkdir(exist_ok=True)
 for component in c['components']:
  for name in component['tasks']:
   src=w/'raw-tokenized'/name;dest=out/name
   if (dest/'metadata.json').exists():continue
   a={f:np.load(src/(f+'.npy'),mmap_mode='r') for f in ('tokens',)+FIELDS}
   keep=(a['inst_len'].astype('uint64')+a['resp_len'])<=4096
   if keep.all():
    if not dest.exists():dest.symlink_to(src.resolve(),target_is_directory=True)
    continue
   dest.mkdir(exist_ok=True);indices={f:np.asarray(a[f][keep]).copy() for f in FIELDS};size=int((indices['inst_len']+indices['resp_len']).sum());tokens=np.lib.format.open_memmap(dest/'tokens.npy',mode='w+',dtype=a['tokens'].dtype,shape=(size,));offset=0
   for i in range(len(indices['inst_len'])):
    for prefix in ('inst','resp'):
     start=int(indices[prefix+'_start'][i]);length=int(indices[prefix+'_len'][i]);tokens[offset:offset+length]=a['tokens'][start:start+length];indices[prefix+'_start'][i]=offset;offset+=length
   tokens.flush()
   for f in FIELDS:np.save(dest/(f+'.npy'),indices[f])
   save(dest/'metadata.json',{'overlength_rows_removed':int((~keep).sum())})
 save(out/'tokenizer_info.json',c['tokenizer_info'])

def verify_tasks(v,c):
 w=work(v);done=0
 for component in c['components']:
  for name,reference in zip(component['tasks'],component['tokenized_parts']):
   ref=Path(reference);ref=ref if ref.is_absolute() else ROOT/ref
   for f in ('tokens',)+FIELDS:equal_arrays(np.load(w/'tokenized'/name/(f+'.npy'),mmap_mode='r'),np.load(ref/(f+'.npy'),mmap_mode='r'),name+'/'+f)
   done+=1
   if done%100==0:print('Compared',done,flush=True)
 save(w/'all-token-comparison.json',{'status':'matched','tasks':done,'config_sha256':sha(config(v))})

def sample(v,c):
 w=work(v);tree=w/'sampling-tree';tree.mkdir(exist_ok=True)
 for comp in c['components']:
  for i,n in enumerate(comp['tasks']):
   name=n if v==13 else comp['name']+f'__part-{i:06d}'
   target=tree/name
   if not target.exists():target.symlink_to((w/'tokenized'/n).resolve(),target_is_directory=True)
 save(tree/'tokenizer_info.json',c['tokenizer_info']);save(w/'prefix.json',[{'prefix':x['name']+'__','repeat':x['repeat'],'long_context':'drop'} for x in c['components']])
 subprocess.run([sys.executable,str(w/'code/sampler.py'),f'tokenized_path={tree}',f'output_path={w/"sampled_additions"}',f'prefix_config_path={w/"prefix.json"}','epochs=3','seed=0','concat_workers=4','skip_unmatched=true','default_long_context=drop','context_size=4097','min_resp_length=1'],check=True)

def combine(v,c):
 w=work(v);spec=importlib.util.spec_from_file_location('dfm12.hf_combine',w/'code/combine.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 for label,src in [('base',work(v-1)/'sampled'),('extra',w/'sampled_additions')]:
  dest=w/('combine-'+label);dest.mkdir(exist_ok=True)
  for p in src.iterdir():
   if p.name=='tokens.npy' or p.name.startswith('epoch_'):
    if not (dest/p.name).exists():(dest/p.name).symlink_to(p.resolve())
  meta=load(src/'metadata.json');meta['tokenizer_info']['tokenizer_path']=str(work(12)/'tokenizer.json');meta['tokenizer_info']['chat_template_path']=str(work(12)/'template.jinja');save(dest/'metadata.json',meta)
 if not (w/'sampled/metadata.json').exists():m.combine(w/'combine-base',w/'combine-extra',w/'sampled',3)
 meta=load(w/'sampled/metadata.json');meta['tokenizer_info']=c['reference_metadata']['tokenizer_info'];save(w/'sampled/metadata.json',meta)

def repair(v,c):
 from dfm14.build_native_reasoning import repair_part
 from dfm14.native_reasoning import native_template
 from dfm14.repair_reasoning import build_sample
 w=work(v);base=work(14)/'sampled';parts=[]
 # Reconstruct source offsets exclusively from verified rebuilt DFM11 and DFM12 arrays.
 offset=0;targets={x['name'] for x in c['repair_inventory_reference']['parts']}
 for tree in [work(11)/'union',work(12)/'tokenized']:
  for path in sorted(tree.iterdir()):
   if not path.is_dir():continue
   tokens=np.load(path/'tokens.npy',mmap_mode='r');n=len(tokens)
   if path.name in targets:parts.append({'path':str(path.resolve()),'name':path.name,'offset':offset,'tokens':n,'norwegian':path.name.startswith('dfm12-norwegian-')})
   offset+=n
 if {x['name'] for x in parts}!=targets:raise ValueError('Missing repaired source')
 old=c['repair_inventory_reference']['parts']
 if [(x['name'],x['offset'],x['tokens']) for x in parts]!=[(x['name'],x['offset'],x['tokens']) for x in old]:raise ValueError('Repair offsets differ')
 (w/'chat_template.jinja').write_text(native_template());save(w/'inventory.json',{'parts':parts,'base':str(base)})
 jobs=[(str(w),str(base),e,str(work(12)/'tokenizer.json')) for e in parts]
 with ProcessPoolExecutor(max_workers=32) as pool:
  results=[]
  for result in pool.map(repair_part,jobs):results.append(result);print('Repaired',result['name'],flush=True)
 save(w/'repairs.json',{'mode':'native_thinking_and_direct_v2','parts':results})
 for e in results:
  for f in ('tokens','valid')+FIELDS:
   equal_arrays(np.load(w/'tokenized'/e['name']/(f+'.npy'),mmap_mode='r'),np.load(ROOT/'data/dfm15/native-reasoning-v2/tokenized'/e['name']/(f+'.npy'),mmap_mode='r'),e['name']+'/'+f)
 build_sample(w,base,results,native=True,output_name='sampled')
 meta=load(w/'sampled/metadata.json');meta['tokenizer_info']=c['reference_metadata']['tokenizer_info'];meta['reasoning_policy']=c['reference_metadata']['reasoning_policy'];save(w/'sampled/metadata.json',meta)

def compare(v,c):
 w=work(v);files=[Path('tokens.npy')]+[Path(f'epoch_{i}')/(f+'.npy') for i in range(3) for f in FIELDS]
 for f in files:print('Comparing',f,flush=True);equal_arrays(np.load(w/'sampled'/f,mmap_mode='r'),np.load(refsample(v)/f,mmap_mode='r'),str(f))
 if load(w/'sampled/metadata.json')!=c['reference_metadata']:raise ValueError('Sample metadata differs')
 save(w/'verified.json',{'version':v,'status':'matched','verified_files':13,'input_policy':'HF-only plus lexdk/DBC','config_sha256':sha(config(v)),'predecessor':require(v-1)})

def run(v):
 w=work(v);p=w/'scheduled-progress.json';state=load(p) if p.exists() else {'completed':[]};stages=('acquire','materialize','tokenize','verify_tasks','sample','combine','compare') if v<15 else ('repair','compare')
 with (w/'scheduled-runner.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   checked(v)
   while True:
    try:parent=require(v-1);break
    except FileNotFoundError:state.update(status='waiting',phase=f'DFM{v-1} exact HF verification');save(p,state);time.sleep(30)
   if state.get('predecessor',parent)!=parent:raise ValueError('Predecessor changed')
   state['predecessor']=parent
   for stage in stages:
    c=checked(v)
    if require(v-1)!=parent:raise ValueError('Predecessor changed')
    if stage in state['completed']:continue
    state.update(status='running',phase=stage);state.pop('error',None);save(p,state);globals()[stage](v,c);state['completed'].append(stage);save(p,state)
   state.update(status='matched',phase='complete');save(p,state)
  except Exception as e:state.update(status='blocked',error=str(e));save(p,state);raise

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['prepare','run','preflight']);p.add_argument('--version',type=int,choices=[13,14,15],required=True);a=p.parse_args()
 if a.stage=='prepare':prepare(a.version)
 elif a.stage=='preflight':c=checked(a.version);print('Preflight',a.version,'components',len(c['components']),'files',sum(len(p['files']) for p in c['packages'].values()))
 else:run(a.version)
