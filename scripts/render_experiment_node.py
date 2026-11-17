#!/usr/bin/env python3
"""Materialize portable recipe snapshots for review; never launch or edit a queue."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(profile, recipes, template_dir, output):
    if profile.get('launch_enabled'):
        raise ValueError('Recipe preparation requires launch_enabled=false')
    for key in ('repo_root', 'env_root'):
        if not Path(profile[key]).is_absolute():
            raise ValueError(f'{key} must be absolute')
    output.mkdir(parents=True, exist_ok=False)
    commands = {}
    for name, original in recipes['runs'].items():
        command = [s.replace('${repo_root}', profile['repo_root']).replace('${env_root}', profile['env_root']) for s in original]
        if '--config-path' in command:
            index = command.index('--config-path') + 1
            config_name = command[command.index('--config-name') + 1]
            if Path(config_name).name != config_name:
                raise ValueError('Invalid config name')
            config = (template_dir / (config_name + '.yaml')).read_text()
            config = config.replace('${oc.env:HRM_REPO_ROOT}', profile['repo_root'])
            (output / (config_name + '.yaml')).write_text(config)
            command[index] = str(output.resolve())
        commands[name] = command
    result = {'node': profile['node_id'], 'launch_enabled': False,
              'initial_runs': profile['initial_runs'], 'commands': commands,
              'warning': 'Recipe snapshots only. Resolve resume checkpoints, ownership and scheduler dependencies before launch.'}
    (output / 'commands.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, default=ROOT / 'config/deployment/node2.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    templates = ROOT / 'config/deployment/dfm11'
    result = render(json.loads(args.profile.read_text()), json.loads((templates / 'commands.json').read_text()), templates, args.output)
    print(f"Prepared {len(result['commands'])} recipes; launch remains disabled")


if __name__ == '__main__':
    main()
