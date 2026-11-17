"""Materialize a complete HF task map; fail closed on missing/ambiguous inputs."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import pyarrow as pa
import pyarrow.parquet as pq
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.acquire_dfm10_hf import DEFAULT, save, sha
from scripts.map_dfm10_hf import build


def hrm(row):
    messages = row['messages']
    if len(messages) != 2 or [m['role'] for m in messages] != ['user', 'assistant'] or any(not isinstance(m.get('content'), str) for m in messages):
        raise ValueError('Cannot invert HRM export without a plain user/assistant pair')
    return {'condition': row.get('condition', 'direct'), 'instruction': messages[0]['content'], 'response': messages[1]['content']}


def materialize(source, target, native=False):
    stage = target.with_name(target.name + '.partial')
    if target.suffix == '.parquet':
        if native:
            schema=pa.schema([('messages',pa.list_(pa.struct([('role',pa.string()),('content',pa.string())]))),('source_file',pa.string()),('upstream_metadata',pa.string())])
        else:
            schema = pa.schema([(k, pa.string()) for k in ('condition','instruction','response')])
        with source.open() as inp, pq.ParquetWriter(stage, schema, compression='zstd') as out:
            batch = []
            for line in inp:
                row = json.loads(line)
                if native:
                    if set(row)-set(schema.names) or not isinstance(row.get('messages'),list):
                        raise ValueError('Unexpected native Parquet row schema')
                    if any(set(m)!={'role','content'} or not all(isinstance(m[k],str) for k in ('role','content')) for m in row['messages']):
                        raise ValueError('Unexpected native message schema; refusing field loss')
                    batch.append(row)
                else:
                    if 'condition' not in row:
                        raise ValueError('Parquet without HRM condition needs explicit schema reconstruction')
                    batch.append(hrm(row))
                if len(batch) >= 512:
                    out.write_table(pa.Table.from_pylist(batch, schema=schema)); batch=[]
            if batch:
                out.write_table(pa.Table.from_pylist(batch, schema=schema))
    else:
        opener = gzip.open if target.name.endswith('.gz') else open
        with source.open() as inp, opener(stage, 'wt', encoding='utf-8') as out:
            for line in inp:
                row = json.loads(line)
                if 'condition' in row:
                    row = hrm(row)
                out.write(json.dumps(row, ensure_ascii=False)+'\n')
    stage.replace(target)


def run(work=DEFAULT):
    report = build(work)
    if report['status'] != 'mapped':
        raise ValueError('HF task mapping incomplete; see task-map.json')
    destination = ROOT / 'data/rebuild_hf_dfm/serial-queue/dfm10-hf-v2'
    payloads = destination / 'payloads'
    payloads.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((ROOT / 'config/data/dfm10_hf_rebuild.json').read_text())
    cfg.update(recipe='dfm10-hf-v2', acquisitions=json.loads((work/'hf-lock.json').read_text()), input_policy='HF-only plus lexdk/DBC', provenance_task_map_sha256=sha(work/'task-map.json'))
    old = {t['task']:t for t in cfg['tasks']}
    tasks=[]
    receipts=destination/'materialization-receipts'
    receipts.mkdir(exist_ok=True)
    for number, entry in enumerate(report['mapped'],1):
        source = Path(entry['input']['path'])
        if not entry['input'].get('agreement_exception') and not source.resolve().is_relative_to(work.resolve()):
            raise ValueError('Public source escaped HF staging')
        target = payloads / entry['task']
        receipt_path=receipts/(entry['task']+'.json')
        identity=hashlib.sha256(json.dumps(entry,sort_keys=True).encode()).hexdigest()
        saved=json.loads(receipt_path.read_text()) if receipt_path.exists() else None
        if saved and saved['input_identity']==identity and target.is_file() and sha(target)==saved['sha256']:
            output_sha=saved['sha256']
        else:
            if sha(source) != entry['input']['sha256']:
                raise ValueError('Mapped source changed')
            if entry['input']['format'] == 'original':
                stage=target.with_name(target.name+'.partial')
                shutil.copyfile(source, stage)
                stage.replace(target)
            else:
                materialize(source, target, native=entry['native'])
            output_sha=sha(target)
            save(receipt_path,{'input_identity':identity,'sha256':output_sha})
        if number % 25 == 0 or number==len(report['mapped']):
            print(f'Materialized {number}/{len(report["mapped"])} tasks',flush=True)
        tasks.append(dict(old[entry['task']], source=str(target.relative_to(ROOT)), source_size=target.stat().st_size, sha256=output_sha, hf_provenance=entry['input']))
    cfg['tasks']=tasks
    save(destination/'hf_recipe.json', cfg)
    print('Materialized', len(tasks), 'tasks', flush=True)


if __name__ == '__main__':
    run()
