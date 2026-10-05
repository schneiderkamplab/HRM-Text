"""Freeze explicitly selected, fully finalized DaLA groups; never claim full completion."""
import argparse
from pathlib import Path
from dfm12.io import load, file_hash, write_json


def snapshot(source, output, languages):
    if output.exists(): raise ValueError('Use a fresh scoped snapshot root')
    entries = [e for e in load(source/'registry.json')['additions'] if e['language'] in languages]
    if {e['language'] for e in entries} != set(languages): raise ValueError('Requested language not complete')
    groups = {}
    for e in entries:
        root = Path(e['export_receipt']['path']).parent
        integration = root/'integration.json'; done = load(integration)
        if done['status'] != 'complete_train_only' or e not in done['components']:
            raise ValueError('Nonterminal group or mismatched component')
        groups[str(integration.resolve())] = file_hash(integration)
    for language in languages:
        tasks = [e['task'] for e in entries if e['language']==language]
        if sorted(tasks) != ['acceptability','correction']:
            raise ValueError('Require exactly one complete two-task group per language')
    output.mkdir(parents=True)
    write_json(output/'registry.json', dict(inherits='dfm12', additions=entries, local_only=True))
    write_json(output/'complete.json', dict(success=True,
        scope='explicit completed-group snapshot, NOT whole finalizer completion',
        source_root=str(source.resolve()), languages=sorted(languages), group_integrations=groups,
        registry=dict(path=str((output/'registry.json').resolve()), sha256=file_hash(output/'registry.json')),
        waiting=[dict(reason='outside_explicit_nine_language_scope')], uploaded=False))
    print(dict(components=len(entries), rows=sum(e['rows'] for e in entries),tokens=sum(e['tokens'] for e in entries)),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--languages',nargs='+',required=True)
    a=p.parse_args();snapshot(a.source,a.output,a.languages)
