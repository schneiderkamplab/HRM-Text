"""Unapproved31B successor campaigns, full quotas, double audit, no26B import."""
import argparse
import asyncio
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sqlite3

import yaml
from . import european_synthetic_campaign as european
from .io import load, write_json, file_hash, digest, lock
from .multilingual_targets import targets
from .wave4_gemma31_download import MODEL, ROOT as DOWNLOAD
from .wave31_endpoint_health import validate as validate_endpoint

VERSION='dfm13-wave31-full-v1'
FAMILY_TARGETS={'grounded-instruct':20000,'summary-rewrite':10000,'multiturn':15000,
                'openhermes':15000,'math-code':6000,'tool-dialogue':4000}
POLICY=dict(automatic_upload=False,automatic_export=False,training_changed=False,
    native_quality_certified=False,accepted_basis='two independent-context automated31B audit requests',
    inherited26b_import=False,independent_semantic_comparison_approval_required=True)


def endpoint_limit(document):
    models=document.get('data',[])
    if (len(models)!=1 or models[0].get('id')!=MODEL
            or type(models[0].get('max_model_len')) is not int or models[0]['max_model_len']<32768):
        raise ValueError('Require exclusively31B and verified32K context')
    return 32768


def modules(wave):
    if wave not in ('wave4','baltic'):raise ValueError('Unknown wave')
    return importlib.import_module(f'dfm12.{wave}_synthetic_campaign'), importlib.import_module(f'dfm12.{wave}_synthetic_specs')


def quotas(config, milestone='tenth', divisor=None):
    wave=config['wave'];_,provider=modules(wave)
    if (set(config['languages'])!=set(provider.LANGUAGES) or config['generator']!=MODEL
        or config['auditor']!=MODEL or config['repeat']!=1 or config['audit_every_candidate'] is not True
        or config['max_rendered_example_tokens']!=4096 or milestone!='tenth'
        or config['milestone_divisors']['tenth']!=10 or divisor not in (None,10)):
        raise ValueError('Full31B policy mismatch')
    result=targets(config,milestone)
    expected={(l,f):n for l in provider.LANGUAGES for f,n in FAMILY_TARGETS.items()}
    if {(r['language'],r['family']):r['accepted_target'] for r in result}!=expected:
        raise ValueError('No language/family target cuts permitted')
    return result


def second_valid(directory,key,outcome):
    from .jobs import validate_audit
    state=load(directory/'stages'/f'{key}-independent-review.json')
    request=load(directory/'requests'/f'{key}-independent-review.json')
    candidate=load(directory/'candidates'/f'{key}.json')
    from .wave_language_review import request as make_request
    expected=make_request(candidate)['request'];expected['model']=MODEL
    if request['request']!=expected:
        raise ValueError('Second request not bound to full candidate')
    if (state.get('status')!='complete' or state.get('request_sha256')!=digest(request['request'])
        or outcome.get('independent_candidate_sha256')!=file_hash(directory/'candidates'/f'{key}.json')
        or digest({k:candidate[k] for k in ('messages','tools')})!=outcome.get('fingerprint')):
        raise ValueError('Second audit evidence mismatch')
    from .multilingual_calibration_v6 import strict_json
    if state.get('raw',{}).get('finish_reason')!='stop' or strict_json(state['raw']['content'])!=state['output']:
        raise ValueError('Second raw audit incomplete')
    validate_audit(state['output'])
    if state['output']['keep'] is not True:raise ValueError('Second audit rejects')


