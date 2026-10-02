"""Panel definitions for the opt-in multilingual evaluation extension."""
import json
from pathlib import Path

import yaml


def panels(population_manifest: Path, euroeval_registry: Path):
    registry=json.loads(population_manifest.read_text())
    english=[('English expanded headline average','avg_population/english_v2/score','avg_population/epoch')]
    multilingual=[('Multilingual headline average','avg_population/multilingual_v1/score','avg_population/epoch')]
    population=next(p for p in registry['populations'] if p['kind']=='multilingual')
    for language in population['languages']:
        multilingual.append((f'{language} headline average',
            f'avg_population/multilingual_v1/languages/{language}/score','avg_population/epoch'))
    for language in [*population['languages'],'en']:
        target=english if language=='en' else multilingual
        target.extend([
            (f'{language} DaLA macro F1',f'dfm_eval/dala_{language}/linguistic-acceptability/dfm_evals_macro_f1','dfm_eval/epoch'),
            (f'{language} GEC exact match',f'dfm_eval/gec_dala_{language}/exact_match/mean','dfm_eval/epoch'),
        ])
    seen=set()
    for entry in yaml.safe_load(euroeval_registry.read_text())['entries']:
        if entry['status']=='coverage_gap' or not entry.get('metric_key'):
            continue
        key=entry['metric_key']
        if key in seen:
            continue
        seen.add(key)
        suffix='' if entry['include_in_average'] else ' (diagnostic)'
        multilingual.append((f"{entry['language']} EuroEval {entry['dataset']}{suffix}",key,'euroeval/epoch'))
    return english,multilingual
