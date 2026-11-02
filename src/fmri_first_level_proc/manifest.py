"""Per-block run manifest: stale-output guard, crash recovery, and a machine-readable result record.

Each analysis block writes ``{out_dir}/{out_file_pre}_manifest.json``. Pipeline
stages skip work whose output file already exists, so without a guard a rerun
with a changed config would silently reuse old outputs, and a crashed attempt
could leave partial files that look finished. The manifest records a hash of
the output-affecting config and the files this block created, which lets a
rerun decide:

- completed, same config, outputs present -> skip, return the recorded result
- completed, same config, outputs missing -> rerun; stages regenerate what is missing
- started/failed (crashed), same config   -> delete files the crashed attempt created, rerun
- different config                        -> ConfigError, unless force=True, which
                                             deletes this block's files and reruns

Ownership is tracked by snapshotting out_dir before and after each run rather
than by filename prefix, because blocks may share an out_dir and one prefix can
be a prefix of another (``sub01`` vs ``sub01_rest``). Blocks sharing an out_dir
must not run concurrently.
"""

import dataclasses
import datetime
import functools
import hashlib
import json
import logging
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .exceptions import ConfigError
from .reporting import FirstLevelResult

MANIFEST_VERSION = 1

# Fields that change how a block runs but not what it produces
_HASH_EXCLUDE = {"num_cores", "remove_previous", "analysis_name"}

_MANIFEST_SUFFIX = "_manifest.json"


def manifest_path(config) -> Path:
    return Path(config.out_dir) / f"{config.out_file_pre}{_MANIFEST_SUFFIX}"


def config_hash(config) -> str:
    """SHA-256 of the output-affecting ResolvedConfig fields."""
    fields = {k: v for k, v in dataclasses.asdict(config).items() if k not in _HASH_EXCLUDE}
    return hashlib.sha256(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()


def read_manifest(path):
    """Return the manifest dict, or None if absent. Raises ConfigError if unreadable."""
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError(
            f"Run manifest {path} is unreadable ({e}); outputs in its out_dir cannot be trusted. "
            "Set remove_previous: true or use a fresh out_dir."
        ) from e


def _package_version():
    try:
        return version("fmri-first-level-proc")
    except PackageNotFoundError:
        return None


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _write(path, data):
    # Atomic replace so a crash never leaves a half-written manifest
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def _snapshot(out_dir: Path) -> set[str]:
    """Relative paths of all files under out_dir, excluding manifests."""
    if not out_dir.is_dir():
        return set()
    return {
        p.relative_to(out_dir).as_posix()
        for p in out_dir.rglob("*")
        if (p.is_file() or p.is_symlink())
        and not p.name.endswith((_MANIFEST_SUFFIX, _MANIFEST_SUFFIX + ".tmp"))
    }


def _remove(out_dir: Path, rel_paths, logger):
    """Delete the given files, then any directories left empty by that."""
    parents = set()
    for rel in rel_paths:
        target = out_dir / rel
        target.unlink(missing_ok=True)
        parents.update(p for p in target.parents if p != out_dir and out_dir in p.parents)
    for d in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        try:
            d.rmdir()
        except OSError:
            pass  # not empty: holds files this block does not own
    if rel_paths:
        logger.info("Removed %d file(s) from a previous run of this block.", len(rel_paths))


def _crashed_files(prev, out_dir):
    """Files created by an attempt that never completed."""
    return _snapshot(out_dir) - set(prev.get("preexisting_files", []))


def manifested(run):
    """Decorator for pipeline ``run(config, logger)``; adds a ``force`` keyword. See module docstring."""
    @functools.wraps(run)
    def wrapper(config, logger=None, *, force=False):
        log = logger or logging.getLogger(__name__)
        out_dir = Path(config.out_dir)
        path = manifest_path(config)
        digest = config_hash(config)

        # remove_previous clears out_dir inside run(), so prior state is irrelevant
        prev = None if config.remove_previous else read_manifest(path)
        owned: set[str] = set()

        if prev is not None:
            same_config = prev.get("config_hash") == digest
            prev_owned = set(prev.get("owned_files", []))
            completed = prev.get("status") == "completed"

            if completed and same_config:
                recorded = prev["result"]
                if all(Path(p).exists() for p in recorded["output_files"]):
                    log.info("%s: outputs from an identical config already complete (%s); skipping.",
                             config.out_file_pre, path)
                    return FirstLevelResult(
                        status=recorded["status"],
                        output_dir=out_dir,
                        warnings=recorded["warnings"],
                        qc_summary=recorded["qc_summary"],
                        output_files=recorded["output_files"],
                    )
                log.info("%s: some recorded outputs are missing; rerunning to regenerate them.",
                         config.out_file_pre)
                owned = prev_owned
            elif same_config:
                log.warning("%s: previous attempt did not complete (status=%s); discarding its partial outputs.",
                            config.out_file_pre, prev.get("status"))
                _remove(out_dir, sorted(_crashed_files(prev, out_dir)), log)
                owned = prev_owned
            else:
                if not force:
                    raise ConfigError(
                        f"{out_dir} holds outputs for '{config.out_file_pre}' from a different configuration "
                        f"(manifest {path}). Reusing them would mix results. Use --force to delete this "
                        "block's previous outputs and rerun, set remove_previous: true, or use a new out_dir."
                    )
                log.warning("%s: configuration changed; --force set, deleting this block's previous outputs.",
                            config.out_file_pre)
                stale = prev_owned if completed else prev_owned | _crashed_files(prev, out_dir)
                _remove(out_dir, sorted(stale), log)

        # With remove_previous, run() empties out_dir first, so everything left afterwards is ours
        before = set() if config.remove_previous else _snapshot(out_dir)
        record = {
            "manifest_version": MANIFEST_VERSION,
            "package_version": _package_version(),
            "analysis_type": config.analysis_type,
            "analysis_name": config.analysis_name,
            "out_file_pre": config.out_file_pre,
            "config_hash": digest,
            "status": "started",
            "started_utc": _now(),
            "owned_files": sorted(owned),
            "preexisting_files": sorted(before),
        }
        out_dir.mkdir(parents=True, exist_ok=True)
        _write(path, record)

        try:
            result = run(config, logger)
        except BaseException as e:
            _write(path, {**record, "status": "failed", "finished_utc": _now(),
                          "error": f"{type(e).__name__}: {e}"})
            raise

        record.pop("preexisting_files")
        _write(path, {
            **record,
            "status": "completed",
            "finished_utc": _now(),
            "owned_files": sorted(owned | (_snapshot(out_dir) - before)),
            "result": {
                "status": result.status,
                "output_files": [str(p) for p in result.output_files],
                "warnings": result.warnings,
                "qc_summary": result.qc_summary,
            },
        })
        return result

    return wrapper
