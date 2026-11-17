"""Preserve DFM15 epochs and interleave complete, context-eligible DFM16 additions."""
import argparse
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('inst_start', 'inst_len', 'resp_start', 'resp_len')
# Repeat, source-domain category (0 neutral, 1 math/code/agent, 2 language).
POLICY = {
    'nvidia/Nemotron-RL-knowledge-mcqa': (2, 0),
    'nvidia/OpenScienceReasoning-2': (1, 1),
    'Lexmount/WebJev': (1, 1),
    'osunlp/Mind2Web': (1, 1),
    'AgentGym/AgentTraj-L': (2, 1),
    'tasksource/nli4ct': (3, 0),
    'copenlu/fever_gold_evidence': (3, 0),
    'LocalLLaMA/typed-decisions': (3, 0),
    'ZefanCai/Open-Jev': (1, 0),
    'ZefanCai/Open-Jev-v1.1': (1, 0),
    'bigcode/commitpackft': (2, 1),
    'emozilla/quality': (3, 2),
    'qiaojin/PubMedQA': (2, 0),
    'local/executable-curriculum': (3, 1),
    'schneiderkamplab/synth-kg-text-hetionet': (1, 0),
    'oliverkinch/dynaword-no-bt': (1, 2),
    'danish-foundation-models/norwegian-dynaword': (1, 2),
    'danish-foundation-models/swedish-dynaword': (1, 2),
}


