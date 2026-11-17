"""Expose the scheduler package when running directly from the repository root.

The installable project lives one directory below this source-layout shim.
Installed wheels continue to use that package unchanged.
"""
from pathlib import Path

__path__.append(str(Path(__file__).with_name('eval_scheduler')))
from .eval_scheduler import __version__
