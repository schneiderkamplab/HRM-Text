import asyncio
import copy
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
import yaml

from dfm12 import european_synthetic_campaign as campaign
from dfm12 import multilingual_quarter as quarter
from dfm12 import multilingual_pilot_v6 as pilot
from dfm12 import multilingual_calibration_v6 as v6
from dfm12.io import digest, file_hash, load, write_json


def configuration():
    return yaml.safe_load(campaign.CONFIG.read_text())


def test_config_72_groups_490k_and_all_languages():
    rows = campaign.milestone_targets(configuration())
    assert len(rows) == 72
    assert sum(r['accepted_target'] for r in rows) == 490000
    for lang in campaign.LANGUAGES:
        expected = 70000 if lang in {'et', 'ca'} else 35000
        assert sum(r['accepted_target'] for r in rows if r['language']==lang) == expected


def test_targets_derived_not_hardcoded():
    config = configuration()
    config['languages'] = {lang:1 for lang in campaign.LANGUAGES}
    assert sum(r['accepted_target'] for r in campaign.milestone_targets(config)) == 840000


@pytest.mark.parametrize('change', ['language', 'family', 'audit', 'model', 'fractional', 'divisor'])
def test_bad_config_fails(change):
    config = configuration()
    if change=='language':
        config['languages']['pt'] = config['languages'].pop('pt_pt')
    elif change=='family':
        del config['families']['math-code']
    elif change=='audit':
        config['audit_every_candidate'] = False
    elif change=='model':
        config['auditor'] = 'other-model'
    elif change=='fractional':
        config['families']['math-code']['full_priority_rows'] = 60001
    else:
        config['milestone_divisors']['tenth'] = 0
    with pytest.raises(ValueError):
        campaign.milestone_targets(config)


def test_modules_and_language_registry_are_isolated():
    old = (quarter.verify, quarter.milestone_targets, dict(v6.LANGUAGES), pilot.v6)
    controller = campaign.isolated_controller()
    another = campaign.isolated_controller()
    assert controller is not quarter and controller.v6 is not v6 and controller.pilot is not pilot
    assert controller.pilot.v6 is controller.v6
    assert controller.v6 is not another.v6
    assert controller.Ledger.finish.__code__.co_code == quarter.Ledger.finish.__code__.co_code
    assert controller.pilot.process.__code__.co_code == pilot.process.__code__.co_code
    for lang,label in campaign.LANGUAGES.items():
        record = controller.v6.audit_record(dict(language=lang, family='math-code', messages=[], tools=[],
            provenance=dict(subtype='math',language_code=lang,language=label,family='math-code',contract_version=4)))
        assert record['language_name'] == label
    assert old == (quarter.verify, quarter.milestone_targets, dict(v6.LANGUAGES), pilot.v6)


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    provider_file = tmp_path/'provider.py'
    provider_file.write_text('# Fake provider module for offline controller test\n')
    actual_provider=campaign._provider()
    provider = SimpleNamespace(__file__=str(provider_file), SourceProvider=type('Provider', (), {}), SeedUnavailable=RuntimeError,
        audit_record=actual_provider.audit_record, PT_PT_REQUIREMENT=actual_provider.PT_PT_REQUIREMENT)
    monkeypatch.setattr(campaign, '_provider', lambda:provider)
    asset = tmp_path/'asset.json'
    write_json(asset, {'fixture':True})
    monkeypatch.setattr(campaign, '_asset_paths', lambda directory:[asset])
    seeds = tmp_path/'seeds'
    seeds.mkdir()
    config = tmp_path/'config.yaml'
    config.write_text(yaml.safe_dump(configuration()))
    root = tmp_path/'campaign'
    manifest = campaign.prepare(root,seeds,tokenizer_dir=tmp_path/'tokenizer',config_path=config)
    return root, manifest, config, seeds


def test_prepare_starts_from_zero_and_verify(prepared):
    root, manifest, config, seeds = prepared
    assert manifest['target'] == 490000 and manifest['groups'] == 72
    assert manifest['initial_state'] == dict(accepted=0,candidates=0,imported=0,fingerprints=0)
    assert 'pilot' not in manifest and not (root/'pilot-import.json').exists()
    assert manifest['default_concurrency_per_server'] == 16
    with sqlite3.connect(root/'jobs.sqlite') as db:
        assert db.execute('SELECT COUNT(*),SUM(accepted),SUM(active),SUM(attempts) FROM groups').fetchone() == (72,0,0,0)
        assert db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM fingerprints').fetchone()[0] == 0
    assert campaign.verify(root) == manifest
    # Config is a frozen local copy, not a live control file shared with another root.
    config.write_text('parent config changed for a future campaign')
    assert campaign.verify(root) == manifest
    with pytest.raises(ValueError, match='new'):
        campaign.prepare(root,seeds)


