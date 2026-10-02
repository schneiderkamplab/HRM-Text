import json
from pathlib import Path

import yaml

from scripts.split_multilingual_workspace import LANGUAGES, split_sections
from scripts.multilingual_workspace_panels import panels


def test_split_preserves_other_sections_and_covers_all_metrics():
    manifest = Path('config/multilingual_headline_populations_20260930.json')
    euro = Path('config/euroeval_dfm12_multilingual.yaml')
    population = next(p for p in json.loads(manifest.read_text())['populations']
                      if p['kind'] == 'multilingual')
    _, definitions = panels(manifest, euro)
    original = {'section': {'runSets': [{'selection': 'unchanged'}],
        'panelBankConfig': {'sections': [
            {'name': 'Headline Averages', 'panels': [{'unchanged': True}]},
            {'name': 'Multilingual Headline Metrics', 'panels': [
                {'__id__': str(i), 'config': {'metrics': [key], 'xAxis': axis}}
                for i, (_, key, axis) in enumerate(definitions)]},
            {'name': 'Training', 'panels': []}]}}}
    result = split_sections(original, yaml.safe_load(euro.read_text()), population)
    sections = result['section']['panelBankConfig']['sections']
    assert len(sections) == 21
    for lang, section in zip(population['languages'], sections[1:-1]):
        assert section['name'] == LANGUAGES[lang] + ' Headline Metrics'
        assert section['panels'][0]['config']['metrics'] == [
            f'avg_population/multilingual_v1/languages/{lang}/score']
    ids = [p['__id__'] for s in sections[1:-1] for p in s['panels']]
    assert len(ids) == len(set(ids))


def test_valeu_excluded_from_all_population_bindings():
    registry = json.loads(Path('config/multilingual_headline_populations_20260930.json').read_text())
    for population in registry['populations']:
        for bindings in population['metrics'].values():
            assert all(not b or '/valeu-' not in b['key'] for b in bindings.values())
