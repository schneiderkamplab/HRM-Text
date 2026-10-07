"""Import pinned remote heldouts, not training rows; produce local eval configs."""
import copy
import json
from pathlib import Path
import subprocess

import yaml
from dfm12.io import file_hash, load, write_json
from dfm14.catalog import LANGUAGES
from dfm14.prepare_evals import build_eval_definitions

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data/dfm14/evaluation'
MANIFEST = ROOT/'config/dfm14_dala_heldout.json'
SUITE = ROOT/'config/dfm_evals_dfm14.yaml'
REGISTRY = ROOT/'config/dfm14_dala_eval_registry.json'
POPULATION = ROOT/'config/multilingual_headline_populations_dfm14.json'
SSH = ['ssh', '-p', '6768', '-o', 'BatchMode=yes', 'ucloud@ssh.cloud.sdu.dk']


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    original = json.loads(subprocess.check_output(SSH+[
        'cat /work/dfm/HRM-Text/config/dfm14_dala_heldout.json']))
    assert set(original['languages']) == set(LANGUAGES)
    write_json(OUT/'remote-manifest.json', original)
    pins = {p['path']: p['sha256'] for e in original['languages'].values()
            for p in [e['selected'], *e['input_pins']]}
    download = OUT/'source'
    download.mkdir(exist_ok=True)
    subprocess.run(['rsync', '-aL', '--partial', '--files-from=-',
        '-e', 'ssh -p 6768 -o BatchMode=yes',
        'ucloud@ssh.cloud.sdu.dk:/', str(download)+'/'],
        input=''.join(p.lstrip('/')+'\n' for p in sorted(pins)), text=True, check=True)
    for path, sha in pins.items():
        assert file_hash(download/path.lstrip('/')) == sha, path
    manifest = copy.deepcopy(original)
    for e in manifest['languages'].values():
        for pin in [e['selected'], *e['input_pins']]:
            pin['path'] = str(download/pin['path'].lstrip('/'))
        assert e['pairs'] == 1000 and e['samples_per_task'] == 2000
    write_json(MANIFEST, manifest)
    old = load(ROOT/'config/multilingual_headline_populations_dfm13_dala_v2_20261006.json')
    suite, tasks, population = build_eval_definitions(ROOT, MANIFEST, SUITE, old)
    SUITE.write_text(yaml.safe_dump(suite, sort_keys=False))
    write_json(REGISTRY, tasks)
    write_json(POPULATION, population)
    write_json(OUT/'prepared.json', dict(languages=list(LANGUAGES), tasks=32, samples_per_task=2000,
        files={str(p):file_hash(p) for p in (MANIFEST, SUITE, REGISTRY, POPULATION)},
        remote_manifest_sha256=file_hash(OUT/'remote-manifest.json'), gpu_calls=False))
    print('Prepared32 tasks for16 languages', flush=True)


if __name__ == '__main__':
    main()
