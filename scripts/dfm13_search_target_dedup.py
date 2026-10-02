"""Deduplicate actual target prefixes, independent of full-row target selection."""
from copy import deepcopy
from pathlib import Path
from scripts import dfm13_search_training_contract as contract
from scripts import dfm13_search_cached_repairs as repairs
from scripts import dfm13_search_calibration as base


def target_fingerprints(row):
    for index in row['target_message_indices']:
        view = deepcopy(row)
        # Later turns are not inputs to this training example.
        view['messages'] = view['messages'][:index + 1]
        view['target_message_indices'] = [index]
        yield index, contract.fingerprint(view)


def main():
    path = contract.ROOT / 'inventory.json'
    inventory = repairs.read(path)
    seen = {}; rows = []; duplicates = []
    for record in inventory['rows']:
        if record['contract_status'] != 'structurally_valid':
            continue
        source = Path(record['candidate'])
        if base.file_hash(source) != record['candidate_sha256']:
            raise ValueError('candidate changed')
        original = repairs.read(source)
        prompt = next(m['content'] for m in original['messages'] if m['role'] == 'user')
        candidate, _ = contract.strict_row(original, prompt)
        for index, digest in target_fingerprints(candidate):
            entry = dict(id=record['id'], target_message_index=index, fingerprint=digest)
            if digest in seen:
                duplicates.append(dict(entry, duplicate_of=seen[digest]))
            else:
                seen[digest] = entry
            rows.append(entry)
    base.atomic(contract.ROOT / 'target-dedup.json', dict(rows=rows, duplicates=duplicates,
        total_targets=len(rows), unique_targets=len(seen), admission_authorized=False,
        pins={str(path.resolve()):base.file_hash(path), str(Path(__file__).resolve()):base.file_hash(Path(__file__)),
              str(Path(contract.__file__).resolve()):base.file_hash(Path(contract.__file__))}))


if __name__ == '__main__':
    main()
