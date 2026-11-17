"""Shard and tokenize the converted curriculum without sampling."""
from contextlib import ExitStack
import json
from pathlib import Path

from scripts.prepare_dfm16_decisions import tokenize_source


def main():
    root = Path('data/dfm16/decision_curriculum')
    source = root / 'input/train.jsonl'
    target = root / 'input/direct'
    if not target.exists():
        stage = root / 'input/.direct.partial'
        stage.mkdir(exist_ok=True)
        with ExitStack() as stack, source.open() as stream:
            outputs = [stack.enter_context((stage/f'part-{i:05d}.jsonl').open('w')) for i in range(64)]
            count = 0
            for i, line in enumerate(stream):
                outputs[i % 64].write(line)
                count += 1
        assert count == 90120
        stage.rename(target)
    receipt = json.loads((root / 'conversion.json').read_text())
    receipt['counts'] = {'direct': receipt['rows']}
    (root / 'conversion.json').write_text(json.dumps(receipt, indent=2)+'\n')
    meta = json.loads(Path('data/dfm15/native-reasoning-v2/sampled_dfm15/metadata.json').read_text())['tokenizer_info']
    tokenize_source(root, meta, 64)


if __name__ == '__main__':
    main()
