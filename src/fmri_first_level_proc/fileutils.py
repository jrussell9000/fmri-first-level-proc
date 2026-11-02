"""Filesystem helpers: safe output-directory clearing and filename sanitizing."""

import logging
import os
import re
import shutil

from .exceptions import GuardError


def remove_files_from_dir(dir_string, logger=None):
    """Remove all files, links, and subdirectories from a directory."""
    _log = logger or logging.getLogger(__name__)
    resolved = os.path.realpath(dir_string)
    if resolved == "/" or resolved == os.path.expanduser("~") or len(resolved) < 5:
        raise GuardError(f"Refusing to clear dangerous path: '{dir_string}' (resolved: '{resolved}').")
    if not os.path.isdir(dir_string):
        _log.warning("'%s' does not yet exist. --remove_previous will be ignored.", dir_string)
    else:
        for item_name in os.listdir(dir_string):
            item_path = os.path.join(dir_string, item_name)
            try:
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except OSError as e:
                _log.error("Error deleting '%s': %s", item_path, e)


def sanitize_filename_label(label):
    """Replace filesystem-unsafe characters with underscores.

    Preserves alphanumerics, hyphens, underscores, and periods. All other
    characters (including spaces, slashes, colons) are replaced with '_'.
    Consecutive underscores are collapsed.
    """
    sanitized = re.sub(r'[^\w.\-]', '_', label)
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized.strip('_')
