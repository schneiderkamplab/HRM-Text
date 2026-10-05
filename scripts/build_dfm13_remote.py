"""Transfer frozen DFM12 and registered DFM13 additions; build three epochs.

CPU-only, resumable transfer, exclusive build lock, metadata published last.
Does not launch training or include pending-audit sources.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/work/mimir/HRM-Text'
HOST = 'ucloud@ssh.cloud.sdu.dk'
BUILD = ROOT / 'data/dfm13_build'
SNAPSHOT = BUILD / 'remote'
FIELDS = ('inst_start', 'inst_len', 'resp_start', 'resp_len')
CHUNK = 1_000_000


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(tmp, path)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def run(args, **kwargs):
    print('RUN', shlex.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def transfer(relative, destination, directory=False):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if directory:
        destination.mkdir(parents=True, exist_ok=True)
    run(['rsync', '-aL', '--partial', '--info=progress2', '--bwlimit=524288',
         '-e', 'ssh -p 2850 -o BatchMode=yes',
         f'{HOST}:{REMOTE}/{relative}' + ('/' if directory else ''),
         str(destination) + ('/' if directory else '')])


def merge(base, additions, output, info):
    """Preserve inherited occurrences; shuffle in added rows with pointer offsets."""
    if (output / 'metadata.json').exists():
        print('Already built', output, flush=True)
        return
    output.mkdir(parents=True, exist_ok=True)
    bm, am = read(base/'metadata.json'), read(additions/'metadata.json')
    assert bm['max_seq_len'] == am['max_seq_len'] == 4097
    a = np.load(base/'tokens.npy', mmap_mode='r')
    b = np.load(additions/'tokens.npy', mmap_mode='r')
    assert a.dtype == b.dtype
    signature = {'base_tokens': len(a), 'addition_tokens': len(b),
                 'base_metadata': sha(base/'metadata.json'),
                 'addition_metadata': sha(additions/'metadata.json')}
    receipt = output/'token-copy.json'
    if receipt.exists():
        assert read(receipt) == signature
    else:
        dst = np.lib.format.open_memmap(output/'tokens.npy', mode='w+',
                                      dtype=a.dtype, shape=(len(a)+len(b),))
        for src, offset in ((a, 0), (b, len(a))):
            for start in range(0, len(src), 8*CHUNK):
                end = min(start+8*CHUNK, len(src))
                dst[offset+start:offset+end] = src[start:end]
                if start % (1024*CHUNK) == 0:
                    dst.flush()
                    print('Token copy', offset+end, '/', len(dst), flush=True)
        dst.flush()
        del dst
        write(receipt, signature)
    reports = []
    for epoch in range(3):
        out = output/f'epoch_{epoch}'
        out.mkdir(exist_ok=True)
        arrays = [{f: np.load(p/f'epoch_{epoch}'/(f+'.npy'), mmap_mode='r')
                   for f in FIELDS} for p in (base, additions)]
        n, m = [len(x['inst_len']) for x in arrays]
        for x, count, size in zip(arrays, (n, m), (len(a), len(b))):
            assert all(len(v) == count for v in x.values())
            for start in range(0, count, CHUNK):
                s = slice(start, start+CHUNK)
                assert np.all(x['inst_len'][s]+x['resp_len'][s] <= 4097)
                for prefix in ('inst', 'resp'):
                    assert np.all(x[prefix+'_start'][s]+x[prefix+'_len'][s] <= size)
        perm = np.random.default_rng(epoch).permutation(n+m)
        total = 0
        for field in FIELDS:
            dst = np.lib.format.open_memmap(out/(field+'.npy'), mode='w+',
                                          dtype=np.uint64, shape=(n+m,))
            for start in range(0, n+m, CHUNK):
                p = perm[start:start+CHUNK]
                mask = p < n
                values = np.empty(len(p), dtype=np.uint64)
                values[mask] = arrays[0][field][p[mask]]
                values[~mask] = arrays[1][field][p[~mask]-n]
                if field.endswith('_start'):
                    values[~mask] += len(a)
                else:
                    total += int(values.sum())
                dst[start:start+len(p)] = values
            dst.flush()
            del dst
        del perm
        reports.append(dict(epoch=epoch, rows=n+m, inherited_rows=n,
                            added_rows=m, tokens=total))
        print('Merged', reports[-1], flush=True)
    write(output/'build-receipt.json', dict(inputs=signature, epochs=reports,
                                           registry_sha256=sha(BUILD/'sources.json')))
    bm.update(tokenizer_info=info, total_length=round(sum(r['tokens'] for r in reports)/3))
    write(output/'metadata.json', bm)


def main():
    os.chdir(ROOT)
    BUILD.mkdir(parents=True, exist_ok=True)
    with (BUILD/'build.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        registry = BUILD/'sources.json'
        if not registry.exists():
            transfer('config/dfm13_sources.json', registry)
        sources = read(registry)
        assert sources['inherits'] == 'dfm12'
        info = read(ROOT/'data/sampled_dfm11/metadata.json')['tokenizer_info']
        for key, filename in [('tokenizer_path', 'tokenizer.json'),
                              ('chat_template_path', 'chat_template.jinja')]:
            target = SNAPSHOT/'tokenizer'/filename
            transfer('data/dfm11_tokenizer/'+filename, target)
            assert sha(target) == sha(Path(info[key])), f'Incompatible {key}'
        stage = BUILD/'accepted_inputs'
        rules = []
        for source in sources['additions']:
            assert source.get('status') != 'pending_audit'
            original = Path(source['output'])
            relative = original.relative_to(REMOTE)
            local = SNAPSHOT/relative
            transfer(str(relative), local)
            assert sha(local) == source['output_sha256'], source['name']
            for key in ('manifest', 'export_manifest', 'release_authorization'):
                if key in source:
                    rel = Path(source[key]).relative_to(REMOTE)
                    transfer(str(rel), SNAPSHOT/rel)
                    if key+'_sha256' in source:
                        assert sha(SNAPSHOT/rel) == source[key+'_sha256']
            dest = stage/source['name']/'train.jsonl'
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                dest.symlink_to(local.resolve())
            assert dest.resolve() == local.resolve()
            rules.append(dict(prefix=source['name']+'__', repeat=source['repeat'], long_context='drop'))
        policy = BUILD/'prefix_config.yaml'
        policy.write_text(yaml.safe_dump(rules))
        tokenized = ROOT/'data/tokenized_dfm13_additions'
        run([sys.executable, 'scripts/tokenize_chat_template.py', stage, '-o', tokenized,
             '--tokenizer-path', info['tokenizer_path'], '--chat-template', info['chat_template_path'],
             '--max-seq-len', '4096', '--workers', '16'])
        sampled = ROOT/'data/sampled_dfm13_additions'
        if not (sampled/'metadata.json').exists():
            run([sys.executable, 'data_io/sample_tokenized.py', f'tokenized_path={tokenized}',
                 f'output_path={sampled}', f'prefix_config_path={policy}', 'epochs=3',
                 'concat_workers=1', 'skip_unmatched=true'])
        base = SNAPSHOT/'sampled_dfm12'
        for name in ('metadata.json', 'build-receipt.json', 'tokens.npy'):
            transfer('data/sampled_dfm12/'+name, base/name)
        for epoch in range(3):
            transfer(f'data/sampled_dfm12/epoch_{epoch}', base/f'epoch_{epoch}', directory=True)
        assert read(base/'metadata.json')['total_length'] == 106799766039, 'Remote base changed'
        merge(base, sampled, ROOT/'data/sampled_dfm13', info)
        write(BUILD/'complete.json', dict(status='ready', epochs=3,
              metadata=read(ROOT/'data/sampled_dfm13/metadata.json')))
        print('DFM13 READY; training not started', flush=True)


if __name__ == '__main__':
    main()
