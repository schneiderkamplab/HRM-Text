"""Offline bounded Persian corpus planning and four-transform staging. No network."""
import argparse
from collections import Counter, defaultdict
import gzip
import heapq
import json
import math
from pathlib import Path, PurePosixPath
import stat
import zipfile

from .io import atomic, digest, file_hash, load, lock, write_json

INVENTORY = Path('data/dfm13/wave4/persian-access-recheck-20261003')
ROOT = Path('data/dfm13/wave4/persian-local-v1')
REPOS = {'matina': 'MatinaAI/matina_persian_text_corpus', 'tlpc': 'Targoman/TLPC'}
MAX_LINE = 2 * 1024**2
MAX_MEMBER = 256 * 1024**2
MAX_EXPANDED = 1024**3
SEED = 20261003


def safe_name(name):
    path = PurePosixPath(name)
    if not name or '\\' in name or path.is_absolute() or '..' in path.parts or ':' in name:
        raise ValueError('unsafe_archive_path')
    return path


def allocate(files, source, max_shards=64, max_bytes=8*1024**3, max_shard_bytes=2*1024**3):
    groups = defaultdict(list)
    eligible = [f for f in files if f['path'].endswith(('.jsonl', '.jsonl.gz', '.zip'))]
    for item in eligible:
        safe_name(item['path'])
        if type(item['bytes']) is not int or not 0 < item['bytes'] <= max_shard_bytes:
            continue
        group = item['path'].split('/')[0] if source == 'tlpc' else item['path']
        groups[group].append(item)
    for group in groups:
        groups[group].sort(key=lambda f: digest([SEED, source, f['path']]))
    order = sorted(groups, key=lambda g: digest([SEED, source, g]))
    chosen, used = [], 0
    # Round robin over sites/categories before taking another month from a site.
    for depth in range(max((len(v) for v in groups.values()), default=0)):
        for group in order:
            if depth >= len(groups[group]):
                continue
            item = groups[group][depth]
            if len(chosen) < max_shards and used + item['bytes'] <= max_bytes:
                chosen.append(item)
                used += item['bytes']
        if len(chosen) >= max_shards:
            break
    return chosen, {'eligible_files': len(eligible), 'eligible_strata_under_shard_cap': len(groups),
        'selected_strata': len({i['path'].split('/')[0] if source == 'tlpc' else i['path'] for i in chosen}),
        'selected_bytes': used, 'unselected_files': len(eligible)-len(chosen)}


def plan(root):
    if root.exists():
        raise ValueError('Use a new immutable plan root')
    sources = {}
    for name, repo in REPOS.items():
        stem = repo.replace('/', '--')
        inventory = INVENTORY / (stem + '-inventory.json')
        receipt = INVENTORY / (stem + '-receipt.json')
        pin = load(receipt)
        selected, coverage = allocate(load(inventory), name)
        if not selected:
            raise ValueError('No bounded eligible shards')
        sources[name] = dict(repo=repo, revision=pin['revision'], license=pin['license'],
            files=selected, coverage=coverage, local_root=str(Path('data/dfm13/wave4/downloads')/stem),
            inventory_sha256=file_hash(inventory), receipt_sha256=file_hash(receipt))
    baseline = load('data/dfm12/baselines.json')
    # Supplementary candidate budget, not a changed accepted language quota.
    targets = {task: math.ceil(v['target_per_language'] * 1.5 / 3) for task,v in baseline['tasks'].items()}
    document = dict(sources=sources, targets_per_source=targets, seed=SEED,
        max_compressed_bytes_per_source=8*1024**3, max_shards_per_source=64,
        max_compressed_shard_bytes=2*1024**3, max_expanded_bytes_per_shard=MAX_EXPANDED,
        max_member_bytes=MAX_MEMBER, max_line_bytes=MAX_LINE, max_rows_per_shard=100000,
        candidate_policy='bounded supplementary staging, not full corpus or increased accepted quotas',
        source_policy='domain-balanced high-quality subset; hash round robin across site/category strata',
        implementation_sha256=file_hash(Path(__file__)),
        dependency_pins={str(p):file_hash(p) for p in map(Path,[
            'dfm12/wave4_transforms.py','dfm12/transform.py','dfm12/baltic_sources_cpu.py',
            'dfm12/baltic_audit.py','dfm12/wave4_cpu.py','dfm12/records.py'])},
        baseline_sha256=file_hash(Path('data/dfm12/baselines.json')), training_ready=False)
    write_json(root/'plan.json', document)
    write_json(root/'seal.json', {'sha256': file_hash(root/'plan.json')})


