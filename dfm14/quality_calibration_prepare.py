"""Prepare fresh held calibration only; never authorizes production."""
from collections import Counter
from pathlib import Path
import json

import typer

from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from dfm14.catalog import LANGUAGES
from dfm14.generation_prepare import factory
from dfm14.synthetic_quality import source_issues

app = typer.Typer()


@app.command()
def prepare(output: Path, per_group: int=2):
    if not 1 <= per_group <= 20:
        raise ValueError('Diagnostic only: 1..20 attempts per group')
    old=Path('data/dfm14/generation-calibration-v2/manifest.json')
    manifest=load(old)
    families=sorted({g['family'] for g in manifest['groups']})
    pools={lang:{} for lang in LANGUAGES}
    oh={}
    held=Counter()
    for group in manifest['groups']:
        if file_hash(group['path']) != group['sha256']:
            raise ValueError('Source manifest drift')
        for row in rows(group['path']):
            spec=row['spec']; source=spec.get('source')
            if not source: continue
            issues=source_issues(spec)
            if issues:
                held.update(issues)
            elif spec['family']=='openhermes': oh[source['id']]=source
            else: pools[spec['language_code']][source['id']]=source
    config=dict(contract_version=4,cohort=output.name,quotas={f:per_group for f in families})
    with lock(output/'.prepare.lock'):
        if (output/'manifest.json').exists(): raise ValueError('Never overwrite a prepared calibration')
        groups=[]
        for lang in LANGUAGES:
            seeds={lang:[pools[lang][k] for k in sorted(pools[lang])],
                   'openhermes':[oh[k] for k in sorted(oh)]}
            if not seeds[lang] or not seeds['openhermes']: raise ValueError('No eligible seeds: '+lang)
            for family in families:
                path=output/lang/(family+'.jsonl')
                with atomic(path) as handle:
                    for i in range(per_group):
                        # New IDs/prompts/problems; no reuse of inspected accepted outputs.
                        slot=200+i
                        spec=factory(lang,family,slot,0,seeds,config)
                        if family=='summary-rewrite':
                            spec['subtype']=['one-sentence summary','summary with exactly three bullets',
                                             'two-sentence summary'][i%3]
                        row=dict(id=digest([config['cohort'],lang,family,slot]),spec=spec,
                                 training_ready=False,admission_authorized=False)
                        handle.write(json.dumps(row,ensure_ascii=False)+'\n')
                groups.append(dict(language=lang,family=family,rows=per_group,path=str(path.resolve()),sha256=file_hash(path)))
        write_json(output/'manifest.json',dict(groups=groups,rows=len(groups)*per_group,
            parent_sha256=file_hash(old),seed_holds=dict(held),production_authorized=False,
            note='Fresh generated examples from filtered existing seed pool; not held-out source evaluation.'))
    print(output, len(groups)*per_group)


if __name__=='__main__': app()
