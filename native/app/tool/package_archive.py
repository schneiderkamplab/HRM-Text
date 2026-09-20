"""Shared archive and checksum operations for desktop packages."""
import hashlib
import os
import re
from pathlib import Path
import shutil
import subprocess


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_archive(stage, output, target):
    archive = Path(shutil.make_archive(str(stage.parent / stage.name),
                                      'gztar' if target == 'linux' else 'zip',
                                      stage.parent, stage.name))
    destination = output / archive.name
    os.replace(archive, destination)
    (output / (destination.name + '.sha256')).write_text(
        digest(destination) + '  ' + destination.name + '\n', encoding='utf-8')
    return destination


def app_version():
    pubspec = Path(__file__).resolve().parents[1] / 'pubspec.yaml'
    match = re.search(r'^version:\s*([^\s+]+)', pubspec.read_text(), re.MULTILINE)
    if not match:
        raise ValueError('Missing app version in pubspec.yaml')
    return match.group(1)


def package_name(version, platform, architecture):
    return f'dfm-mimir-{version}-{platform}-{architecture}'


def compile_server(dart, output):
    package = Path(__file__).resolve().parents[1] / 'packages/mimir_api'
    subprocess.run([str(dart), 'pub', 'get'], cwd=package, check=True)
    subprocess.run([str(dart), 'compile', 'exe', 'bin/server.dart', '-o', str(output)],
                   cwd=package, check=True)
