"""Resume unpublished DaLA13 assembly without rewriting completed local views."""
from pathlib import Path
from types import FunctionType
from dfm12.io import load
from scripts import queue_dala_compact_assembly as queue


def main():
    finalized = Path('data/dfm13/dala-compact-remaining-four-20261004-v1')
    output = Path('data/dfm13/verified-finished-additions-dala13-20261004-v1')
    saved = load(output.with_name(output.name+'-control')/'registry.json')
    reference = load('data/dfm13/authoritative-additions.json')
    if Path(reference['root']).name != 'verified-finished-additions-dala9-20261004-v1':
        raise ValueError('Unexpected predecessor')
    previous = load(Path(reference['root'])/'registry.snapshot.json')
    old = {e['name']: e for e in previous['additions']}
    new = {e['name']: e for e in saved['additions']}
    if any(new.get(name) != entry for name, entry in old.items()):
        raise ValueError('Preserved predecessor entries differ')
    added = [e for e in saved['additions'] if e['name'] not in old]
    raw = load(finalized/'registry.json')['additions']
    if {e['name'] for e in added} != {e['name'] for e in raw}:
        raise ValueError('Preserved delta membership changed')
    for entry in raw:
        if any(new[entry['name']].get(k) != v for k, v in entry.items()):
            raise ValueError('Preserved finalized entry changed')
    def prepared(*args):
        return added
    run = FunctionType(queue.run.__code__, dict(queue.run.__globals__, prepare=prepared))
    run(finalized, output)


if __name__ == '__main__':
    main()
