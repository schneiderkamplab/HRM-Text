"""Use exact complete documentation table rows, not neighboring table blocks."""
from pathlib import Path
from scripts import dfm13_search_heldout_cpu_corrections as previous

ROOT = Path('data/dfm13/search-heldout-cpu-corrections-20261001-v3')
original_paragraph = previous.paragraph


def evidence_window(body, anchor, chars=1400):
    pos = body.index(anchor)
    start = body.rfind('\n', 0, pos) + 1
    if body[start:pos].startswith('|'):
        end = body.find('\n', pos)
        if end == -1:
            end = len(body)
        return dict(start=start, end=end, text=body[start:end])
    return original_paragraph(body, anchor, chars)


def main():
    previous.ROOT = ROOT
    previous.paragraph = evidence_window
    previous.main()
    path = ROOT / 'queue.json'
    queue = previous.repairs.read(path)
    queue['pins'][str(Path(__file__).resolve())] = previous.base.file_hash(Path(__file__))
    queue['supersedes'] = 'data/dfm13/search-heldout-cpu-corrections-20261001-v2'
    queue['change'] = 'Exact full documentation rows replace neighboring table material; no target or conversation truncation.'
    previous.base.atomic(path, queue)


if __name__ == '__main__':
    main()