def controller(wave,tokenizer):
    base,provider=modules(wave);c=base.controller()
    runtime=european._private_module('wave_synthetic_runtime');runtime.MODEL=MODEL
    generation=european._private_module('multilingual_generation_v4')
    original_adapters=c.v6.adapters
    review,_=original_adapters()
    budget=None
    def measure(payload,limit=32768):
        nonlocal budget
        if budget is None:budget=runtime.Budget(tokenizer)
        return budget.measure(dict(payload,model=MODEL),limit)
    generation.measure_prompt=measure
    generation.context_limit=lambda docs=None: min(endpoint_limit(d) for d in (docs if isinstance(docs,list) else [docs]))
    def generation_request(spec,adapter,endpoint_models=None):
        payload=runtime.generation_request(spec,adapter,endpoint_models)
        payload['model']=MODEL
        return payload
    def review_request(record,adapter):
        payload=runtime.review_request(record,adapter);payload['model']=MODEL
        return payload
    c.v6.generation_request=generation_request;c.v6.review_request=review_request
    c.v6.adapters=lambda:(review,generation)
    def live_endpoint_limit(document):
        validate_endpoint(document,tokenizer)
        return endpoint_limit(document)
    c.v6.Budget=runtime.Budget;c.v6.endpoint_limit=live_endpoint_limit
    c.v6.compact_request=runtime.compact_request
    c.VERSION=VERSION;c.POLICY=POLICY;c.milestone_targets=quotas
    c.verify=lambda root:verify(root,c)
    original_process=c.pilot.process
    async def process(spec,endpoint,directory,stages,health,gen,reviewer,seen):
        outcome=await original_process(spec,endpoint,directory,stages,health,gen,reviewer,seen)
        if outcome.get('effective_keep') is not True:return outcome
        # Original terminal file is not enough for quota credit: finish/recovery
        # below enforce a second raw evidence-bound decision, including crashes.
        outcome.update(effective_keep=False,independent_review_status='pending')
        key=outcome['id'];path=directory/'outcomes'/f'{key}.json'
        write_json(path,outcome)
        try:
            from .wave_language_review import request
            candidate=load(directory/'candidates'/f'{key}.json')
            payload=request(candidate)['request'];payload['model']=MODEL
            schema=payload['response_format']['json_schema']['schema']
            state=await stages.call(key,'independent-review',payload,schema,endpoint,endpoint_limit(health[endpoint]))
            outcome['independent_review_status']=state['status']
            outcome['independent_candidate_sha256']=file_hash(directory/'candidates'/f'{key}.json')
            if state['status']=='complete':
                from .jobs import validate_audit
                validate_audit(state['output'])
                outcome['effective_keep']=state['output']['keep'] is True
            else:outcome['status']='independent_review_'+state['status']
            if outcome['effective_keep']:second_valid(directory,key,outcome)
        except Exception as exc:
            outcome.update(status='independent_review_invalid',effective_keep=False,error=repr(exc))
        finally:
            write_json(path,outcome)
        return outcome
    c.pilot.process=process
    old_validate=c.validate_saved_keep
    def validate(directory,key,spec,outcome,adapters=None):
        second_valid(directory,key,outcome)
        return old_validate(directory,key,spec,outcome,adapters)
    c.validate_saved_keep=validate
    Original=c.Ledger
    class Ledger(Original):
        def remaining_groups(self):
            # Sealed sources are finite: exit explicitly blocked rather than
            # silently repeat documents or wait forever on exhausted pools.
            return [g for g in super().remaining_groups() if g['active'] or
                    not (g['blocked'] or '').startswith('seed_shortage:')]
        def finish(self,key,outcome):
            if outcome.get('effective_keep'):
                job=self.db.execute('SELECT workdir FROM jobs WHERE id=?',(key,)).fetchone()
                second_valid(Path(job['workdir']),key,outcome)
            return super().finish(key,outcome)
        def recover(self,campaign=None):
            for job in self.db.execute("SELECT * FROM jobs WHERE status='running'").fetchall():
                p=Path(job['workdir'])/'outcomes'/f"{job['id']}.json"
                if p.exists():
                    o=load(p)
                    if o.get('effective_keep'):
                        try:second_valid(Path(job['workdir']),job['id'],o)
                        except (ValueError,OSError,KeyError):
                            o.update(effective_keep=False,status='independent_review_missing_or_invalid')
                            write_json(p,o)
            return super().recover(campaign)
    c.Ledger=Ledger
    return c


