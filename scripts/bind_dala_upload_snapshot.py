"""Bind a queued nine-subset upload to Tesla's exact immutable assembly snapshot."""
import argparse
from pathlib import Path
from dfm12.io import load, file_hash, write_json


def verify(queue, completion, registry):
    if completion.get('success') is not True or len(queue['items']) != 9:
        raise ValueError('Nine completed groups required')
    integrations = {x['integration']['path']:x['integration']['sha256'] for x in queue['items']}
    if integrations != completion['group_integrations']:
        raise ValueError('Group integration pins differ')
    components = [c for item in queue['items'] for c in item['train_components']]
    expected = {c['name']:c for c in components}
    actual = {c['name']:c for c in registry['additions']}
    if len(components) != 18 or len(expected) != 18 or len(registry['additions']) != 18 or actual != expected:
        raise ValueError('Paired task components differ')
    return dict(groups=9, components=18, exact_group_hash_match=True, exact_component_match=True,
                training_rows=sum(c['rows'] for c in components), tokens=sum(c['tokens'] for c in components))


def bind(queue_root, snapshot):
    queue=load(queue_root/'queue.json'); seal=load(queue_root/'seal.json')
    if file_hash(queue_root/'queue.json') != seal['queue']['sha256']:
        raise ValueError('Queue drift')
    completion=load(snapshot/'complete.json')
    if file_hash(snapshot/'registry.json') != completion['registry']['sha256']:
        raise ValueError('Tesla registry drift')
    result=verify(queue,completion,load(snapshot/'registry.json'))
    for path,sha in completion['group_integrations'].items():
        if file_hash(path) != sha: raise ValueError('Group drift')
    result.update(queue=seal['queue'], tesla_snapshot=str(snapshot.resolve()),
        tesla_completion_sha256=file_hash(snapshot/'complete.json'),
        tesla_registry_sha256=completion['registry']['sha256'], uploaded=False,
        upload_receipt=None, live_finalizer_registry_modified=False)
    output=queue_root/'tesla-snapshot-binding.json'
    if output.exists(): raise FileExistsError(output)
    write_json(output,result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--queue',type=Path,default=Path('data/dfm13/dala-v2-upload-nine-20261004-v1'))
    p.add_argument('--snapshot',type=Path,default=Path('data/dfm13/dala-compact-nine-completed-20261004-v1'))
    a=p.parse_args();print(bind(a.queue,a.snapshot))
