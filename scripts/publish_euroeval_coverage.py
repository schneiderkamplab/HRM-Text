"""Generate the 21-language coverage table and optionally add W&B panels."""
import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
import uuid

import yaml

from scripts.split_multilingual_workspace import LANGUAGES
from scripts.create_dfm5_headline_workspace import (
    DANISH_EUROEVAL_METRICS, ENGLISH_EUROEVAL_METRICS, MATH_CODE_EUROEVAL_METRICS)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--update-workspace', action='store_true')
    args = parser.parse_args()
    tasks = json.loads(Path('config/euroeval_additions_20260930.json').read_text())
    registry = yaml.safe_load(Path('config/euroeval_dfm12_multilingual.yaml').read_text())
    langs = {'da': 'Danish', 'en': 'English', **LANGUAGES}
    cells = {c: {lang: [] for lang in langs} for c in registry['categories'] if c != 'european-values'}
    for _, key, _ in DANISH_EUROEVAL_METRICS + ENGLISH_EUROEVAL_METRICS + MATH_CODE_EUROEVAL_METRICS:
        _, lang, cat, dataset, _ = key.split('/')
        if cat in cells:
            cells[cat][lang].append(dataset)
    for e in registry['entries']:
        if e['category'] in cells and e.get('metric_key') and e['status'] != 'coverage_gap':
            cells[e['category']][e['language']].append(e['dataset'])
    for task in tasks:
        cells[task['category']][task['language']].append(task['dataset'])
    lines = ['# EuroEval Coverage: 21 Languages', '',
             'Scheduled coverage as of 2026-09-30; excludes all `valeu-*`. '
             'Names are exact EuroEval CLI dataset identifiers. A dash means no task scheduled.', '',
             '| Category | ' + ' | '.join(langs.values()) + ' |',
             '|---|' + '---|' * len(langs)]
    for cat, by_lang in cells.items():
        lines.append('| ' + cat + ' | ' + ' | '.join(
            ', '.join(dict.fromkeys(by_lang[lang])) or '-' for lang in langs) + ' |')
    lines += ['', f'The {len(tasks)} additions apply to epoch_10, 2900K and all later checkpoints in the current plan. '
              'ScaLA and MultiIFEval now cover all 21 languages. Existing average definitions are unchanged. '
              'Shared Norwegian datasets run once, with results shown for both applicable variants.', '']
    Path('docs/euroeval-21-languages.md').write_text('\n'.join(lines))
    print('\n'.join(lines))
    if not args.update_workspace:
        return
    import wandb
    from wandb_workspaces.workspaces import internal
    from wandb_workspaces.workspaces.internal import gql
    before = internal.get_view_dict('peter-sk-sdu', 'DFM5', '3fvncok3gjh')
    original = json.loads(before['spec'])
    updated = copy.deepcopy(original)
    sections = updated['section']['panelBankConfig']['sections']
    added = []
    for task in tasks:
        name = langs[task['language']] + ' Headline Metrics'
        section = next(s for s in sections if s['name'] == name)
        key = f"euroeval/{task['language']}/{task['category']}/{task['dataset']}/{task['metric']}"
        if any(key in p.get('config', {}).get('metrics', []) for p in section['panels']):
            continue
        panel = copy.deepcopy(section['panels'][-1])
        panel['__id__'] = uuid.uuid4().hex[:16]
        panel['config'].update(chartTitle='EuroEval ' + task['dataset'], metrics=[key],
                               xAxis='euroeval/epoch', xAxisTitle='epoch')
        section['panels'].append(panel)
        added.append(panel['__id__'])
    restored = copy.deepcopy(updated)
    for s in restored['section']['panelBankConfig']['sections']:
        s['panels'] = [p for p in s['panels'] if p['__id__'] not in added]
    assert restored == original
    root = Path('logs/wandb_workspace_specs') / ('euro-additions-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    root.mkdir(parents=True)
    (root/'before-view.json').write_text(json.dumps(before, indent=2))
    (root/'intended-spec.json').write_text(json.dumps(updated, indent=2))
    if internal.get_view_dict('peter-sk-sdu', 'DFM5', '3fvncok3gjh') != before:
        raise RuntimeError('Concurrent workspace update; refusing stale write')
    mutation = gql('''mutation UpdateExistingView($id: ID!, $spec: String!) {
      upsertView(input: {id: $id, spec: $spec}) {view {id name} inserted}
    }''')
    wandb.Api().client.execute(mutation, {'id': before['id'], 'spec': json.dumps(updated)})
    after = internal.get_view_dict('peter-sk-sdu', 'DFM5', '3fvncok3gjh')
    (root/'after-view.json').write_text(json.dumps(after, indent=2))
    assert json.loads(after['spec']) == updated
    print('Verified added panels:', len(added), root)


if __name__ == '__main__':
    main()