def prepare(root,wave,seeds):
    base,provider=modules(wave);ready=load(DOWNLOAD/'ready.json')
    if ready['model']!=MODEL or ready.get('all_files_verified') is not True:raise ValueError('Weights unverified')
    config=yaml.safe_load(Path(base.CONFIG).read_text())
    config.update(wave=wave,generator=MODEL,auditor=MODEL,campaign=f'dfm13-{wave}-31b-full-v1')
    q=quotas(config);receipt=load(seeds/'receipt.json')
    if not receipt.get('ready') or file_hash(seeds/'seeds.sqlite')!=receipt['sha256']:raise ValueError('Seed pin mismatch')
    c=controller(wave,ready['snapshot'])
    root.mkdir(parents=True,exist_ok=False)
    with lock(root/'controller.lock'):
        ledger=c.Ledger(root/'jobs.sqlite')
        try:
            ledger.initialize(q);write_json(root/'config.json',config)
            paths=set(european._dependencies(c,provider))|{Path(__file__).resolve(),Path(base.__file__).resolve(),
                Path('dfm12/wave_synthetic_runtime.py').resolve(),Path('dfm12/wave_language_review.py').resolve(),
                Path('dfm12/wave31_endpoint_health.py').resolve(),Path('dfm12/wave4_gemma31_download.py').resolve()}
            paths |= {Path(provider._path).resolve(),Path('dfm12/wave_repair.py').resolve(),
                      Path('dfm12/jobs.py').resolve(),Path('dfm12/wave31_capacity.py').resolve()}
            assets=set(european._asset_paths(ready['snapshot']))|{(DOWNLOAD/'ready.json').resolve(),(seeds/'receipt.json').resolve()}
            m=dict(version=VERSION,wave=wave,campaign=config['campaign'],model=MODEL,revision=ready['revision'],
                seeds_root=str(seeds.resolve()),tokenizer_dir=ready['snapshot'],target=sum(x['accepted_target'] for x in q),
                groups=len(q),languages=provider.LANGUAGES,candidate_multiplier=6,milestone='tenth',milestone_divisor=10,
                provider=f'dfm12.{wave}_synthetic_specs',policy=POLICY,
                implementation_pins={str(p):file_hash(p) for p in paths},
                external_pins={str(p):file_hash(p) for p in assets},input_pins={'config.json':file_hash(root/'config.json')},
                calibration_required_before_bulk=True,production_approved=False,old26b_imported=0)
            write_json(root/'manifest.json',m);seal=file_hash(root/'manifest.json')
            write_json(root/'seal.json',dict(manifest_sha256=seal))
            ledger.db.execute('INSERT INTO metadata VALUES(?,?)',('manifest_sha256',seal));ledger.report(root,'prepared_unapproved')
        finally:ledger.close()
    return verify(root)


def verify(root,c=None):
    root=root.resolve();m=load(root/'manifest.json');c=c or controller(m['wave'],m['tokenizer_dir'])
    seal=file_hash(root/'manifest.json')
    if seal!=load(root/'seal.json')['manifest_sha256'] or m['policy']!=POLICY or m['version']!=VERSION:
        raise ValueError('Campaign pin/policy drift')
    c.v6.verify_pins(root,m)
    config=load(root/'config.json');q=quotas(config)
    if m['target']!=sum(r['accepted_target'] for r in q) or m['groups']!=len(q):raise ValueError('Target drift')
    with sqlite3.connect((root/'jobs.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        c.verify_ledger(db,m,config)
        if db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0]!=seal:raise ValueError('DB seal')
    return m


def approved(root):
    m=verify(root);a=load(root/'comparison-reviewed-approval.json')
    expected={(r['language'],r['family']) for r in quotas(load(root/'config.json'))}
    if (a.get('manifest_sha256')!=file_hash(root/'manifest.json') or a.get('model_revision')!=m['revision']
        or a.get('production_authorized') is not True or a.get('independent_semantic_review_complete') is not True
        or {tuple(g) for g in a.get('approved_groups',[])}!=expected or not a.get('reviewer')
        or not a.get('evidence_pins')):raise ValueError('Explicit reviewed all-group comparison approval required')
    for p,sha in a['evidence_pins'].items():
        if file_hash(Path(p))!=sha:raise ValueError('Comparison evidence drift')
    return sorted(expected)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','verify','run'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--wave',choices=['wave4','baltic'])
    p.add_argument('--seeds-root',type=Path);p.add_argument('--concurrency-per-server',type=int,default=2)
    p.add_argument('--capacity-profile',type=Path,help='Pinned measured post-calibration production capacity')
    a=p.parse_args()
    if a.command=='prepare':
        if not a.wave or not a.seeds_root:p.error('wave and seeds-root required')
        print(prepare(a.root,a.wave,a.seeds_root)['target'])
    elif a.command=='verify':print(verify(a.root)['target'])
    else:
        groups=approved(a.root);m=verify(a.root);c=controller(m['wave'],m['tokenizer_dir'])
        if a.capacity_profile:
            from .wave31_capacity import validate
            profile=load(a.capacity_profile);validate(profile)
            if a.concurrency_per_server!=profile['client_allocations'][m['wave']]:
                p.error('Client concurrency must match measured aggregate allocation')
            write_json(a.root/'capacity-runtime.json',dict(profile=str(a.capacity_profile.resolve()),
                profile_sha256=file_hash(a.capacity_profile),allocation=a.concurrency_per_server,
                aggregate=profile['aggregate_client_concurrency_per_server'],
                server_max_num_seqs=profile['server_max_num_seqs']))
        elif not 1<=a.concurrency_per_server<=8:
            p.error('Above comparison cap requires measured production capacity profile')
        asyncio.run(c.execute(a.root,endpoints=[f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)],
            concurrency=a.concurrency_per_server,timeout=600,max_kv_cache_utilization=.90,allowed_groups=groups))


if __name__=='__main__':main()
