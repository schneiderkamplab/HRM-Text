"""Add multilingual panels without reserializing existing workspace models."""
import copy
import json
from pathlib import Path
import uuid

import wandb
from wandb_workspaces.workspaces import internal
from wandb_workspaces.workspaces.internal import gql
from scripts.multilingual_workspace_panels import panels

ROOT = Path('logs/wandb_workspace_specs/3fvncok3gjh-multilingual-20260930')


def save(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2) + '\n')


def main():
    ROOT.mkdir(parents=True, exist_ok=False)
    before = internal.get_view_dict('peter-sk-sdu', 'DFM5', '3fvncok3gjh')
    save('before-view.json', before)
    original = json.loads(before['spec'])
    save('before-spec.json', original)
    updated = copy.deepcopy(original)
    sections = updated['section']['panelBankConfig']['sections']
    headline = next(s for s in sections if s['name'] == 'Headline Averages')
    if any(s['name'] == 'Multilingual Headline Metrics' for s in sections):
        raise ValueError('Section already exists; inspect before making further changes')
    template = headline['panels'][0]

    def panel(definition):
        title, metric, axis = definition
        result = copy.deepcopy(template)
        result['__id__'] = uuid.uuid4().hex[:16]
        result['config'].update(chartTitle=title, metrics=[metric], xAxis=axis)
        return result

    _, definitions = panels(Path('config/multilingual_headline_populations_20260930.json'),
                            Path('config/euroeval_dfm12_multilingual.yaml'))
    headline['panels'].append(panel(definitions[0]))
    section = copy.deepcopy(headline)
    section.update(__id__=uuid.uuid4().hex[:16], name='Multilingual Headline Metrics',
                   panels=[panel(d) for d in definitions])
    sections.append(section)
    # Removing exactly the additions must recover the entire original spec.
    restored = copy.deepcopy(updated)
    restored_sections = restored['section']['panelBankConfig']['sections']
    restored_sections.pop()
    next(s for s in restored_sections if s['name'] == 'Headline Averages')['panels'].pop()
    assert restored == original
    save('intended-spec.json', updated)
    current = internal.get_view_dict('peter-sk-sdu', 'DFM5', '3fvncok3gjh')
    if current != before:
        raise RuntimeError('Workspace changed during preparation; refusing stale update')
    mutation = gql('''mutation UpdateExistingView($id: ID!, $spec: String!) {
      upsertView(input: {id: $id, spec: $spec}) {view {id name} inserted}
    }''')
    response = wandb.Api().client.execute(mutation, {'id': before['id'], 'spec': json.dumps(updated)})
    save('mutation-response.json', response)
    after = internal.get_view_dict('peter-sk-sdu', 'DFM5', '3fvncok3gjh')
    save('after-view.json', after)
    actual = json.loads(after['spec'])
    save('after-spec.json', actual)
    if actual != updated or after['id'] != before['id'] or after['displayName'] != before['displayName']:
        raise RuntimeError('Remote persisted state differs; inspect saved snapshots')
    receipt = dict(remote_verified=True, existing_spec_preserved=True,
                   headline_panels_added=1, multilingual_panels_added=len(definitions),
                   original_sections=len(sections)-1, final_sections=len(sections),
                   selections_unchanged=actual['section']['runSets']==original['section']['runSets'])
    save('verification.json', receipt)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
