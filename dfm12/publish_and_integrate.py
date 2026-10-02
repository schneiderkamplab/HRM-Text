"""Publish the registered exports, then stage all DFM12 additions without sampling."""
from pathlib import Path
import subprocess
import sys
import time

from .io import load, lock, write_json


def publish_registered_root(export):
    root = Path(export)
    packages = load(root / 'manifest.json')['packages']
    schemas = {load(root / p['name'] / 'metadata/manifest.json').get('schema')
               for p in packages if p['rows']}
    if schemas == {'dfm12-multilingual-completed-export-v1'}:
        from .upload_multilingual_completed import publish
        publish([root], Path('exports_dfm12/multilingual-publication-20260929-v1'))
    elif schemas == {'dfm12-identity21-accepted-export-v1'}:
        from .export_identity_multilingual import publish
        publish(root)
    else:
        subprocess.run([sys.executable, '-u', '-m', 'dfm12.upload_exports',
                        '--output', export], check=True)


def main():
    root = Path('data/dfm12/publication-integration-20260929')
    root.mkdir(parents=True, exist_ok=True)
    with lock(root / '.lock'):
        config = load('dfm12/training_sources.json')
        try:
            for export in config['export_roots']:
                write_json(root / 'status.json', dict(phase='upload', export_root=export, time=time.time()))
                publish_registered_root(export)
            write_json(root / 'status.json', dict(phase='stage_inputs', time=time.time()))
            subprocess.run([sys.executable, '-u', '-m', 'dfm12.build_training',
                            '--suffix', 'completed-campaign-20260929', '--prepare-only'], check=True)
            write_json(root / 'status.json', dict(phase='complete', time=time.time(), sampled=False))
        except Exception as exc:
            write_json(root / 'status.json', dict(phase='failed', error=str(exc), time=time.time()))
            raise


if __name__ == '__main__':
    main()
