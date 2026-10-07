"""Prepare/apply optimistic-concurrency workspace patches; never write run history."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import uuid

VIEW = '3fvncok3gjh'
RUN = 'dfm8-xl-from-dfm6-dfm7-epoch5-clean-full'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def build(spec, population, replacements=None):
    result = copy.deepcopy(spec)
    sections = result['section']['panelBankConfig']['sections']
    template_section = next(s for s in sections if s['name'] == 'Headline Averages')
    template = template_section['panels'][0]
    existing = {k for s in sections for p in s.get('panels', []) for k in p.get('config', {}).get('metrics', [])}
    if replacements is None:
        pop = next(p for p in population['populations'] if p['kind'] == 'dfm13_new_languages')
        section = next(s for s in sections if s['name'] == 'Multilingual Headline Metrics')
        original_count = len(section['panels'])
        for lang in pop['languages']:
            for task in pop['required_tasks'][lang]:
                definition = pop['metrics'][lang][task]
                key = definition['key']
                if key in existing: raise ValueError('Metric already displayed: ' + key)
                panel = copy.deepcopy(template)
                panel['__id__'] = uuid.uuid4().hex[:16]
                panel['config'].update(metrics=[key], chartTitle=f'{lang}: {task}',
                    xAxis='dfm_eval/epoch' if definition['suite'] == 'dfm' else 'euroeval/epoch')
                section['panels'].append(panel)
                existing.add(key)
        restored = copy.deepcopy(result)
        target = next(s for s in restored['section']['panelBankConfig']['sections'] if s['name'] == 'Multilingual Headline Metrics')
        target['panels'] = target['panels'][:original_count]
        assert restored == spec
    else:
        if replacements.get('overall_weighting_preserved') is not True:
            raise ValueError('Owner must confirm unchanged overall weighting')
        for change in replacements['replacements']:
            matches = [p for s in sections for p in s.get('panels', []) if p.get('__id__') == change['panel_id']]
            if len(matches) != 1 or matches[0]['config']['metrics'] != [change['old']]:
                raise ValueError('Panel identity/key changed')
            matches[0]['config']['metrics'] = [change['new']]
            matches[0]['config']['xAxis'] = change['axis']
        section = next(s for s in sections if s['name'] == 'Multilingual Headline Metrics')
        for addition in replacements.get('append_panels', []):
            if addition['key'] in existing: raise ValueError('Average already displayed')
            target = section
            if 'section' in addition:
                matches = [s for s in sections if s['name'] == addition['section']]
                if len(matches) != 1: raise ValueError('Addition requires an existing unique section')
                target = matches[0]
            panel = copy.deepcopy(template)
            panel['__id__'] = uuid.uuid4().hex[:16]
            panel['config'].update(metrics=[addition['key']], chartTitle=addition['title'], xAxis=addition['axis'])
            target['panels'].append(panel)
            existing.add(addition['key'])
    assert result['section'].get('runSets') == spec['section'].get('runSets')
    return result


def check_sync(receipt, mapping):
    pause = mapping.get('sync_pause_step', 3200000)
    if pause not in (3154500, 3200000): raise ValueError('Unknown authorized synchronization pause')
    if receipt.get('run_id') != RUN or receipt.get('checkpoint_step') != pause:
        raise ValueError('Need synchronization evidence for this run at authorized pause')
    if receipt.get('remote_verified') is not True or receipt.get('mapping_sha256') != digest(mapping):
        raise ValueError('Unverified or differently mapped synchronization receipt')
    keys = [c['new'] for c in mapping['replacements']] + [c['key'] for c in mapping.get('append_panels', [])]
    for key in keys:
        value = receipt.get('values', {}).get(key)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError('New metric has no finite synchronized value: ' + key)
    policy = mapping.get('evidence_policy', {})
    if policy.get('kind') == 'historical_67':
        for key in keys:
            if receipt.get('verified_history_points', {}).get(key, 0) != 67:
                raise ValueError('All67 historical points must be remote verified')
    if policy.get('kind') in ('population_baseline', 'expanded_baseline'):
        if receipt.get('population_baseline_step') != 3150000:
            raise ValueError('New populations require the3150000 baseline')
        if not all(receipt.get('complete', {}).get(key) is True for key in keys):
            raise ValueError('Incomplete population cannot replace missing data')
    if policy.get('kind') == 'population_available':
        if not all(receipt.get('positive_coverage', {}).get(k) is True for k in keys):
            raise ValueError('Available population requires positive coverage and verified definition')


def check_raw_layout(mapping, registry):
    """Authorize empty raw panels from installed tasks, not fabricated history."""
    if mapping.get('replacements') or mapping.get('evidence_policy', {}).get('kind') != 'additional_raw_metrics':
        raise ValueError('Task registry authorization is raw additions only')
    expected = set()
    for task in registry:
        name = task['name']
        if name.startswith('gec_dala_v2_'):
            expected.add(f'dfm_eval/{name}/exact_match/mean')
        elif name.startswith('dala_v2_'):
            expected.add(f'dfm_eval/{name}/semantic_v1/macro_f1')
        else:
            raise ValueError('Unexpected task in raw registry')
    actual = [item['key'] for item in mapping.get('append_panels', [])]
    if len(actual) != 42 or len(expected) != 42 or len(set(actual)) != 42 or set(actual) != expected:
        raise ValueError('Raw additions must exactly match the42 registered tasks')


def verify_remote(mapping, prepared, api, history_min_step=None):
    """Read history only; create evidence, never log or register metrics."""
    run = api.run('peter-sk-sdu/DFM5/' + RUN)
    keys = [c['new'] for c in mapping['replacements']] + [c['key'] for c in mapping.get('append_panels', [])]
    kind = mapping['evidence_policy']['kind']
    scan_options = {}
    if history_min_step is not None:
        if history_min_step < 0: raise ValueError('Negative history bound')
        scan_options['min_step'] = history_min_step
    elif kind in ('population_baseline', 'expanded_baseline', 'population_available'):
        last = getattr(run, 'lastHistoryStep', None)
        if isinstance(last, int):
            scan_options.update(min_step=max(0, last-2000), max_step=last+1)
    result = dict(run_id=RUN, checkpoint_step=mapping.get('sync_pause_step', 3200000), remote_verified=True,
                  mapping_sha256=digest(mapping), values={}, verified_history_points={}, complete={})
    result['history_scan_bounds'] = scan_options
    result['positive_coverage'] = {}
    # These baselines are each emitted as one atomic row. Requiring all keys
    # together avoids34 redundant scans and cannot combine partial emissions.
    atomic_rows = None
    if kind in ('population_baseline', 'expanded_baseline'):
        requested = set()
        for key in keys:
            requested.update((key, key.split('/')[0]+'/train_step'))
            if kind == 'population_baseline': requested.add(key.rsplit('/',1)[0]+'/complete')
            else: requested.update(mapping['evidence_policy']['required_values'][key])
        atomic_rows = list(run.scan_history(keys=sorted(requested), page_size=1000, **scan_options))
    if kind == 'historical_67':
        if prepared is None or prepared.get('run_path') != 'peter-sk-sdu/DFM5/'+RUN or len(prepared['points']) != 67:
            raise ValueError('Need exact prepared67-point payload')
        expected_steps = {p['train_step'] for p in prepared['points']}
        if len(expected_steps) != 67: raise ValueError('Prepared checkpoint IDs are not unique')
    for key in keys:
        axis = key.split('/')[0] + '/train_step'
        requested = [key, axis]
        completeness = key.rsplit('/', 1)[0] + '/complete'
        if kind == 'population_baseline': requested.append(completeness)
        if kind == 'expanded_baseline':
            checks = mapping['evidence_policy']['required_values'][key]
            requested.extend(checks)
        if kind == 'population_available':
            proof = mapping['evidence_policy']['definitions'][key]
            coverage_key = key.rsplit('/',1)[0]+'/coverage'
            requested.extend((coverage_key, proof['key']))
        found = {}
        rows = atomic_rows if atomic_rows is not None else run.scan_history(keys=requested, page_size=1000, **scan_options)
        for row in rows:
            value = row.get(key)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value): continue
            step = row.get(axis)
            if kind == 'historical_67' and step in expected_steps: found[step] = value
            if kind == 'population_baseline' and step == 3150000 and row.get(completeness) == 1:
                found[step] = value
            if kind == 'expanded_baseline' and step == 3150000 and all(row.get(k) == v for k, v in checks.items()):
                found[step] = value
            if kind == 'population_available':
                coverage = row.get(coverage_key)
                if (type(step) in (int,float) and math.isfinite(step) and step >= 0
                    and type(coverage) in (int,float) and 0 < coverage <= 1
                    and row.get(proof['key']) == proof['sha256']):
                    found[step] = value
            if kind == 'additional_raw_metrics' and isinstance(step, (int, float)) and step >= 3150000:
                found[step] = value
        if kind == 'historical_67':
            if set(found) != expected_steps: raise ValueError('Historical synchronization incomplete: '+key)
            for row in prepared['rows']:
                if key in row:
                    step = row[axis]
                    if not math.isclose(found[step], row[key], rel_tol=1e-9, abs_tol=1e-10):
                        raise ValueError('Remote value differs from prepared payload: '+key)
            result['verified_history_points'][key] = len(found)
        elif kind in ('population_baseline', 'expanded_baseline'):
            if 3150000 not in found: raise ValueError('Complete baseline missing: '+key)
            result['population_baseline_step'] = 3150000
            result['complete'][key] = True
        elif kind == 'additional_raw_metrics':
            if not found: raise ValueError('New raw task has not synchronized: '+key)
        elif kind == 'population_available':
            if not found: raise ValueError('No positive-coverage definition-matched history: '+key)
            result['positive_coverage'][key] = True
            result['verified_history_points'][key] = len(found)
        else: raise ValueError('Unknown evidence policy')
        result['values'][key] = found[max(found)]
    check_sync(result, mapping)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--population', type=Path, default=Path('config/multilingual_headline_populations_dfm13_20261006.json'))
    parser.add_argument('--replacement-mapping', type=Path)
    parser.add_argument('--sync-receipt', type=Path)
    parser.add_argument('--apply-prepared', action='store_true')
    parser.add_argument('--verify-remote-sync', action='store_true')
    parser.add_argument('--prepared-history', type=Path)
    parser.add_argument('--history-min-step', type=int,
                        help='Explicit internal history lower bound; recent atomic baselines default to last2000 steps')
    parser.add_argument('--raw-task-registry', type=Path,
                        help='Authorize42 additive raw panels without claiming synchronized values')
    args = parser.parse_args()
    from wandb_workspaces.workspaces import internal
    from wandb_workspaces.workspaces.internal import gql
    import wandb
    root = args.output
    if args.verify_remote_sync:
        if args.apply_prepared or args.replacement_mapping is None or args.sync_receipt is None:
            raise ValueError('Read-only verification requires mapping/receipt, without apply')
        mapping = json.loads(args.replacement_mapping.read_text())
        prepared = json.loads(args.prepared_history.read_text()) if args.prepared_history else None
        receipt = verify_remote(mapping, prepared, wandb.Api(), args.history_min_step)
        with args.sync_receipt.open('x') as handle:
            json.dump(receipt, handle, indent=2)
        print('Read-only remote synchronization verified')
        return
    if not args.apply_prepared:
        root.mkdir(parents=True, exist_ok=False)
        before = internal.get_view_dict('peter-sk-sdu', 'DFM5', VIEW)
        spec = json.loads(before['spec'])
        population = json.loads(args.population.read_text())
        mapping = json.loads(args.replacement_mapping.read_text()) if args.replacement_mapping else None
        intended = build(spec, population, mapping)
        for name, value in [('before-view', before), ('intended-spec', intended),
                            ('population', population), ('replacement-mapping', mapping)]:
            (root/(name+'.json')).write_text(json.dumps(value, indent=2)+'\n')
        (root/'prepared.json').write_text(json.dumps(dict(stage='replace' if mapping else 'append_combined_section',
            before_sha256=digest(before), intended_sha256=digest(intended), population_sha256=digest(population),
            mapping_sha256=digest(mapping), history_writes=False), indent=2)+'\n')
        print('Prepared only:', root)
        return
    before = json.loads((root/'before-view.json').read_text())
    intended = json.loads((root/'intended-spec.json').read_text())
    mapping = json.loads((root/'replacement-mapping.json').read_text())
    proof = json.loads((root/'prepared.json').read_text())
    if proof['stage'] not in ('replace', 'append_combined_section'):
        raise ValueError('Superseded layout plan; prepare again')
    for value, key in [(before, 'before_sha256'), (intended, 'intended_sha256'), (mapping, 'mapping_sha256')]:
        if digest(value) != proof[key]: raise ValueError('Prepared artifact changed')
    if mapping is not None:
        if args.raw_task_registry is not None:
            registry = json.loads(args.raw_task_registry.read_text())
            check_raw_layout(mapping, registry)
            (root/'raw-layout-authorization.json').write_text(json.dumps(dict(
                registry_path=str(args.raw_task_registry), registry_sha256=digest(registry),
                mapping_sha256=digest(mapping), history_verified=False,
                authorization='User authorized additive raw panels before baseline; existing panels unchanged'), indent=2)+'\n')
        else:
            if args.sync_receipt is None: raise ValueError('Deferred: no synchronization receipt')
            check_sync(json.loads(args.sync_receipt.read_text()), mapping)
    # A changed definition or user edit requires a new dry run, never a stale overwrite.
    if digest(json.loads(args.population.read_text())) != proof['population_sha256']:
        raise ValueError('Population definition changed')
    if internal.get_view_dict('peter-sk-sdu', 'DFM5', VIEW) != before:
        raise ValueError('Concurrent workspace edit; re-prepare')
    query = gql('mutation Patch($id:ID!,$spec:String!){upsertView(input:{id:$id,spec:$spec}){view{id name}}}')
    wandb.Api().client.execute(query, dict(id=before['id'], spec=json.dumps(intended)))
    after = internal.get_view_dict('peter-sk-sdu', 'DFM5', VIEW)
    (root/'after-view.json').write_text(json.dumps(after, indent=2)+'\n')
    if after['id'] != before['id'] or after['displayName'] != before['displayName'] or json.loads(after['spec']) != intended:
        raise ValueError('Remote verification failed; inspect receipt, do not retry blindly')
    print('Workspace patch verified; no history writes')


if __name__ == '__main__':
    main()
