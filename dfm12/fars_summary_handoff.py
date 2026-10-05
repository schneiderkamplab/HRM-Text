"""CPU-only completion delta and actual-tokenizer preflight for held summaries."""
import argparse
from collections import Counter
from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import time

from . import fars_summary_packets as packets
from . import fars_summary_deferral as deferral
from .io import digest, file_hash, load, lock, write_json


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def delta(base, authorization, root):
    root.mkdir(parents=True, exist_ok=True)
    with lock(root / '.lock'):
        if (root / 'manifest.json').exists():
            raise ValueError('Delta already frozen; choose a new root for later completions')
        manifest = packets.verify(base)
        proposal, _ = deferral.load_proposal(authorization)
        sources = packets.SourceRows(manifest['downloads'])
        counts, readiness = Counter(), Counter()
        pins = {str(base/'manifest.json'):file_hash(base/'manifest.json'),
                str(base/'snapshot.sqlite'):manifest['snapshot_sha256'],
                str(authorization/'receipt.json'):file_hash(authorization/'receipt.json'),
                str(authorization/'proposal.json'):file_hash(authorization/'proposal.json'),
                str(Path(__file__).resolve()):file_hash(__file__),
                str(Path(deferral.__file__).resolve()):file_hash(deferral.__file__),
                **manifest['pins']}
        with closing(readonly(base/'snapshot.sqlite')) as prior, closing(readonly(proposal['queue'])) as live, closing(sqlite3.connect(root/'packets.sqlite')) as out:
            out.execute('CREATE TABLE packets(component TEXT,id TEXT,packet TEXT,sha256 TEXT,error TEXT,PRIMARY KEY(component,id))')
            out.execute('CREATE TABLE inventory(id TEXT PRIMARY KEY,component TEXT,status TEXT,payload TEXT,result TEXT,payload_sha256 TEXT,disposition TEXT)')
            out.execute('CREATE TABLE content_keys(key TEXT PRIMARY KEY)')
            live.execute('BEGIN')
            authorized = deferral.authorized_jobs(authorization,live)
            for key,raw,status,result in live.execute("SELECT id,payload,status,result FROM jobs WHERE stage='generate' "
                    "AND json_extract(payload,'$.record.component') IN (?,?) ORDER BY rowid", packets.COMPONENTS):
                original = json.loads(raw)['record']
                component = original['component']
                state = deferral.handoff_state(key,status,raw,authorized)
                readiness[state] += 1
                old = prior.execute('SELECT status,result FROM queue_snapshot WHERE id=?',(key,)).fetchone()
                if old and old == (status,result):
                    continue
                disposition, candidate = state, None
                if state == 'unfinished31B_authorized':
                    candidate = original
                elif status == 'done':
                    try:
                        candidate = packets.completed_repair(original,json.loads(result))
                        disposition = 'completed26B_requires31B_review'
                    except (ValueError,KeyError,TypeError) as exc:
                        disposition = 'structurally_unusable: ' + str(exc)
                if candidate is not None:
                    parent = candidate['provenance'].get('repair_parent',candidate['id'])
                    content_key = digest([component,parent,candidate['messages']])
                    already = prior.execute('SELECT 1 FROM candidates WHERE content_key=?',(content_key,)).fetchone()
                    if already or out.execute('INSERT OR IGNORE INTO content_keys VALUES(?)',(content_key,)).rowcount == 0:
                        disposition += ': duplicate_content_already_queued'
                    else:
                        try:
                            provenance = candidate['provenance']
                            relative = provenance['file']
                            source_path = str((Path(manifest['downloads'])/relative).resolve())
                            upstream = sources.get(relative,provenance['row'])
                            packet = packets.packet(component,'job:'+key,json.dumps(candidate),disposition,
                                upstream,dict(file=relative,row=provenance['row'],file_sha256=manifest['pins'][source_path]))
                            packet['ledger_row_id'] = parent
                            packet['unfinished31B'] = True
                            packet['origin_job_payload_sha256'] = deferral.payload_hash(raw)
                            packet['deferral_receipt_sha256'] = pins[str(authorization/'receipt.json')] if status==deferral.STATUS else None
                            encoded,sha,error = json.dumps(packet,ensure_ascii=False),digest(packet),None
                        except (ValueError,KeyError,TypeError) as exc:
                            encoded,sha,error = None,None,str(exc)
                        out.execute('INSERT INTO packets VALUES(?,?,?,?,?)',(component,key,encoded,sha,error))
                out.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?)',
                    (key,component,status,raw,result,deferral.payload_hash(raw),disposition))
                counts[disposition] += 1
            out.commit()
            prepared,blocked = out.execute('SELECT count(*),coalesce(sum(error IS NOT NULL),0) FROM packets').fetchone()
        receipt = dict(created=time.time(),model=packets.MODEL,pins=pins,
            packets_sha256=file_hash(root/'packets.sqlite'),prepared=prepared,blocked=blocked,
            dispositions=dict(counts),handoff_states=dict(readiness),
            migration_ready=not readiness['blocked_nonterminal_not_authorized'],
            quality_review_complete=False,admission_authorized=False,
            later_completions_require_another_delta=True)
        write_json(root/'manifest.json',receipt)
        write_json(root/'seal.json',dict(manifest_sha256=file_hash(root/'manifest.json')))
        return receipt