def json_lines(handle, counters, max_rows=100000, byte_limit=MAX_MEMBER):
    consumed = 0
    for ordinal in range(max_rows):
        line = handle.readline(min(MAX_LINE+1, byte_limit-consumed+1))
        if not line:
            return
        consumed += len(line)
        if consumed > byte_limit or len(line) > MAX_LINE:
            raise ValueError('expanded_or_line_limit')
        if not line.strip():
            continue
        try:
            row = json.loads(line.decode('utf-8'))
        except (ValueError, UnicodeError):
            counters['invalid_json'] += 1
            continue
        if not isinstance(row, dict):
            counters['nonobject'] += 1
            continue
        yield ordinal, row
    counters['bounded_prefix_scan'] += 1


def local_rows(path, counters):
    if path.suffix == '.zip':
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > 10000 or sum(m.file_size for m in members) > MAX_EXPANDED:
                raise ValueError('archive_expanded_limit')
            names = set()
            for m in members:
                safe_name(m.filename)
                if m.filename in names:
                    raise ValueError('duplicate_archive_member')
                names.add(m.filename)
                if stat.S_ISLNK(m.external_attr >> 16) or m.flag_bits & 1:
                    raise ValueError('symlink_or_encrypted_archive')
                if m.file_size > MAX_MEMBER or m.file_size > max(1,m.compress_size)*1000:
                    raise ValueError('archive_member_limit')
            for m in sorted(members, key=lambda m: digest([SEED,m.filename])):
                if m.is_dir():
                    continue
                if not m.filename.endswith('.jsonl'):
                    counters['unsupported_archive_member'] += 1
                    continue
                with archive.open(m) as handle:
                    for ordinal,row in json_lines(handle,counters):
                        yield m.filename,ordinal,row
    else:
        opener = gzip.open if path.name.endswith('.gz') else open
        with opener(path,'rb') as handle:
            for ordinal,row in json_lines(handle,counters):
                yield None,ordinal,row


def document(row, source):
    if source == 'matina':
        if not isinstance(row.get('text'),str):
            raise ValueError('unknown_matina_schema')
        return row['text'], {'paragraph_structure':'original_text_unmodified',
            'url':row.get('url'), 'title':row.get('title')}
    content = row.get('content')
    category = row.get('category')
    if not isinstance(category,dict) or category.get('textType') != 'Formal':
        raise ValueError('not_formal_tlpc')
    if not isinstance(content,list) or not content or any(not isinstance(p,dict) or not isinstance(p.get('text'),str) for p in content):
        raise ValueError('unknown_tlpc_schema')
    # Preserve every main-content element in order; never flatten comments/QA
    # into article prose or invent paragraph boundaries inside an element.
    return '\n\n'.join(p['text'] for p in content), {'paragraph_structure':'original_content_elements',
        'category':category,'url':row.get('url'),'title':row.get('title'),'date':row.get('date'),
        'content_types':[p.get('type') for p in content]}


