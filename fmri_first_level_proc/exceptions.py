"""Custom exception hierarchy for fmri-first-level-proc."""


class FmriFirstLevelError(Exception):
    """Base exception for fmri-first-level-proc."""

    def __init__(self, message: str = "", context: dict | None = None) -> None:
        super().__init__(message)
        self.context: dict = context if context is not None else {}


class ConfigError(FmriFirstLevelError):
    """Invalid config: missing required fields, incompatible options, schema violations."""


class InputError(FmriFirstLevelError):
    """Input file missing, malformed, wrong dimensions, or unreadable."""


class ToolUnavailableError(FmriFirstLevelError):
    """External tool binary not found on PATH."""


class ToolVersionError(FmriFirstLevelError):
    """Installed external tool or library version is below the minimum recorded in the packaged lockfile."""


class ToolExecutionError(FmriFirstLevelError):
    """External tool command returned non-zero or failed to produce expected output."""


class ModelError(FmriFirstLevelError):
    """Data quality prevents model estimation: singularity, insufficient DOF, no surviving trials."""


class GuardError(FmriFirstLevelError):
    """Pipeline invariant violation: unexpected state indicating a bug."""


def exit_code(exc):
    """Return the CLI exit code for an exception.

    ConfigError, InputError -> 2; ModelError -> 5; ToolUnavailableError,
    ToolVersionError, ToolExecutionError, subprocess.CalledProcessError -> 4;
    GuardError and any other exception -> 1.
    """
    import subprocess

    if isinstance(exc, (ConfigError, InputError)):
        return 2
    if isinstance(exc, ModelError):
        return 5
    if isinstance(exc, (ToolUnavailableError, ToolVersionError, ToolExecutionError,
                        subprocess.CalledProcessError)):
        return 4
    return 1