def tokenizer_init(directory):
    global TOKENIZER
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['OMP_NUM_THREADS'] = '1'
    from transformers import AutoTokenizer
    TOKENIZER = AutoTokenizer.from_pretrained(directory,local_files_only=True,fix_mistral_regex=False)


def measure_request(request, tokenizer, context):
    if request['model'] != packets.MODEL or request['chat_template_kwargs'] != {'enable_thinking':True}:
        raise ValueError('Unexpected model or template mode')
    ids = tokenizer.apply_chat_template(request['messages'],tokenize=True,
        add_generation_prompt=True,enable_thinking=True)
    if isinstance(ids,Mapping):
        ids = ids['input_ids']
    if not isinstance(ids,list) or not all(type(i) is int for i in ids):
        raise ValueError('Expected flat token IDs')
    reserve = request['max_tokens']
    if type(reserve) is not int or reserve <= 0:
        raise ValueError('Invalid output reservation')
    return dict(prompt_tokens=len(ids),output_tokens=reserve,total_tokens=len(ids)+reserve,
        context_limit=context,fits=len(ids)+reserve<=context,token_ids_sha256=digest(ids),truncated=False)


def measure_item(item):
    component,key,raw,context = item
    try:
        packet = json.loads(raw)
        measured = measure_request(packet['audit_request'],TOKENIZER,context)
        return component,key,json.dumps(measured),None
    except Exception as exc:
        return component,key,None,f'{type(exc).__name__}: {exc}'


