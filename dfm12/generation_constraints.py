"""Model-neutral request constraint and CPU-only calibration preparation."""
import argparse
from copy import deepcopy
from pathlib import Path

from .io import file_hash, load, write_json

DEFAULT_MODEL = 'google/gemma-4-26B-A4B-it'
DEFAULT_TOKENIZER = Path('/work/mimir/.home/.cache/huggingface/hub/models--google--gemma-4-26B-A4B-it/snapshots/4d7ae4984b7db7de8f8457170b3f1a419ee76d52')
SOURCE = Path('data/dfm13/gemma31-generation-constraints-20261003-v1')
ROOT = Path('data/dfm13/generation-constraints-26b-cpu-20261003-v1')

# Keep the exposed prompt contrast identical; the sealed 31B module is untouched.
CONSTRAINT = '''
Ground actions and technical literals precisely:
Do not speak as an actual institution's employee or invent its fees, eligibility,
loan periods, required documents, transport rules or app prices. If these are
unknown, ask for the institution/location or explain how to check. Invented rules
are allowed only in an explicitly fictional user scenario established BEFORE
using them, not through a disclaimer added after factual-sounding claims.
Without an appropriate tool and successful action receipt, do not claim or promise
external actions such as updating documents, sending email, booking or redirecting.
Offer a draft or instructions instead. An available option is not a completed
action: available_locker_id is a possible destination, not the parcel's current
location; redirect_allowed means permission, not that redirection happened.
For translation, translate explanatory prose only. Copy source code blocks,
inline executable identifiers, CSV headers and column order, literal data/axis
labels, indices, filenames and explicitly requested output strings unchanged.
Do not localize or rename them even when a translated version would still run.
Keep the meaning of prose tied to the displayed operations and supplied evidence;
do not invent an explanation to reconcile inconsistent source claims.
'''.strip()


def apply_request(request):
    """Return a copy, changing only one system string; preserve model and schema."""
    result = deepcopy(request)
    systems = [m for m in result['messages'] if m['role'] == 'system']
    if len(systems) != 1 or not isinstance(systems[0]['content'], str):
        raise ValueError('Exactly one textual system instruction required')
    if CONSTRAINT in systems[0]['content']:
        raise ValueError('Constraint already applied')
    systems[0]['content'] += '\n\n'+CONSTRAINT
    return result


def prepare(root, source=SOURCE, model=DEFAULT_MODEL, tokenizer=DEFAULT_TOKENIZER):
    root,source,tokenizer = (Path(p).resolve() for p in (root,source,tokenizer))
    if root.exists():
        raise ValueError('Fresh CPU preparation root required')
    if not isinstance(model,str) or not model.strip():
        raise ValueError('Explicit nonempty model required')
    manifest = load(source/'manifest.json')
    if file_hash(source/'manifest.json') != load(source/'seal.json')['manifest_sha256']:
        raise ValueError('Source manifest changed')
    if manifest['system_suffix'] != CONSTRAINT:
        raise ValueError('Historical prompt contrast changed')
    if file_hash(source/'baseline/manifest.json') != manifest['child_manifest_pins']['baseline']:
        raise ValueError('Source arm changed')
    child = load(source/'baseline/manifest.json')
    filenames = ['specifications.json','generation-requests.json','pairs.json','source-holds.json']
    pins = {str(source/'manifest.json'):file_hash(source/'manifest.json'),
            str(source/'baseline/manifest.json'):file_hash(source/'baseline/manifest.json')}
    for name in filenames:
        path = source/'baseline'/name
        if file_hash(path) != child['pins'][str(path)]:
            raise ValueError('Source input drift: '+name)
        pins[str(path)] = file_hash(path)
    from .european_synthetic_campaign import _private_module
    runtime = _private_module('wave_synthetic_runtime')
    runtime.MODEL = model
    budget = runtime.Budget(tokenizer)
    for path in [Path(__file__),Path('dfm12/wave_synthetic_runtime.py'),
                 Path('dfm12/european_synthetic_campaign.py'),
                 *(tokenizer/name for name in ['tokenizer.json','tokenizer_config.json','chat_template.jinja'])]:
        pins[str(path.resolve())] = file_hash(path)
    original = load(source/'baseline/generation-requests.json')
    baseline = deepcopy(original)
    for envelope in baseline.values():
        envelope['request']['model'] = model
    constrained = deepcopy(baseline)
    for envelope in constrained.values():
        envelope['request'] = apply_request(envelope['request'])
    for arm,requests in [('baseline',baseline),('constrained',constrained)]:
        write_json(root/arm/'generation-requests.json',requests)
        write_json(root/arm/'prompt-budgets.json',
                   {key:budget.measure(e['request']) for key,e in requests.items()})
    for name in ['specifications.json','pairs.json','source-holds.json']:
        write_json(root/name,load(source/'baseline'/name))
    outputs = {str(path.resolve()):file_hash(path) for path in root.rglob('*.json')}
    write_json(root/'manifest.json',dict(schema='model-neutral-generation-constraints-v1',
        default_preparation_model=model,bulk_model_choice='pending; default26B is not approval',
        tokenizer_dir=str(tokenizer),matched_specs=len(baseline),generation_requests=2*len(baseline),
        historical_model=child['model'],pins={**pins,**outputs},
        source_root=str(source),prompt_constraint=CONSTRAINT,
        execution_ready=False,run_command_available=False,gpu_calls=0,
        schema_unchanged=True,reviewer_changed=False,admission_authorized=False,
        student_context='Pending actual generated full messages/tools;4096,no truncation',
        integration='Apply apply_request to the chosen model request BEFORE compact transport; reviewer/schema owners separate',
        source_holds='Retained independently of any future automated keep'))
    write_json(root/'seal.json',dict(manifest_sha256=file_hash(root/'manifest.json')))
    return verify(root)


def verify(root):
    root=Path(root)
    manifest=load(root/'manifest.json')
    if file_hash(root/'manifest.json') != load(root/'seal.json')['manifest_sha256']:
        raise ValueError('Manifest changed')
    for path,sha in manifest['pins'].items():
        if file_hash(path)!=sha:
            raise ValueError('Input/output drift: '+path)
    baseline=load(root/'baseline/generation-requests.json')
    changed=load(root/'constrained/generation-requests.json')
    if set(baseline)!=set(changed):
        raise ValueError('Coverage mismatch')
    for key,envelope in baseline.items():
        expected=deepcopy(envelope)
        expected['request']=apply_request(expected['request'])
        if changed[key]!=expected or envelope['request']['model']!=manifest['default_preparation_model']:
            raise ValueError('Not a model-consistent prompt-only contrast')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','verify'])
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--source',type=Path,default=SOURCE)
    p.add_argument('--model',default=DEFAULT_MODEL)
    p.add_argument('--tokenizer-dir',type=Path,default=DEFAULT_TOKENIZER)
    a=p.parse_args()
    result=prepare(a.root,a.source,a.model,a.tokenizer_dir) if a.command=='prepare' else verify(a.root)
    print(result['generation_requests'])
