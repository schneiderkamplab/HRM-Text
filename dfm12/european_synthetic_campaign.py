"""Isolated twelve-language synthetic campaign; no pilot import or server lifecycle."""
import argparse
import asyncio
import importlib
import importlib.util
from pathlib import Path
import sqlite3

from .audit_pilot_gpu import TOKENIZER_DIR
from .io import file_hash, load, lock, write_json
from .multilingual_targets import targets

VERSION = 'european-synthetic-campaign-v1'
CONFIG = Path(__file__).with_name('european_synthetic_extension.yaml')
PROVIDER = 'dfm12.european_synthetic_specs'
LANGUAGES = dict(de='German', fr='French', es='Spanish', it='Italian', cs='Czech',
    pt_pt='European Portuguese (pt-PT)', fi='Finnish', et='Estonian', ca='Catalan',
    el='Greek', ro='Romanian', uk='Ukrainian')
FAMILIES = {'multiturn', 'grounded-instruct', 'openhermes', 'summary-rewrite', 'math-code', 'tool-dialogue'}
POLICY = dict(automatic_upload=False, automatic_export=False, training_changed=False,
    native_quality_certified=False, accepted_basis='user-authorized retained-v6 automated gates',
    pilot_import=False, independent_audit_every_candidate=True)


def milestone_targets(config, milestone='tenth', divisor=None):
    """Counts come from the sealed config, including any authorized later increase."""
    if milestone != 'tenth' or config.get('active_milestone', 'tenth') != 'tenth':
        raise ValueError('This controller requires the tenth milestone')
    if set(config.get('languages', {})) != set(LANGUAGES) or set(config.get('families', {})) != FAMILIES:
        raise ValueError('Exactly twelve European languages and six families required')
    configured = config.get('milestone_divisors', {}).get(milestone)
    if type(configured) is not int or configured != 10 or (divisor is not None and divisor != configured):
        raise ValueError('Tenth milestone divisor must be ten')
    if not isinstance(config.get('campaign'), str) or not config['campaign'].strip():
        raise ValueError('Explicit campaign identity required')
    from .multilingual_tasks import MODEL
    if (config.get('generator') != MODEL or config.get('auditor') != MODEL
            or config.get('audit_every_candidate') is not True
            or config.get('repeat') != 1 or config.get('max_rendered_example_tokens') != 4096):
        raise ValueError('Retained generator/auditor, repeat-one and student context required')
    for value in config['languages'].values():
        if type(value) is not int or value <= 0:
            raise ValueError('Language target divisors must be positive integers')
    for settings in config['families'].values():
        if any(type(settings.get(k)) is not int or settings[k] <= 0 for k in
               ('full_priority_rows', 'estimated_tokens_per_row')):
            raise ValueError('Positive integer family targets and estimates required')
    quotas = targets(config, milestone)
    if len(quotas) != 72 or any(q['accepted_target'] <= 0 for q in quotas):
        raise ValueError('Require 72 positive target groups')
    return quotas