def preflight(packet_root, output, ready_path, limit=10000, workers=4, context=32768):
    if not 1<=limit<=10000 or not 1<=workers<=8 or context!=32768:
        raise ValueError('Bounded 1..10000 rows, 1..8 CPU workers and explicit 32768 planning context required')
    output.mkdir(parents=True,exist_ok=True)
    with lock(output/'.lock'):
        if (output/'seal.json').exists():
            seal = load(output/'seal.json')
            if (file_hash(output/'manifest.json')!=seal['manifest_sha256']
                    or file_hash(output/'budgets.sqlite')!=seal['budgets_sha256']):
                raise ValueError('Completed preflight drift')
        ready = load(ready_path)
        if ready['model']!=packets.MODEL or ready.get('all_files_verified') is not True:
            raise ValueError('Verified31B model receipt required')
        directory = Path(ready['snapshot'])
        tokenizer_pins = {}
        for name in ('tokenizer.json','tokenizer_config.json','chat_template.jinja','config.json'):
            entry = next(f for f in ready['files'] if f['name']==name)
            actual = file_hash(directory/name)
            if actual!=entry['local_sha256']:
                raise ValueError('Tokenizer/model metadata drift: '+name)
            tokenizer_pins[str(directory/name)] = actual
        if (packet_root/'cpu-complete-receipt.json').exists():
            packet_sha = load(packet_root/'cpu-complete-receipt.json')['packets_sha256']
        else:
            if file_hash(packet_root/'manifest.json')!=load(packet_root/'seal.json')['manifest_sha256']:
                raise ValueError('Delta manifest drift')
            packet_sha = load(packet_root/'manifest.json')['packets_sha256']
        if file_hash(packet_root/'packets.sqlite')!=packet_sha:
            raise ValueError('Packet database drift')
        config = dict(model=packets.MODEL,revision=ready['revision'],tokenizer_pins=tokenizer_pins,
            ready_sha256=file_hash(ready_path),packets_sha256=packet_sha,context_limit=context,
            fix_mistral_regex=False,enable_thinking=True,code_sha256=file_hash(__file__),
            server_context_verified=False,live_model_context_recheck_required_before_dispatch=True)
        if (output/'manifest.json').exists():
            if load(output/'manifest.json')!=config:
                raise ValueError('Preflight configuration drift')
        else:
            write_json(output/'manifest.json',config)
        with closing(sqlite3.connect(output/'budgets.sqlite')) as db:
            db.execute('CREATE TABLE IF NOT EXISTS budgets(component TEXT,id TEXT,result TEXT,error TEXT,PRIMARY KEY(component,id))')
            db.execute('ATTACH DATABASE ? AS source',((packet_root/'packets.sqlite').resolve().as_uri()+'?mode=ro',))
            todo = db.execute('SELECT component,id,packet FROM source.packets p WHERE error IS NULL AND NOT EXISTS '
                '(SELECT 1 FROM budgets b WHERE b.component=p.component AND b.id=p.id) ORDER BY component,id LIMIT ?',(limit,)).fetchall()
            if todo:
                with ProcessPoolExecutor(max_workers=workers,initializer=tokenizer_init,initargs=(str(directory),)) as pool:
                    for row in pool.map(measure_item,((c,k,r,context) for c,k,r in todo),chunksize=16):
                        db.execute('INSERT INTO budgets VALUES(?,?,?,?)',row)
                db.commit()
            total = db.execute('SELECT count(*) FROM source.packets WHERE error IS NULL').fetchone()[0]
            done,errors = db.execute('SELECT count(*),coalesce(sum(error IS NOT NULL),0) FROM budgets').fetchone()
            oversized = db.execute("SELECT count(*) FROM budgets WHERE json_extract(result,'$.fits')=0").fetchone()[0]
            result = dict(total=total,measured=done,remaining=total-done,errors=errors,oversized=oversized,
                cpu_only=True,network_requests=0,live_context_verification_required=True,
                repairs_and_fresh_reaudits_require_new_content_specific_preflight=True)
            write_json(output/'progress.json',result)
        if not result['remaining']:
            write_json(output/'seal.json',dict(manifest_sha256=file_hash(output/'manifest.json'),
                budgets_sha256=file_hash(output/'budgets.sqlite')))
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('delta')
    d.add_argument('--base',type=Path,required=True)
    d.add_argument('--authorization',type=Path,required=True)
    d.add_argument('--root',type=Path,required=True)
    f=sub.add_parser('preflight')
    f.add_argument('--packets',type=Path,required=True)
    f.add_argument('--root',type=Path,required=True)
    f.add_argument('--ready',type=Path,default=Path('data/dfm13/wave4/gemma31-download/ready.json'))
    f.add_argument('--limit',type=int,default=10000)
    f.add_argument('--workers',type=int,default=4)
    args=p.parse_args()
    result=delta(args.base,args.authorization,args.root) if args.command=='delta' else preflight(args.packets,args.root,args.ready,args.limit,args.workers)
    print(json.dumps(result))


if __name__=='__main__':
    main()
