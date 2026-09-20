"""Shared archive and checksum operations for desktop packages."""
import hashlib
import os
from pathlib import Path
import shutil


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