@pytest.mark.parametrize('tamper', ['config','manifest','ledger_target','ledger_seal','asset','missing_pin'])
def test_verify_rejects_drift(prepared,tamper):
    root, manifest, _, _ = prepared
    if tamper=='config':
        value=load(root/'config.json');value['languages']['de']=1;write_json(root/'config.json',value)
    elif tamper=='manifest':
        manifest['target']=1;write_json(root/'manifest.json',manifest)
    elif tamper.startswith('ledger'):
        with sqlite3.connect(root/'jobs.sqlite') as db:
            db.execute("UPDATE groups SET target=target+1 WHERE language='de'" if tamper=='ledger_target' else
                       "UPDATE metadata SET value='wrong' WHERE key='manifest_sha256'")
    elif tamper=='asset':
        Path(next(iter(manifest['external_pins']))).write_text('changed')
    else:
        manifest['implementation_pins'].pop(str(Path(campaign.__file__).resolve()))
        write_json(root/'manifest.json',manifest)
        seal=file_hash(root/'manifest.json');write_json(root/'seal.json',dict(manifest_sha256=seal))
        with sqlite3.connect(root/'jobs.sqlite') as db:
            db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'",(seal,))
    with pytest.raises(ValueError):
        campaign.verify(root)


def test_new_language_ledger_requires_independent_effective_keep(tmp_path):
    controller=campaign.isolated_controller()
    ledger=controller.Ledger(tmp_path/'jobs.sqlite')
    ledger.initialize([dict(language='pt_pt',family='math-code',accepted_target=1)])
    class Provider:
        def next_spec(self,language,family,slot):
            return dict(language_code=language,language='European Portuguese (pt-PT)',family=family,slot=slot,
                        contract_version=4,subtype='math')
    first=ledger.reserve(Provider(),RuntimeError,tmp_path)
    rejected=dict(controller.pilot.base_outcome(first['spec']),terminal=True,status='valid',effective_keep=False)
    ledger.finish(first['id'],rejected)
    assert ledger.report(tmp_path,'test')['accepted']==0
    second=ledger.reserve(Provider(),RuntimeError,tmp_path)
    fingerprint='a'*64
    kept=dict(controller.pilot.base_outcome(second['spec']),terminal=True,status='valid',effective_keep=True,fingerprint=fingerprint)
    with pytest.raises(ValueError,match='owned unique'):
        ledger.finish(second['id'],kept)
    controller.Seen(ledger,second['id']).add(fingerprint)
    assert ledger.finish(second['id'],kept)
    assert not ledger.finish(second['id'],kept)
    assert ledger.reserve(Provider(),RuntimeError,tmp_path) is None
    ledger.close()


@pytest.mark.parametrize('kwargs', [dict(concurrency=33),dict(concurrency=64),dict(concurrency=True),
    dict(timeout=601),dict(max_kv_cache_utilization=.91),dict(max_kv_cache_utilization=float('nan'))])
def test_invalid_runtime_rejected_before_io(kwargs,tmp_path):
    with pytest.raises(ValueError):
        asyncio.run(campaign.execute(tmp_path,**kwargs))


def test_run_delegates_private_controller_with_conservative_defaults(monkeypatch,tmp_path):
    calls=[]
    async def execute(root,**kwargs):
        calls.append((root,kwargs))
    controller=SimpleNamespace(execute=execute,pilot=SimpleNamespace(ENDPOINTS=['borrowed']))
    monkeypatch.setattr(campaign,'isolated_controller',lambda:controller)
    asyncio.run(campaign.execute(tmp_path))
    assert calls == [(tmp_path,dict(endpoints=['borrowed'],concurrency=16,timeout=600,max_kv_cache_utilization=.90))]


@pytest.mark.parametrize('family',['grounded-instruct','tool-dialogue'])
def test_portuguese_generation_and_review_keep_native_json(monkeypatch,family):
    import dfm12.multilingual_tool_dialogue as tools
    controller=campaign.isolated_controller()
    provider=campaign._provider()
    def request(*args,**kwargs):
        return dict(messages=[dict(role='system',content='Original instructions')],
                    structured_outputs={'grammar':'do not retain for non-tools'},
                    response_format={'type':'json_schema','json_schema':{'schema':{'type':'object'}}})
    monkeypatch.setattr(tools,'request',request)
    generator=SimpleNamespace(request=request,schema=lambda s:{'type':'object'})
    spec=dict(language_code='pt_pt',family=family)
    payload=controller.v6.generation_request(spec,generator)
    assert provider.PT_PT_REQUIREMENT in payload['messages'][0]['content']
    assert 'response_format' in payload
    if family!='tool-dialogue':
        assert 'structured_outputs' not in payload
    reviewer=SimpleNamespace(request=request,schema=lambda r:{'type':'object'})
    reviewed=controller.v6.review_request({'language':'pt_pt'},reviewer)
    assert provider.PT_PT_REQUIREMENT in reviewed['messages'][0]['content']
    assert 'Reject a wrong language variant.' in reviewed['messages'][0]['content']
    assert 'structured_outputs' not in reviewed
    assert 'response_format' in reviewed


def test_provider_base_module_is_pinned():
    controller=campaign.isolated_controller()
    names={p.name for p in campaign._dependencies(controller,campaign._provider())}
    assert {'multilingual_production_specs.py','european_synthetic_specs.py','european_synthetic_seeds.py'} <= names
