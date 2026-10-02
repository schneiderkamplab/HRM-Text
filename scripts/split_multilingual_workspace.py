"""Replace the aggregate multilingual section with language sections in place."""
import copy
import json
from datetime import datetime
from pathlib import Path
import uuid

import yaml

LANGUAGES = {
    'nb': 'Norwegian Bokmal', 'nn': 'Norwegian Nynorsk', 'sv': 'Swedish',
    'is': 'Icelandic', 'fo': 'Faroese', 'nl': 'Dutch', 'pl': 'Polish',
    'de': 'German', 'fr': 'French', 'es': 'Spanish', 'it': 'Italian',
    'cs': 'Czech', 'pt_pt': 'Portuguese', 'fi': 'Finnish', 'et': 'Estonian',
    'ca': 'Catalan', 'el': 'Greek', 'ro': 'Romanian', 'uk': 'Ukrainian',
}


def split_sections(original, registry, population):
    updated = copy.deepcopy(original)
    sections = updated['section']['panelBankConfig']['sections']
    old = next(s for s in sections if s['name'] == 'Multilingual Headline Metrics')
    names = {s['name'] for s in sections}
    by_metric = {}
    for panel in old['panels']:
        for key in panel.get('config', {}).get('metrics', []):
            by_metric[key] = panel
    assert set(population['languages']) == set(LANGUAGES)
    replacements = []
    used_ids = set()
    for language in population['languages']:
        title = LANGUAGES[language]
        name = title + ' Headline Metrics'
        if name in names:
            raise ValueError('Existing section: ' + name)
        average = f'avg_population/multilingual_v1/languages/{language}/score'
        keys = [average,
                f'dfm_eval/dala_{language}/linguistic-acceptability/dfm_evals_macro_f1',
                f'dfm_eval/gec_dala_{language}/exact_match/mean']
        keys += [e['metric_key'] for e in registry['entries']
                 if e['language'] == language and e.get('metric_key')
                 and e['status'] != 'coverage_gap']
        section = copy.deepcopy(old)
        section.update(__id__=uuid.uuid4().hex[:16], name=name, panels=[],
                       sorted=0, isOpen=True)
        for key in dict.fromkeys(keys):
            panel = copy.deepcopy(by_metric[key])
            # Shared Norwegian metrics appear under both applicable languages.
            if panel['__id__'] in used_ids:
                panel['__id__'] = uuid.uuid4().hex[:16]
            used_ids.add(panel['__id__'])
            if key == average:
                panel['config'].update(chartTitle=title + ' headline average',
                                       xAxis='avg_population/epoch', xAxisTitle='epoch')
            section['panels'].append(panel)
        replacements.append(section)
    index = sections.index(old)
    sections[index:index + 1] = replacements
    # Everything outside the replaced section, including selection trees, is exact.
    restored = copy.deepcopy(updated)
    restored['section']['panelBankConfig']['sections'][index:index + 19] = [copy.deepcopy(old)]
    assert restored == original
    old_keys = set(by_metric) - {'avg_population/multilingual_v1/score'}
    new_keys = {k for s in replacements for p in s['panels'] for k in p['config']['metrics']}
    assert old_keys == new_keys
    return updated


def main():
    import wandb
    from wandb_workspaces.workspaces import internal
    from wandb_workspaces.workspaces.internal import gql

    root = Path('logs/wandb_workspace_specs') / (
        '3fvncok3gjh-languages-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    root.mkdir(parents=True, exist_ok=False)
    before = internal.get_view_dict('peter-sk-sdu', 'DFM5', '3fvncok3gjh')
    original = json.loads(before['spec'])
    registry = yaml.safe_load(Path('config/euroeval_dfm12_multilingual.yaml').read_text())
    manifest = json.loads(Path('config/multilingual_headline_populations_20260930.json').read_text())
    population = next(p for p in manifest['populations'] if p['kind'] == 'multilingual')
    updated = split_sections(original, registry, population)
    for name, value in [('before-view.json', before), ('intended-spec.json', updated)]:
        (root / name).write_text(json.dumps(value, indent=2))
    if internal.get_view_dict('peter-sk-sdu', 'DFM5', '3fvncok3gjh') != before:
        raise RuntimeError('Concurrent workspace edit; refusing stale update')
    mutation = gql('''mutation UpdateExistingView($id: ID!, $spec: String!) {
      upsertView(input: {id: $id, spec: $spec}) {view {id name} inserted}
    }''')
    wandb.Api().client.execute(mutation, {'id': before['id'], 'spec': json.dumps(updated)})
    after = internal.get_view_dict('peter-sk-sdu', 'DFM5', '3fvncok3gjh')
    (root / 'after-view.json').write_text(json.dumps(after, indent=2))
    assert json.loads(after['spec']) == updated
    print('Verified 19 language sections; backups:', root)


if __name__ == '__main__':
    main()
