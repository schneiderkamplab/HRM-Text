"""Reconcile planned production, admitted rows and published DFM14 packages."""
from collections import Counter, defaultdict
from pathlib import Path

from dfm12.io import load, write_json
from dfm14.release import ROOT, EXPORT
from dfm14.release_inputs import inventory


def report():
    contract=load(ROOT/'contract.json')
    if inventory()!=contract['inputs']:
        raise ValueError('Completed input inventory differs from prepared release')
    prepared=load(ROOT/'prepared.json')
    production=load('data/dfm14/production-v1/manifest.json')
    groups=defaultdict(Counter)
    streams=defaultdict(Counter)
    for job in production['jobs']:
        groups[job['language']+'/'+job['family']]['planned_slots']+=job['end']-job['start']
    for entry in prepared['reports']:
        job=entry['job']
        streams[job['name'].split('--')[0]].update(entry['counts'])
        if job['kind']=='synthetic':
            spec=job['job']
            groups[spec['language']+'/'+spec['family']].update(entry['counts'])
    manifest=load(EXPORT/'manifest.json')
    dedup=load(ROOT/'deduplication.json')
    publications=load(EXPORT/'upload-receipts.json') if (EXPORT/'upload-receipts.json').exists() else {}
    packages=[]
    for p in manifest['packages']:
        selected=dedup['sources'][p['name']]
        packages.append(dict(name=p['name'],hf_repo_id=p['hf_repo_id'],origins=p['origins'],
            packaged_rows=p['rows'],repeat=p['repeat'],selected=selected,
            tokens_per_epoch=selected['tokens']*p['repeat'],
            publication=publications.get(p['hf_repo_id'])))
    missing=[name for name,counts in groups.items() if not counts['eligible_rows']]
    dala=load('data/dfm14/local-audited-dala-additions.json')
    value=dict(planned_generation_groups=dict(groups),audit_streams=dict(streams),
        zero_accepted_generation_groups=missing,packages=packages,
        dala_components= dala['additions'],
        published_packages=len(publications),expected_packages=len(packages),
        sampled=(Path('data/sampled_dfm14')/'metadata.json').exists(),
        limitations=['Automated review, not independent human quality certification',
            'Exact benchmark checks do not establish semantic/translated decontamination',
            'Rejected/failed generation slots are not silently admitted or topped up'])
    write_json(ROOT/'coverage.json',value)
    lines=['# DFM14 Release Coverage','',
        f'Published packages: {len(publications)}/{len(packages)}.',
        f'Sampled metadata present: {value["sampled"]}.',
        'Zero accepted generation groups: '+(', '.join(missing) or 'none')+'.','',
        '## Generation Targets','',
        '| Group | Planned | Accepted | Eligible |','|---|---:|---:|---:|']
    for name,c in sorted(groups.items()):
        lines.append(f'| {name} | {c["planned_slots"]:,} | {c["accepted_source_rows"]:,} | {c["eligible_rows"]:,} |')
    lines+=['','## Integrated Packages','','| HF repository | Rows selected | Repeat | Tokens/epoch | Uploaded |',
            '|---|---:|---:|---:|---|']
    for p in packages:
        lines.append(f'| {p["hf_repo_id"]} | {p["selected"]["rows"]:,} | {p["repeat"]} | {p["tokens_per_epoch"]:,} | {bool(p["publication"])} |')
    target=Path('docs/reports/dfm14-release-coverage.md')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text('\n'.join(lines)+'\n')
    print(f'Coverage: {len(packages)} packages, {len(publications)} published; zero accepted: {missing}',flush=True)


if __name__=='__main__':
    report()
