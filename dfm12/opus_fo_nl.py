"""Owner-approved English-anchor FO/NL candidates, pending bilingual audit."""
import json
from pathlib import Path

from .catalog import config
from .io import atomic, digest, file_hash, load, lock, write_json
from .opus_pivot_probe import aligned
from .prepare import Renderer, enqueue_candidates
from .records import validate_messages


def main():
    root = Path('data/dfm12').resolve()
    probe = load(root / 'opus/fo-nl-pivot-probe.json')
    cfg = config()
    info = load('data/sampled_dfm11/metadata.json')['tokenizer_info']
    renderer = Renderer(info, cfg['max_seq_len'])
    origins = {}
    sources = []
    for entry in probe['sources']:
        archive = root / 'opus/downloads' / (digest(entry['url']) + '.zip')
        sources.append(dict(entry, archive_sha256=file_hash(archive)))
        for line, english, target in aligned(archive, 'en', entry['target']):
            origins.setdefault((entry['target'], english, target), []).append(line)
    component = 'opus-fo-nl-english-anchor'
    directory = root / 'candidates' / component
    directory.mkdir(parents=True, exist_ok=True)
    counts = {'candidate_pairs': 0, 'ambiguous_anchors_excluded': 0, 'duplicate_pairs': 0}
    seen = set()
    with lock(directory / '.lock'):
        if (directory / 'receipt.json').exists():
            raise FileExistsError('Completed component exists; refusing to replace audit inputs')
        with atomic(directory / 'candidates.jsonl') as out:
            for match in probe['matches']:
                if len(match['fo']) != 1 or len(match['nl']) != 1:
                    counts['ambiguous_anchors_excluded'] += 1
                    continue
                fo, nl = match['fo'][0], match['nl'][0]
                key = digest({'fo': fo, 'nl': nl})
                if key in seen:
                    counts['duplicate_pairs'] += 1
                    continue
                seen.add(key)
                messages = [{'role': 'user', 'content': 'Translate from Faroese into Dutch. Output only the translation.\n\n' + fo},
                            {'role': 'assistant', 'content': nl}]
                reverse = [{'role': 'user', 'content': 'Translate from Dutch into Faroese. Output only the translation.\n\n' + nl},
                           {'role': 'assistant', 'content': fo}]
                validate_messages(messages)
                validate_messages(reverse)
                record = {'id': key, 'messages': messages, 'reverse_messages': reverse,
                          'language': 'nl', 'reverse_language': 'fo', 'task': 'translation', 'pair': 'fo-nl',
                          'rendered_tokens': renderer.count(messages) + renderer.count(reverse),
                          'provenance': {'method': 'exact_english_anchor_join', 'sources': sources,
                                         'english_anchor': match['en'], 'license': 'cc-by-2.0',
                                         'fo_archive_lines': origins[('fo', match['en'], fo)],
                                         'nl_archive_lines': origins[('nl', match['en'], nl)],
                                         'machine_translated': False},
                          'audit_context': {'english_anchor': match['en'],
                                            'instruction': 'Check both translation directions and sense equivalence. English text equality is not proof of shared meaning. Reject ambiguity, wrong variants or non-equivalent targets.'}}
                out.write(json.dumps(record, ensure_ascii=False) + '\n')
                counts['candidate_pairs'] += 1
        receipt = {'component': component, 'counts': counts, 'tokenizer_info': info,
                   'sha256': file_hash(directory / 'candidates.jsonl'), 'audit_status': 'pending',
                   'final_sampling': False, 'blocking': False}
        write_json(directory / 'receipt.json', receipt)
    enqueue_candidates(root, component, cfg['model'], limit=100)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