def write_json(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(tmp, path)


def eligible(arrays, limit):
    return (arrays['inst_len'] + arrays['resp_len'] <= limit) & (arrays['resp_len'] > 0)


def interleave(old, added, positions, order, start, end):
    indexes = np.arange(start, end, dtype=np.int64)
    ranks = np.searchsorted(positions, indexes)
    left, right = np.searchsorted(positions, [start, end])
    mask = np.zeros(end-start, dtype=bool)
    mask[positions[left:right]-start] = True
    values = np.empty(end-start, dtype=old.dtype)
    values[~mask] = old[indexes[~mask]-ranks[~mask]]
    values[mask] = added[order[left:right]]
    return values, mask


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=ROOT/'incoming/mimir-xl-20261015/data/sampled_dfm15')
    parser.add_argument('--output', type=Path, default=ROOT/'data/sampled_dfm16')
    parser.add_argument('--additional-source', type=Path, action='append', default=[],
                        help='Prepared source receipt to append; never modifies an existing sample')
    args = parser.parse_args()
    base, target = args.base.resolve(), args.output.resolve()
    stage = target.with_name(target.name+'.building')
    with target.with_suffix('.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if target.exists():
            raise FileExistsError(target)
        stage.mkdir(exist_ok=True)
        metadata = json.loads((base/'metadata.json').read_text())
        expected = json.loads((base/'validated.json').read_text())
        assert hashlib.sha256((base/'metadata.json').read_bytes()).hexdigest() == expected['metadata_sha256']
        limit = metadata['max_seq_len']
        backing = np.load(base/'tokens.npy', mmap_mode='r')
        assert len(backing) == expected['stored_tokens']
        sources = json.loads((ROOT/'data/dfm16/decisions-v1/preparation_summary.json').read_text())
        assert not sources['pending']
        sources = sources['sources'] + [json.loads((ROOT/'data/dfm16/hetionet/prepared.json').read_text())]
        sources += [json.loads(path.read_text()) for path in args.additional_source]
        if len({source['repo_id'] for source in sources}) != len(sources):
            raise ValueError('Duplicate source receipts')
        template_hash = hashlib.sha256((base/'chat_template.jinja').read_bytes()).hexdigest()
        tokenizer = (ROOT/metadata['tokenizer_info']['tokenizer_path']).resolve()
        tokenizer_hash = hashlib.sha256(tokenizer.read_bytes()).hexdigest()
        pieces = {k: [] for k in (*FIELDS, 'category_id')}
        totals, payloads = [], []
        offset = len(backing)
        for source in sources:
            assert source['template_sha256'] == template_hash
            assert source['tokenizer_sha256'] == tokenizer_hash
            repeat, category = POLICY[source['repo_id']]
            rows = tokens = rejected = 0
            for path in sorted(Path(source['tokenized_path']).rglob('inst_len.npy')):
                arrays = {k: np.load(path.parent/(k+'.npy'), mmap_mode='r') for k in FIELDS}
                payload = np.load(path.parent/'tokens.npy', mmap_mode='r')
                assert payload.dtype.kind in 'iu' and backing.dtype.kind in 'iu'
                keep = eligible(arrays, limit)
                rejected += int((~keep).sum())
                idx = np.flatnonzero(keep)
                rows += len(idx)
                tokens += int((arrays['inst_len'][idx]+arrays['resp_len'][idx]).sum(dtype=np.uint64))
                for prefix in ('inst', 'resp'):
                    starts, lengths = arrays[prefix+'_start'][idx], arrays[prefix+'_len'][idx]
                    assert np.all(starts <= len(payload)) and np.all(lengths <= len(payload)-starts)
                for k in FIELDS:
                    values = arrays[k][idx].astype(np.uint64)
                    pieces[k].append(np.tile(values+(offset if k.endswith('_start') else 0), repeat))
                pieces['category_id'].append(np.full(len(idx)*repeat, category, dtype=np.uint8))
                payloads.append(payload)
                offset += len(payload)
            assert rows + rejected == source['rows']
            totals.append(dict(repo_id=source['repo_id'], repeat=repeat, category=category,
                               eligible_rows=rows, eligible_tokens=tokens, excluded_rows=rejected,
                               sampled_rows=rows*repeat, sampled_tokens=tokens*repeat))
        added = {k: np.concatenate(v) for k, v in pieces.items()}
        added_tokens = sum(t['sampled_tokens'] for t in totals)
        write_json(stage/'additions.json', totals)
        print(json.dumps(totals, indent=2), flush=True)
        # A private copy is essential: never append to a hard link to DFM15.
        token_receipt = stage/'tokens-complete.json'
        if not token_receipt.exists():
            print('Copying inherited token store (reflink if supported)', flush=True)
            subprocess.run(['cp', '--reflink=auto', '--sparse=always', str(base/'tokens.npy'), str(stage/'tokens.npy')], check=True)
            from scripts.build_dfm15_full_sample import append_tokens
            stored = append_tokens(stage/'tokens.npy', payloads, len(backing))
            assert stored == offset
            write_json(token_receipt, {'stored_tokens': stored})
        assert np.load(stage/'tokens.npy', mmap_mode='r').shape == (offset,)
        reports = []
        for original in expected['epochs']:
            epoch = original['epoch']
            folder = stage/f'epoch_{epoch}'
            folder.mkdir(exist_ok=True)
            nnew = len(added['inst_start'])
            nold = original['rows']
            n = nold+nnew
            rng = np.random.default_rng(16000+epoch)
            positions = np.sort(rng.choice(n, nnew, replace=False))
            order = rng.permutation(nnew)
            keys = list(FIELDS)
            if (base/f'epoch_{epoch}/category_id.npy').exists():
                keys.append('category_id')
            total = inherited_total = 0
            for k in keys:
                old = np.load(base/f'epoch_{epoch}'/(k+'.npy'), mmap_mode='r')
                assert len(old) == nold
                dest = np.lib.format.open_memmap(folder/(k+'.npy'), mode='w+', dtype=old.dtype, shape=(n,))
                for start in range(0, n, 1_000_000):
                    end = min(n, start+1_000_000)
                    values, mask = interleave(old, added[k], positions, order, start, end)
                    dest[start:end] = values
                    if k.endswith('_len'):
                        total += int(values.sum(dtype=np.uint64))
                        inherited_total += int(values[~mask].sum(dtype=np.uint64))
                dest.flush()
                del dest
            assert inherited_total == original['tokens']
            assert total == original['tokens']+added_tokens
            # Read back every index, checking exact inherited sequence and new targets.
            for k in keys:
                old = np.load(base/f'epoch_{epoch}'/(k+'.npy'), mmap_mode='r')
                saved = np.load(folder/(k+'.npy'), mmap_mode='r')
                for start in range(0, n, 1_000_000):
                    end = min(n, start+1_000_000)
                    values, _ = interleave(old, added[k], positions, order, start, end)
                    assert np.array_equal(saved[start:end], values)
            np.save(folder/'addition_positions.npy', positions)
            report = dict(epoch=epoch, rows=n, tokens=total, inherited_tokens=original['tokens'], added_tokens=added_tokens)
            reports.append(report)
            write_json(folder/'verified.json', report)
            print('Verified', report, flush=True)
        shutil.copyfile(base/'chat_template.jinja', stage/'chat_template.jinja')
        metadata['total_length'] = round(sum(r['tokens'] for r in reports)/len(reports))
        metadata['vocab_size'] = 262144
        metadata['tokenizer_info']['tokenizer_path'] = str(tokenizer)
        metadata['tokenizer_info']['chat_template_path'] = str(target/'chat_template.jinja')
        metadata['dfm16_sampling'] = {'base': str(base), 'repeat_policy': POLICY, 'seed': 16000,
                                     'inherited_epochs_unchanged': True, 'length_limit': limit}
        write_json(stage/'metadata.json', metadata)
        receipt = dict(base=str(base), epochs=reports, additions=totals, stored_tokens=offset,
                       metadata_sha256=hashlib.sha256((stage/'metadata.json').read_bytes()).hexdigest())
        write_json(stage/'validated.json', receipt)
        write_json(stage/'ready.json', receipt)
        stage.rename(target)
        print('READY', target, flush=True)


if __name__ == '__main__':
    main()
