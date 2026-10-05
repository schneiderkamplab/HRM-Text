"""Isolated matched prompt-only calibration; no shared schema or repair changes."""
import argparse
import asyncio
from copy import deepcopy
from pathlib import Path
from types import FunctionType

from . import wave31_balanced_run as runner
from . import wave4_gemma31_fresh as fresh
from .io import file_hash, load, lock, write_json

SOURCE = Path('data/dfm13/gemma31-balanced-execution-20261003-v2/wave4')
ROOT = Path('data/dfm13/gemma31-generation-constraints-20261003-v1')
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

# Exposed diagnostic cases, not a fresh heldout or a population estimate.
CASES = [
    ('01cb9acbac42', 'institution_policy'),
    ('fdfa97e5b409', 'institution_policy'),
    ('cc4c40761618', 'transport_policy'),
    ('aeb5d25e74c0', 'external_action_promise'),
    ('06a40f07', 'destination_not_current_location'),
    ('d284d7f2', 'destination_not_current_location'),
    ('9fe268aa', 'preserve_code_identifiers'),
    ('dbf543d7', 'preserve_requested_literal'),
    ('58f3d7ba', 'source_fault_csv_diagnostic_only'),
    ('758a1ff5', 'source_fault_axis_labels_diagnostic_only'),
    ('f18b605c', 'passing_parcel_control'),
    ('bef5c80c0044', 'passing_quoted_latin_control'),
]


def treatment(envelope):
    result = deepcopy(envelope)
    systems = [m for m in result['request']['messages'] if m['role'] == 'system']
    if len(systems) != 1 or not isinstance(systems[0]['content'], str):
        raise ValueError('Exactly one textual system instruction required')
    systems[0]['content'] += '\n\n'+CONSTRAINT
    return result


def prepare(root, source=SOURCE):
    root, source = Path(root).resolve(), Path(source).resolve()
    if root.exists():
        raise ValueError('Fresh root required')
    original = fresh.verify(source)
    requests = load(source/'generation-requests.json')
    c = runner.production.controller('wave4', load(fresh.DOWNLOAD/'ready.json')['snapshot'])
    specifications = {c.pilot.slot_key(s): s for s in load(source/'specifications.json')}
    selected, pairs, held = {}, [], []
    pins = dict(original['pins'])
    for path in [source/'manifest.json', source/'seal.json', Path(__file__),
                 Path(runner.__file__), Path(fresh.__file__), fresh.DOWNLOAD/'ready.json']:
        pins[str(path.resolve())] = file_hash(path)
    for prefix, purpose in CASES:
        keys = [key for key in requests if key.startswith(prefix)]
        if len(keys) != 1:
            raise ValueError('Ambiguous/missing selected case '+prefix)
        key = keys[0]
        candidate_path = source/'candidates'/f'{key}.json'
        candidate = load(candidate_path)
        spec = specifications[key]
        if candidate['provenance'] != spec:
            # Tool assembly adds provenance fields; original fields must survive.
            if any(candidate['provenance'].get(k) != v for k,v in spec.items()):
                raise ValueError('Candidate/specification mismatch')
        pins[str(candidate_path)] = file_hash(candidate_path)
        selected[key] = spec
        pairs.append(dict(id=key,language=spec['language_code'],family=spec['family'],
            purpose=purpose,baseline_candidate=str(candidate_path),
            baseline_candidate_sha256=pins[str(candidate_path)],
            source_hold=purpose.startswith('source_fault'),
            source_reference=spec.get('source'),scenario_reference=spec.get('scenario'),
            interpretation='Exposed matched diagnostic; no old answer or review supplied to generator'))
        if purpose.startswith('source_fault'):
            held.append(dict(id=key,reason=purpose,
                policy='Evaluate literal retention only; source repair/reaudit remains required regardless of keep'))
    budget = c.v6.Budget(load(fresh.DOWNLOAD/'ready.json')['snapshot'])
    root.mkdir(parents=True)
    for arm in ('baseline','constrained'):
        directory = root/arm
        envelopes = {key: deepcopy(requests[key]) if arm == 'baseline' else treatment(requests[key])
                     for key in selected}
        budgets = {key: budget.measure(e['request']) for key,e in envelopes.items()}
        for name,value in [('specifications.json',list(selected.values())),
                           ('generation-requests.json',envelopes),('preparation-budgets.json',budgets),
                           ('config.json',load(source/'config.json')),('pairs.json',pairs),
                           ('source-holds.json',held)]:
            write_json(directory/name,value)
        child_pins = dict(pins)
        child_pins.update({str(p):file_hash(p) for p in directory.iterdir() if p.is_file()})
        write_json(directory/'manifest.json',dict(model=original['model'],revision=original['revision'],
            wave='wave4',total=len(selected),pins=child_pins,arm=arm,
            admission_authorized=False,production_approved=False,publication_allowed=False,
            independent_review_required=True,source_hold_ids=[r['id'] for r in held],
            treatment='Historical full request unchanged' if arm=='baseline' else 'Only system suffix added',
            student_context='Pending full generated messages/tools; 4096, no truncation',
            schema_unchanged=True,reviewer_unchanged=True))
        write_json(directory/'seal.json',dict(manifest_sha256=file_hash(directory/'manifest.json')))
    write_json(root/'manifest.json',dict(total_generation_requests=2*len(selected),matched_specs=len(selected),
        arms=['baseline','constrained'],source_root=str(source),pairs=pairs,
        source_holds=held,system_suffix=CONSTRAINT,capacity_release_required_before_run=True,
        admission_authorized=False,production_approved=False,gpu_calls=0,pins={},
        child_manifest_pins={arm:file_hash(root/arm/'manifest.json') for arm in ('baseline','constrained')}))
    write_json(root/'seal.json',dict(manifest_sha256=file_hash(root/'manifest.json')))
    return verify(root)


def verify(root):
    root = Path(root)
    manifest = fresh.verify(root)
    for arm,sha in manifest['child_manifest_pins'].items():
        if file_hash(root/arm/'manifest.json') != sha:
            raise ValueError('Arm manifest drift')
        fresh.verify(root/arm)
    if load(root/'baseline/specifications.json') != load(root/'constrained/specifications.json'):
        raise ValueError('Matched specifications changed')
    a,b = (load(root/arm/'generation-requests.json') for arm in ('baseline','constrained'))
    if set(a) != set(b) or any(treatment(a[k]) != b[k] for k in a):
        raise ValueError('Not an exact prompt-only contrast')
    return manifest


async def run(root, arm):
    verify(root)
    execute = FunctionType(fresh.run.__code__,dict(fresh.run.__globals__,
        adapter=runner.adapter,endpoint_limit=runner.endpoint_limit),
        fresh.run.__name__,fresh.run.__defaults__,fresh.run.__closure__)
    with lock(Path(root)/arm/'run.lock'):
        await execute(Path(root)/arm,1)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','verify','run'])
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--arm',choices=['baseline','constrained'],default='constrained')
    p.add_argument('--capacity-released',action='store_true',
                   help='Operator acknowledgment only; not an automated release detector')
    a=p.parse_args()
    if a.command=='run':
        if not a.capacity_released:
            p.error('Do not run until capacity owner releases endpoints; acknowledgment required')
        asyncio.run(run(a.root,a.arm))
    else:
        print((prepare(a.root) if a.command=='prepare' else verify(a.root))['total_generation_requests'])


if __name__=='__main__':
    main()