def _private_module(name):
    """Independent globals; never reload or patch a live imported module."""
    path = Path(__file__).with_name(name + '.py')
    spec = importlib.util.spec_from_file_location('dfm12._european_private_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def isolated_controller():
    v6 = _private_module('multilingual_calibration_v6')
    v6.LANGUAGES = dict(v6.LANGUAGES, **LANGUAGES)
    provider = _provider()
    generation_request, review_request = v6.generation_request, v6.review_request
    def european_generation_request(spec, generation, endpoint_models=None):
        payload = generation_request(spec, generation, endpoint_models=endpoint_models)
        if spec['language_code'] == 'pt_pt':
            payload['messages'][0]['content'] += '\n' + provider.PT_PT_REQUIREMENT
        return payload
    def european_review_request(record, review):
        payload = review_request(record, review)
        if record['language'] == 'pt_pt':
            payload['messages'][0]['content'] += '\nReject a wrong language variant. ' + provider.PT_PT_REQUIREMENT
        return payload
    v6.generation_request = european_generation_request
    v6.review_request = european_review_request
    v6.audit_record = provider.audit_record
    pilot = _private_module('multilingual_pilot_v6')
    pilot.v6 = v6
    controller = _private_module('multilingual_quarter')
    controller.v6, controller.pilot = v6, pilot
    controller.VERSION, controller.PROVIDER, controller.POLICY = VERSION, PROVIDER, dict(POLICY)
    controller.milestone_targets = milestone_targets
    controller.verify = lambda root: verify(root, _controller=controller)
    return controller


def _provider():
    provider = importlib.import_module(PROVIDER)
    if (not callable(getattr(provider, 'SourceProvider', None))
            or not isinstance(getattr(provider, 'SeedUnavailable', None), type)
            or not callable(getattr(provider, 'audit_record', None))
            or not isinstance(getattr(provider, 'PT_PT_REQUIREMENT', None), str)):
        raise ValueError('Provider SourceProvider and SeedUnavailable interface required')
    return provider


def _dependencies(controller, provider):
    paths = [Path(__file__), Path(controller.__file__), Path(controller.pilot.__file__),
        Path(provider.__file__), Path(__file__).with_name('multilingual_targets.py'),
        Path(__file__).with_name('multilingual_production_specs.py'),
        Path(__file__).with_name('calibration_streaming.py'), *controller.v6.implementation_paths()]
    # Seed inventories can grow, but their preparation/adaptation code is fixed.
    helper = Path(__file__).with_name('european_synthetic_seeds.py')
    if helper.exists():
        paths.append(helper)
    return sorted({p.resolve() for p in paths})


def _asset_paths(tokenizer_dir):
    tokenizer_dir = Path(tokenizer_dir).resolve()
    metadata = Path('data/sampled_dfm11/metadata.json').resolve()
    info = load(metadata)['tokenizer_info']
    return [*(tokenizer_dir / n for n in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja')),
            metadata, Path(info['tokenizer_path']).resolve(), Path(info['chat_template_path']).resolve()]


def prepare(root, seeds_root, tokenizer_dir=TOKENIZER_DIR, config_path=CONFIG):
    """CPU-only fresh ledger. No donor root, accepted rows, fingerprints or calls."""
    import yaml
    root, seeds_root = Path(root).resolve(), Path(seeds_root).resolve()
    if root.exists():
        raise ValueError('Prepare requires a new campaign root')
    controller, provider = isolated_controller(), _provider()
    config = yaml.safe_load(Path(config_path).read_text())
    quotas = milestone_targets(config)
    if not seeds_root.is_dir():
        raise ValueError('Seed inventory directory required; inventory may grow afterward')
    dependencies = _dependencies(controller, provider)
    implementation_pins = {str(p): file_hash(p) for p in dependencies}
    external_pins = {str(p): file_hash(p) for p in _asset_paths(tokenizer_dir)}
    root.mkdir(parents=True, exist_ok=False)
    with lock(root / 'controller.lock'):
        ledger = controller.Ledger(root / 'jobs.sqlite')
        try:
            ledger.initialize(quotas)
            write_json(root / 'config.json', config)
            manifest = dict(version=VERSION, campaign=config['campaign'], seeds_root=str(seeds_root),
                tokenizer_dir=str(Path(tokenizer_dir).resolve()), target=sum(q['accepted_target'] for q in quotas),
                groups=72, languages=LANGUAGES, candidate_multiplier=6, milestone='tenth',
                milestone_divisor=10, provider=PROVIDER, policy=POLICY,
                external_pins=external_pins, implementation_pins=implementation_pins,
                input_pins={'config.json': file_hash(root / 'config.json')},
                seed_inventory='growing; exact sources pinned in immutable provider specs per allocation',
                initial_state=dict(accepted=0, candidates=0, imported=0, fingerprints=0),
                default_concurrency_per_server=16, max_concurrency_per_server=32,
                max_kv_cache_utilization=.90)
            controller.v6.verify_pins(root, manifest)
            write_json(root / 'manifest.json', manifest)
            seal = file_hash(root / 'manifest.json')
            write_json(root / 'seal.json', {'manifest_sha256': seal})
            ledger.db.execute('INSERT INTO metadata VALUES(?,?)', ('manifest_sha256', seal))
            ledger.report(root, 'prepared')
        finally:
            ledger.close()
    return verify(root, _controller=controller)


def verify(root, *, _controller=None):
    root = Path(root).resolve()
    controller = _controller or isolated_controller()
    manifest = load(root / 'manifest.json')
    seal = file_hash(root / 'manifest.json')
    if seal != load(root / 'seal.json').get('manifest_sha256'):
        raise ValueError('Campaign manifest seal drift')
    if (manifest.get('version') != VERSION or manifest.get('policy') != POLICY
            or manifest.get('provider') != PROVIDER or manifest.get('candidate_multiplier') != 6
            or manifest.get('groups') != 72 or manifest.get('languages') != LANGUAGES
            or manifest.get('milestone') != 'tenth' or manifest.get('milestone_divisor') != 10
            or manifest.get('max_concurrency_per_server') != 32
            or manifest.get('default_concurrency_per_server') != 16
            or manifest.get('max_kv_cache_utilization') != .90 or 'pilot' in manifest):
        raise ValueError('Campaign policy drift')
    required = {str(p) for p in _dependencies(controller, _provider())}
    if not required.issubset(manifest.get('implementation_pins', {})):
        raise ValueError('Missing implementation pins')
    if 'config.json' not in manifest.get('input_pins', {}):
        raise ValueError('Missing config pin')
    assets = {str(p) for p in _asset_paths(manifest['tokenizer_dir'])}
    if not assets.issubset(manifest.get('external_pins', {})):
        raise ValueError('Missing teacher/student asset pins')
    controller.v6.verify_pins(root, manifest)
    config = load(root / 'config.json')
    quotas = milestone_targets(config)
    if manifest['target'] != sum(q['accepted_target'] for q in quotas) or manifest['campaign'] != config['campaign']:
        raise ValueError('Campaign target or identity mismatch')
    if not Path(manifest['seeds_root']).is_absolute() or not Path(manifest['tokenizer_dir']).is_absolute():
        raise ValueError('Absolute inventory and tokenizer paths required')
    with sqlite3.connect((root / 'jobs.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        controller.verify_ledger(db, manifest, config)
        if db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0] != seal:
            raise ValueError('SQLite campaign seal mismatch')
        if db.execute("SELECT 1 FROM jobs WHERE origin != 'production' LIMIT 1").fetchone():
            raise ValueError('Imported jobs are forbidden in the new campaign')
    return manifest


async def execute(root, endpoints=None, concurrency=16, timeout=600, max_kv_cache_utilization=.90):
    if type(concurrency) is not int or not 1 <= concurrency <= 32:
        raise ValueError('This additional campaign allows only 1..32 clients per server')
    if type(timeout) is not int or not 1 <= timeout <= 600:
        raise ValueError('Timeout must be 1..600 seconds')
    if type(max_kv_cache_utilization) not in (int, float) or not 0 < max_kv_cache_utilization <= .90:
        raise ValueError('KV utilization must be positive and <=0.90')
    controller = isolated_controller()
    await controller.execute(Path(root), endpoints=controller.pilot.ENDPOINTS if endpoints is None else endpoints,
        concurrency=concurrency, timeout=timeout, max_kv_cache_utilization=max_kv_cache_utilization)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'verify', 'run'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--seeds-root', type=Path)
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--tokenizer-dir', type=Path, default=TOKENIZER_DIR)
    parser.add_argument('--endpoints', nargs='+')
    parser.add_argument('--concurrency-per-server', type=int, default=16)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--max-kv-cache-utilization', type=float, default=.90)
    args = parser.parse_args()
    if args.command == 'prepare':
        if args.seeds_root is None:
            parser.error('prepare requires --seeds-root')
        print(prepare(args.root, args.seeds_root, args.tokenizer_dir, args.config)['target'])
    elif args.command == 'verify':
        print(verify(args.root)['target'])
    else:
        asyncio.run(execute(args.root, args.endpoints, args.concurrency_per_server,
                            args.timeout, args.max_kv_cache_utilization))


if __name__ == '__main__':
    main()