def prepare(root, source, enqueue=False):
    if file_hash(root/'plan.json') != load(root/'seal.json')['sha256']:
        raise ValueError('Plan changed')
    policy = load(root/'plan.json')
    if policy['implementation_sha256'] != file_hash(Path(__file__)):
        raise ValueError('Implementation changed; new plan required')
    for path,sha in policy.get('dependency_pins',{}).items():
        if file_hash(Path(path)) != sha:
            raise ValueError('Dependency changed; new plan required')
    pin = policy['sources'][source]
    dest = root/source
    with lock(dest/'.lock'):
        if (dest/'receipt.json').exists():
            raise ValueError('Existing sealed preparation; do not overwrite')
        missing = [f['path'] for f in pin['files'] if not (Path(pin['local_root'])/f['path']).is_file()]
        if missing:
            write_json(dest/'status.json',dict(status='blocked_missing_selected_files',missing=missing,
                source_access_last_observed=403,network_requests=0,full_source_complete=False,training_ready=False))
            return
        for f in pin['files']:
            path=Path(pin['local_root'])/f['path']
            if path.stat().st_size != f['bytes'] or not f.get('lfs_sha256') or file_hash(path) != f['lfs_sha256']:
                raise ValueError('Source size/hash mismatch: '+f['path'])
        from .wave4_transforms import transform
        from .transform import window
        from .baltic_sources_cpu import renderer
        targets=policy['targets_per_source'];limit=max(targets.values())*3
        heap=[];counts=Counter()
        for f in pin['files']:
            path=Path(pin['local_root'])/f['path']
            # Any archive corruption/limit error aborts before candidate publication.
            for member,ordinal,row in local_rows(path,counts):
                counts['rows_scanned']+=1
                try:
                    text,metadata=document(row,source)
                except ValueError as exc:
                    counts[str(exc)]+=1;continue
                if not 500<=len(text)<=MAX_LINE or '\ufffd' in text:
                    counts['text_bounds']+=1;continue
                rank=int(digest([SEED,pin['repo'],f['path'],member,ordinal])[:16],16)
                selected=window(text,rank,max_chars=4500)
                if len(selected)<500 or sum(c.isalpha() for c in selected)/len(selected)<.6:
                    counts['window_quality']+=1;continue
                origin=dict(repo=pin['repo'],revision=pin['revision'],license=pin['license'],
                    file=f['path'],file_sha256=f['lfs_sha256'],member=member,row=ordinal,
                    document_sha256=digest(text),window_sha256=digest(selected),window_seed=rank,**metadata)
                entry=(-rank,digest(origin),selected,origin)
                if len(heap)<limit:heapq.heappush(heap,entry)
                elif rank < -heap[0][0]:heapq.heapreplace(heap,entry)
        render=renderer();seen=set()
        with atomic(dest/'candidates.jsonl') as out, atomic(dest/'seeds.jsonl') as seeds:
            for _,_,text,origin in sorted(heap,reverse=True):
                key=digest(text)
                if key in seen:counts['duplicate_windows']+=1;continue
                seen.add(key)
                seeds.write(json.dumps(dict(id=key,text=text,language='fa',provenance=origin),ensure_ascii=False)+'\n')
                for task,target in targets.items():
                    if counts[task]>=target:continue
                    try:
                        record=transform(text,'fa',task,origin,SEED)
                        record['rendered_tokens']=render.count(record['messages'])
                    except ValueError as exc:
                        counts['rejected:'+str(exc)]+=1;continue
                    record.update(admission_authorized=False,audit_status='pending')
                    out.write(json.dumps(record,ensure_ascii=False)+'\n');counts[task]+=1
        write_json(dest/'receipt.json',dict(status='bounded_candidates_prepared',counts=counts,
            shortfalls={t:max(0,n-counts[t]) for t,n in targets.items()},sha256=file_hash(dest/'candidates.jsonl'),
            plan_sha256=file_hash(root/'plan.json'),license=pin['license'],full_source_complete=False,training_ready=False))
        write_json(dest/'license-notice.json',dict(repo=pin['repo'],revision=pin['revision'],license=pin['license'],
            owner_approved=True,upstream_license_unchanged=True))
        if enqueue:
            from .wave4_cpu import enqueue as audit_enqueue
            audit_enqueue(Path('data/dfm13/wave4'),'persian-'+source+'-'+digest(policy)[:12],dest/'candidates.jsonl')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['plan','prepare']);p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--source',choices=REPOS);p.add_argument('--enqueue',action='store_true')
    a=p.parse_args()
    if a.action=='plan':plan(a.root)
    elif not a.source:p.error('--source required')
    else:prepare(a.root,a.source,a.enqueue)


if __name__=='__main__':main()
