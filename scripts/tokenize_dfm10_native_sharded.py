"""Resume native DFM10 tasks with row-group shards and exact ordered joins."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.acquire_dfm10_hf import sha,save
from scripts.replay_dfm_serial import equal_arrays
from scripts.queue_dfm_hf_rebuild import safe_tokenizer_workers
FIELDS=('tokens','inst_start','inst_len','resp_start','resp_len')


def complete(output, source, max_seq_len):
    if not all((output/(f+'.npy')).is_file() for f in FIELDS) or not (output/'metadata.json').is_file():
        return False
    m=json.loads((output/'metadata.json').read_text());st=source.stat()
    return (m.get('source_size')==st.st_size and m.get('source_mtime')==int(st.st_mtime)
            and m.get('max_seq_len')==max_seq_len and m.get('preserve_first_user') is True)


def run(work, config):
    cfg=json.loads(config.read_text())
    for task in [t for t in cfg['tasks'] if t['native']]:
        name=task['task'];source=work/'sources_native'/name;output=work/'tokenized_native'/name
        if complete(output,source,cfg['native_max_seq_len']):
            print('Retained completed native task',name,flush=True)
            continue
        if sha(source)!=task['sha256']:
            raise ValueError('Native input changed: '+name)
        stage=work/'native_sharded'/name;stage.mkdir(parents=True,exist_ok=True)
        split=stage/'inputs';receipt=stage/'split-verified.json'
        if not receipt.exists():
            subprocess.run([sys.executable,str(ROOT/'scripts/shard_dfm7_large_parquets.py'),
                '--input',str(source),'--output',str(split),'--columns','messages','source_file','upstream_metadata','--force'],check=True)
            manifest=json.loads((split/'manifest.json').read_text())
            save(receipt,{'source_sha256':task['sha256'],'rows':manifest['num_source_rows'],
                          'shards':[{'path':x['path'],'sha256':sha(split/x['path'])} for x in manifest['shards']]})
        proof=json.loads(receipt.read_text())
        if proof['source_sha256']!=task['sha256']:raise ValueError('Shard source receipt changed')
        for item in proof['shards']:
            if sha(split/item['path'])!=item['sha256']:raise ValueError('Native shard changed')
        tokens=stage/'tokenized'
        subprocess.run([sys.executable,str(work/'native_adapter.py'),str(split),'-o',str(tokens),
            '--tokenizer-path',str(work/'tokenizer/tokenizer.json'),'--chat-template',str(work/'chat_template.jinja'),
            '--workers',str(min(64,safe_tokenizer_workers())),'--max-seq-len',str(cfg['native_max_seq_len']),
            '--preserve-first-user'],check=True)
        actual={p.name for p in tokens.iterdir() if p.is_dir() and p.name.startswith('part-')}
        if actual!={s['path'] for s in proof['shards']}:raise ValueError('Native shard inventory differs')
        joined=tokens/name
        if not (joined/'joined_shards.json').exists():
            subprocess.run([sys.executable,str(ROOT/'scripts/join_tokenized_shards.py'),
                '--tokenized-root',str(tokens),'--shard-prefix','part-','--output-name',name,'--source-file',str(source)],check=True)
        for f in FIELDS:
            equal_arrays(np.load(joined/(f+'.npy'),mmap_mode='r'),
                         np.load(ROOT/'data/tokenized_dfm10'/name/(f+'.npy'),mmap_mode='r'),name+'/'+f)
        metadata=json.loads((joined/'metadata.json').read_text())
        metadata.update(max_seq_len=cfg['native_max_seq_len'],preserve_first_user=True)
        save(joined/'metadata.json',metadata)
        save(stage/'comparison.json',{'status':'matched','task':name,'arrays':5,'shards':len(proof['shards']),'source_sha256':task['sha256']})
        if output.exists() or output.is_symlink():
            raise ValueError('Refusing to overwrite existing native output: '+str(output))
        output.symlink_to(joined.resolve(),target_is_directory=True)
        print('Verified sharded native task',name,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--config',type=Path,required=True)
    a=p.parse_args();run(a.work.resolve(),a.config.resolve())
