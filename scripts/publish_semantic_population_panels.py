"""Select semantic multilingual scores without removing legacy run history."""
import argparse
import copy
from datetime import datetime
import json
from pathlib import Path

from scripts.prepare_semantic_acceptability_averages import VERSIONS


def update_spec(original):
    updated = copy.deepcopy(original)
    changes = []
    for section in updated['section']['panelBankConfig']['sections']:
        for panel in section['panels']:
            config = panel.get('config', {})
            keys = config.get('metrics', [])
            result = []
            for key in keys:
                new = key
                for old, version in VERSIONS.items():
                    prefix = 'avg_population/' + old + '/'
                    if key.startswith(prefix):
                        new = 'avg_population/' + version + '/' + key[len(prefix):]
                        break
                # Unlike Danish, these new tasks have no historical runs whose
                # curves would disappear when switching the selected metric.
                if key.startswith('dfm_eval/dala_') and key.endswith('/linguistic-acceptability/dfm_evals_macro_f1'):
                    new = key.replace('/linguistic-acceptability/dfm_evals_macro_f1',
                                      '/semantic_v1/macro_f1')
                if new != key:
                    changes.append({'section': section['name'], 'old': key, 'new': new})
                result.append(new)
            if result != keys:
                config['metrics'] = result
                if any('/semantic_v1/' in key for key in result):
                    title = config.get('chartTitle', 'DaLA macro F1')
                    config['chartTitle'] = title + ' (semantic)'
    return updated, changes


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    import wandb
    from wandb_workspaces.workspaces import internal
    from wandb_workspaces.workspaces.internal import gql
    before = internal.get_view_dict('peter-sk-sdu', 'DFM5', '3fvncok3gjh')
    updated, changes = update_spec(json.loads(before['spec']))
    print(json.dumps(changes, indent=2))
    if not args.apply or not changes:
        return
    root = Path('logs/wandb_workspace_specs') / ('semantic-acceptability-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    root.mkdir(parents=True, exist_ok=False)
    for name, value in [('before.json', before), ('intended.json', updated), ('changes.json', changes)]:
        (root / name).write_text(json.dumps(value, indent=2) + '\n')
    if internal.get_view_dict('peter-sk-sdu', 'DFM5', '3fvncok3gjh') != before:
        raise RuntimeError('Concurrent workspace edit; refusing stale update')
    mutation = gql('''mutation UpdateExistingView($id: ID!, $spec: String!) {
      upsertView(input: {id: $id, spec: $spec}) {view {id name} inserted}
    }''')
    wandb.Api().client.execute(mutation, {'id': before['id'], 'spec': json.dumps(updated)})
    after = internal.get_view_dict('peter-sk-sdu', 'DFM5', '3fvncok3gjh')
    (root / 'after.json').write_text(json.dumps(after, indent=2) + '\n')
    assert json.loads(after['spec']) == updated
    print('Verified remote spec:', root)


if __name__ == '__main__':
    main()
