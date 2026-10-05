"""Model-agnostic source/instruction successor; preparation defaults to 26B.

The historically named wave31 implementation is immutable and contains only CPU
text/schema/student validation. Teacher selection here is independent of it.
"""
import argparse
from pathlib import Path

from . import wave31_source_instruction_adapter as core
from .io import file_hash, load, write_json

DEFAULT_MODEL = 'google/gemma-4-26B-A4B-it'
schema = core.schema
assemble = core.assemble
decode = core.decode
normalize_user = core.normalize_user


def model_name(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError('explicit nonempty model identifier required')
    return value


def request(spec, historical, *, model=DEFAULT_MODEL):
    envelope = core.request(spec, historical)
    envelope['request']['model'] = model_name(model)
    return envelope


def prepare(parent, root, *, model=DEFAULT_MODEL):
    model = model_name(model)
    result = core.prepare(parent, root)  # Requires a new root; historical files untouched.
    path = root / 'generation-requests.json'
    envelopes = load(path)
    inherited = sorted({e['request']['model'] for e in envelopes.values()})
    for envelope in envelopes.values():
        envelope['request']['model'] = model
    write_json(path, envelopes)
    manifest = load(root / 'manifest.json')
    manifest.update(model=model, model_agnostic_adapter=True,
                    inherited_request_models=inherited,
                    teacher_change_authorized_by_preparation=False,
                    teacher_endpoint_preflight_required=True,
                    model_selection='Explicit CPU request preparation only; not teacher/bulk approval.')
    manifest['pins'][str(path.resolve())] = file_hash(path)
    manifest['pins'][str(Path(__file__).resolve())] = file_hash(Path(__file__))
    write_json(root / 'manifest.json', manifest)
    write_json(root / 'seal.json', dict(manifest_sha256=file_hash(root / 'manifest.json')))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--model', default=DEFAULT_MODEL)
    args = parser.parse_args()
    result = prepare(args.parent, args.root, model=args.model)
    print(f'Prepared {len(result)} CPU-only requests for {args.model}; no inference authorized or launched.')


if __name__ == '__main__':
    main()
