"""Repair multilingual panel placement in the owner's existing DFM5 view."""
import copy
import json
from datetime import datetime
from pathlib import Path

import wandb
from wandb_workspaces.workspaces import internal
from wandb_workspaces.workspaces.internal import gql


def main():
    root = Path('logs/wandb_workspace_specs') / (
        '3fvncok3gjh-order-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    root.mkdir(parents=True)
    before = internal.get_view_dict('peter-sk-sdu', 'DFM5', '3fvncok3gjh')
    original = json.loads(before['spec'])
    updated = copy.deepcopy(original)
    sections = updated['section']['panelBankConfig']['sections']
    key = 'avg_population/multilingual_v1/score'
    for name in ('Headline Averages', 'Multilingual Headline Metrics'):
        section = next(s for s in sections if s['name'] == name)
        matches = [p for p in section['panels'] if key in p.get('config', {}).get('metrics', [])]
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one average panel in {name}')
        panel = matches[0]
        panel['config'].update(chartTitle='Multilingual headline average',
                               xAxis='avg_population/epoch', xAxisTitle='epoch')
        section['panels'] = [panel] + [p for p in section['panels'] if p is not panel]
        section['isOpen'] = True
        section['sorted'] = 0
        if name == 'Headline Averages':
            section.setdefault('flowConfig', {})['rowsPerPage'] = 5
    multilingual = next(s for s in sections if s['name'] == 'Multilingual Headline Metrics')
    sections.remove(multilingual)
    insertion = next(i for i, s in enumerate(sections) if s['name'] == 'Training Metrics & Params')
    sections.insert(insertion, multilingual)
    assert updated['section']['runSets'] == original['section']['runSets']
    old_panels = {p['__id__'] for s in original['section']['panelBankConfig']['sections'] for p in s['panels']}
    new_panels = {p['__id__'] for s in sections for p in s['panels']}
    assert old_panels == new_panels
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
    print(f'Verified saved ordering. Backup: {root}')


if __name__ == '__main__':
    main()
