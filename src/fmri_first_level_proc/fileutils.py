"""Filesystem helpers: safe output-directory clearing and filename sanitizing."""

import logging
import re
import shutil
from pathlib import Path

from .exceptions import GuardError


def remove_files_from_dir(dir_string, logger=None):
    """Remove all files, links, and subdirectories from a directory."""
    _log = logger or logging.getLogger(__name__)
    directory = Path(dir_string)
    resolved = directory.resolve()
    if resolved == Path("/") or resolved == Path.home() or len(str(resolved)) < 5:
        raise GuardError(f"Refusing to clear dangerous path: '{dir_string}' (resolved: '{resolved}').")
    if not directory.is_dir():
        _log.warning("'%s' does not yet exist. --remove_previous will be ignored.", dir_string)
        return
    for item in directory.iterdir():
        try:
            # Symlinks are unlinked, never followed into
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(item)
            else:
                item.unlink()
        except OSError as e:
            _log.error("Error deleting '%s': %s", item, e)


def sanitize_filename_label(label):
    """Replace filesystem-unsafe characters with underscores.

    Preserves alphanumerics, hyphens, underscores, and periods. All other
    characters (including spaces, slashes, colons) are replaced with '_'.
    Consecutive underscores are collapsed.
    """
    sanitized = re.sub(r'[^\w.\-]', '_', label)
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized.strip('_')
