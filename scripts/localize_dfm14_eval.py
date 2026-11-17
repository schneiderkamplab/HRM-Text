"""Generate verified machine-local DFM14 configs without modifying shared pins."""
from pathlib import Path
import hashlib
import json
import yaml

from dfm12.io import write_json


def main():
    root = Path(__file__).resolve().parents[1]
    output = root/'data/dfm14/evaluation/local-config'
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((root/'config/dfm14_dala_heldout.json').read_text())
    for entry in manifest['languages'].values():
        for pin in [entry['selected'], *entry['input_pins']]:
            old = pin['path']
            candidates = [Path(old), Path(old.replace('/work/dfm/HRM-Text', str(root), 1))]
            if '/source/work/' in old:
                candidates.append(Path('/work/'+old.split('/source/work/', 1)[1]))
            matched = [p for p in candidates if p.is_file()
                       and hashlib.sha256(p.read_bytes()).hexdigest() == pin['sha256']]
            if not matched:
                raise ValueError('Missing or changed heldout: '+old)
            pin['path'] = str(matched[0].resolve())
    target = output/'heldout.json'
    write_json(target, manifest)
    config = yaml.safe_load((root/'config/dfm_evals_dfm14.yaml').read_text())

    def localize(value):
        if isinstance(value, dict):
            return {k: localize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [localize(v) for v in value]
        if isinstance(value, str):
            return value.replace('/work/dfm/HRM-Text/config/dfm14_dala_heldout.json', str(target)).replace(
                '/work/dfm/HRM-Text/evaluation/', str(root/'evaluation')+'/')
        return value
    (output/'tasks.yaml').write_text(yaml.safe_dump(localize(config), sort_keys=False))
    print(output/'tasks.yaml')


if __name__ == '__main__':
    main()
