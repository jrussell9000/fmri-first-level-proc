"""Execution engine for the fmri-first-level-proc pipelines.

Provides ``RunContext``, which runs always-run steps and ledgered stages
through a staging directory: outputs are validated, recorded in the ledger
and promoted to out_dir with os.replace. A step appends a staged record
only when its output path set changed; a stage appends a staged record
and, after promotion, a completion record carrying its stage hash. A
ledgered stage reruns when it has no valid completion record, its stage
hash changed (declared config fields, derived files and values, upstream
hashes or tool versions), a recorded output is missing, an upstream stage
ran in this invocation, or its last completion recorded failed runs;
otherwise its qc fragment and warnings are replayed. ``finish`` cross-checks
expected outputs, retires unlisted recorded paths and writes qc_summary.json
with a ``run_status`` record. ``run_with_status`` wraps a pipeline body: on
any exception it writes a failure qc_summary.json (``analysis_type``,
``run_status`` and provenance only, never partial metrics) through
``write_failure_qc`` and re-raises.
"""

import copy
import dataclasses
import gzip
import logging
import os
import shutil
import time
from pathlib import Path

import numpy as np

from . import checkpoint, names, qc
from .exceptions import GuardError, InputError, ToolExecutionError, exit_code
from .first_level_utils import (
    FirstLevelResult,
    get_warnings,
    graded_warning,
    reemit_warning,
    warning_count,
    run_afni_command,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Output:
    """Specification of a single output file from a step or stage.

    Attributes
    ----------
    relpath : str
        Path relative to out_dir (and to the staging dir).
    cls : str
        ``'final'`` or ``'intermediate'``.
    kind : str
        ``'nifti'``, ``'afni_text'``, ``'x1d'``, ``'py_text'``,
        ``'reml_cmd'``, or ``'afni_aux'``.
    producer : str
        Human description of the producing command.
    expected_text : str or None
        For ``py_text``: exact file content.
    expected_rows : int or None
        For ``afni_text`` / ``x1d``: expected row count.
    expected_cols : int or None
        For ``afni_text`` / ``x1d``: expected column count.
    expected_nvols : int or None
        For ``nifti``: expected number of volumes.
    check_grid : bool
        For ``nifti``: compare grid with grid_ref.
    """
    relpath: str
    cls: str
    kind: str
    producer: str = ""
    expected_text: str | None = None
    expected_rows: int | None = None
    expected_cols: int | None = None
    expected_nvols: int | None = None
    check_grid: bool = True


@dataclasses.dataclass
class StageSpec:
    """Hash specification for a ledgered stage."""
    label: str
    fields: tuple = ()
    derived_files: tuple = ()
    derived_values: dict = dataclasses.field(default_factory=dict)
    upstream: tuple = ()


@dataclasses.dataclass
class StepIO:
    """I/O paths for a step or stage function.

    Attributes
    ----------
    label : str
        Step/stage label.
    staging : str
        Absolute path to the staging directory.
    out_dir : str
        Absolute path to the output directory.
    pre : str
        Output file prefix.
    """
    label: str
    staging: str
    out_dir: str
    pre: str

    def path(self, relpath):
        """Return the absolute path inside the staging directory, creating parent dirs."""
        full = os.path.join(self.staging, relpath)
        parent = os.path.dirname(full)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        return full

    def out(self, relpath):
        """Return the absolute path inside out_dir."""
        return os.path.join(self.out_dir, relpath)


@dataclasses.dataclass
class Outcome:
    """Result of a step or stage function."""
    outputs: list = dataclasses.field(default_factory=list)
    qc: dict = dataclasses.field(default_factory=dict)
    deferred_error: Exception | None = None
    reused: bool = False


@dataclasses.dataclass
class RunTracker:
    """Current step label and provenance versions of one pipeline run.

    Read by run_with_status to record where a failed run stopped.
    """
    step: str | None = None
    versions: dict | None = None


# ---------------------------------------------------------------------------
# RunContext
# ---------------------------------------------------------------------------

class RunContext:
    """Execution engine for a single pipeline run.

    Parameters
    ----------
    config : ResolvedConfig
        The configuration (working copy; may be mutated by pipeline steps).
    analysis_type : str
    logger : logging.Logger
    versions : dict
        Provenance versions from runtime_check.
    grid_ref : str
        Path to the reference scan for grid checks.
    tracker : RunTracker, optional
        Updated with the label of each step or stage as it starts.
    """

    def __init__(self, config, analysis_type, logger, versions, grid_ref, tracker=None):
        self.entry_config = copy.deepcopy(config)
        self.config = config
        self.out_dir = os.path.abspath(config.out_dir)
        self.pre = config.out_file_pre
        self.type_label = names.TYPE_LABEL[analysis_type]
        self.analysis_type = analysis_type
        self.ledger_path = os.path.join(self.out_dir, names.ledger(self.pre))
        self.history = None
        self.versions = versions
        self.grid_ref = grid_ref
        self.logger = logger
        self.tracker = tracker

        self.stage_hashes = {}
        self.executed = []
        self.reused = []
        self.failed = {}
        self.dag_order = []
        self.step_outputs = {}
        self.stage_outputs = {}
        self.fragments = []
        self.new_records = []

    # ---- Lifecycle ----

    def start(self):
        """Initialize the engine: refuse unrecorded files, apply remove_previous, load history."""
        if not os.path.exists(self.ledger_path):
            self._refuse_unrecorded()

        if self.config.remove_previous and os.path.exists(self.ledger_path):
            self._remove_previous()

        self.history = checkpoint.read_history(self.ledger_path)
        if self.history.unreadable_lines:
            graded_warning(
                self.logger, "medium", "LEDGER_ENTRY_UNREADABLE",
                f"Ledger {self.ledger_path}: unreadable lines "
                f"{self.history.unreadable_lines}; affected stages rerun.",
                user_facing=True,
            )

    def _refuse_unrecorded(self):
        """Raise InputError if out_dir contains files no ledger records."""
        ext_pre = getattr(self.config, "extract_out_file_pre", None)
        conn_pre = getattr(self.config, "conn_out_file_pre", None)
        prefixes = names.all_prefixes(self.pre, ext_pre, conn_pre)
        template_path = getattr(self.config, "template_path", None)

        # Collect log file paths to exclude
        log_files = set()
        for handler in self.logger.handlers:
            if isinstance(handler, logging.FileHandler):
                log_files.add(os.path.abspath(handler.baseFilename))
        parent = self.logger.parent
        while parent:
            for handler in getattr(parent, "handlers", []):
                if isinstance(handler, logging.FileHandler):
                    log_files.add(os.path.abspath(handler.baseFilename))
            parent = getattr(parent, "parent", None)

        # Collect paths from other ledgers in out_dir
        other_recorded = set()
        for entry in os.listdir(self.out_dir) if os.path.isdir(self.out_dir) else []:
            if entry.endswith("_ledger.jsonl") and entry != names.ledger(self.pre):
                other_path = os.path.join(self.out_dir, entry)
                other_hist = checkpoint.read_history(other_path)
                for rel in checkpoint.recorded_paths(other_hist):
                    other_recorded.add(os.path.join(self.out_dir, rel))

        # Scan for unrecorded files
        unrecorded = []
        if os.path.isdir(self.out_dir):
            for entry in os.listdir(self.out_dir):
                matched = False
                for p in prefixes:
                    if entry.startswith(f"{p}_"):
                        matched = True
                        break
                if template_path and entry == names.legacy_template_resampled(template_path):
                    matched = True
                if entry == "_sequenced_intermediates":
                    matched = True
                if matched:
                    full = os.path.join(self.out_dir, entry)
                    if os.path.isdir(full):
                        for root, _, files in os.walk(full):
                            for f in files:
                                fp = os.path.join(root, f)
                                if fp not in log_files and fp not in other_recorded:
                                    unrecorded.append(os.path.relpath(fp, self.out_dir))
                    else:
                        if full not in log_files and full not in other_recorded:
                            unrecorded.append(entry)

        if unrecorded:
            raise InputError(
                f"No ledger for analysis '{self.pre}' records these files "
                f"(for example, output of an earlier package version or a "
                f"deleted ledger). remove_previous cannot remove them. "
                f"Use an empty out_dir or remove the listed paths. "
                f"Count: {len(unrecorded)}, first 20: {unrecorded[:20]}",
                context={"unrecorded_paths": unrecorded[:20], "count": len(unrecorded)},
            )

    def _remove_previous(self):
        """Ledger-scoped remove_previous."""
        history = checkpoint.read_history(self.ledger_path)
        for rel in sorted(checkpoint.recorded_paths(history)):
            full = os.path.join(self.out_dir, rel)
            if os.path.exists(full):
                os.remove(full)
                # Remove empty parent dirs
                parent = os.path.dirname(full)
                while parent != self.out_dir and parent:
                    try:
                        os.rmdir(parent)
                        parent = os.path.dirname(parent)
                    except OSError:
                        break

        # Remove staging dirs
        if os.path.isdir(self.out_dir):
            for entry in os.listdir(self.out_dir):
                if entry.startswith(f".staging_{self.pre}_"):
                    shutil.rmtree(os.path.join(self.out_dir, entry), ignore_errors=True)

        # Remove ledger last
        if os.path.exists(self.ledger_path):
            os.remove(self.ledger_path)

    # ---- Validation ----

    def _validate(self, io, out):
        """Validate a single output file."""
        path = io.path(out.relpath)
        if not os.path.exists(path):
            if out.kind == "py_text":
                raise GuardError(f"Expected Python-written file not found: {out.relpath}")
            raise ToolExecutionError(
                f"Expected output file not found: {out.relpath} "
                f"(producer: {out.producer})"
            )

        if out.kind == "nifti":
            # Validate NIfTI is readable
            try:
                if path.endswith(".gz"):
                    with gzip.open(path, "rb") as f:
                        while True:
                            chunk = f.read(1024 * 1024)
                            if not chunk:
                                break
                else:
                    with open(path, "rb") as f:
                        while True:
                            chunk = f.read(1024 * 1024)
                            if not chunk:
                                break
            except Exception as e:
                raise ToolExecutionError(
                    f"Validation failed for {out.relpath} produced by "
                    f"{out.producer}: decompression error: {e}"
                ) from e

            if out.check_grid:
                grid_out = run_afni_command(
                    ["3dinfo", "-same_grid", self.grid_ref, path],
                    capture_output=True,
                    description=f"grid check {out.relpath}",
                    logger=self.logger,
                )
                if grid_out.strip().split()[0] != "1":
                    raise ToolExecutionError(
                        f"Validation failed for {out.relpath} produced by "
                        f"{out.producer}: grid mismatch with {self.grid_ref}"
                    )

            if out.expected_nvols is not None:
                nv_out = run_afni_command(
                    ["3dinfo", "-nv", path],
                    capture_output=True,
                    description=f"nv check {out.relpath}",
                    logger=self.logger,
                )
                nv = int(nv_out.strip())
                if nv != out.expected_nvols:
                    raise ToolExecutionError(
                        f"Validation failed for {out.relpath} produced by "
                        f"{out.producer}: expected {out.expected_nvols} volumes, "
                        f"found {nv}"
                    )

        elif out.kind in ("afni_text", "x1d"):
            try:
                data = np.loadtxt(path, comments="#", ndmin=2)
            except Exception as e:
                raise ToolExecutionError(
                    f"Validation failed for {out.relpath} produced by "
                    f"{out.producer}: parse error: {e}"
                ) from e
            if out.expected_rows is not None and data.shape[0] != out.expected_rows:
                raise ToolExecutionError(
                    f"Validation failed for {out.relpath} produced by "
                    f"{out.producer}: expected {out.expected_rows} rows, "
                    f"found {data.shape[0]}"
                )
            if out.expected_cols is not None and data.shape[1] != out.expected_cols:
                raise ToolExecutionError(
                    f"Validation failed for {out.relpath} produced by "
                    f"{out.producer}: expected {out.expected_cols} cols, "
                    f"found {data.shape[1]}"
                )

        elif out.kind == "py_text":
            with open(path, "r", newline="") as f:
                content = f.read()
            if out.expected_text is not None and content != out.expected_text:
                raise GuardError(
                    f"Python-written file {out.relpath} content does not match "
                    f"expected text (len actual={len(content)}, "
                    f"expected={len(out.expected_text)})"
                )

        elif out.kind == "reml_cmd":
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                raise ToolExecutionError(
                    f"Validation failed for {out.relpath}: REML_cmd file is empty"
                )
            if "3dREMLfit" not in content:
                raise ToolExecutionError(
                    f"Validation failed for {out.relpath}: REML_cmd file does "
                    f"not contain '3dREMLfit'"
                )

        elif out.kind == "afni_aux":
            # File exists and decodes as UTF-8
            try:
                with open(path, "r", encoding="utf-8") as f:
                    f.read()
            except UnicodeDecodeError as e:
                raise ToolExecutionError(
                    f"Validation failed for {out.relpath}: not valid UTF-8: {e}"
                ) from e

    # ---- Promotion ----

    def _promote(self, io, outputs):
        """Move validated outputs from staging to out_dir."""
        for out in outputs:
            src = io.path(out.relpath)
            dst = os.path.join(self.out_dir, out.relpath)
            parent = os.path.dirname(dst)
            if parent:
                os.makedirs(parent, exist_ok=True)
            os.replace(src, dst)

    def _path_set(self, outputs):
        return frozenset((o.relpath, o.cls) for o in outputs)

    def _latest_staged_set(self, label):
        """Return the path set from the last staged record for this label."""
        all_records = (self.history.records if self.history else []) + [
            r for r in self.new_records if isinstance(r, checkpoint.StagedRecord)
        ]
        result = frozenset()
        for rec in all_records:
            if isinstance(rec, checkpoint.StagedRecord) and rec.step == label:
                result = frozenset((o.path, o.cls) for o in rec.outputs)
        return result

    # ---- Always-run step ----

    def run_step(self, label, fn):
        """Execute an always-run step.

        Parameters
        ----------
        label : str
            Step label (e.g. ``'task-act-events'``).
        fn : callable
            ``fn(io: StepIO) -> Outcome``. Exceptions propagate; the
            staging directory is left in place on failure.

        Returns
        -------
        Outcome
        """
        self._track(label)
        staging = os.path.join(self.out_dir, names.staging_dir(self.pre, label))
        if os.path.exists(staging):
            shutil.rmtree(staging)
        os.makedirs(staging)

        io = StepIO(label=label, staging=staging, out_dir=self.out_dir, pre=self.pre)
        outcome = fn(io)

        # Validate
        for out in outcome.outputs:
            self._validate(io, out)

        # Staged record (only if path set changed)
        current_set = self._path_set(outcome.outputs)
        if current_set != self._latest_staged_set(label):
            staged = checkpoint.StagedRecord(
                step=label,
                outputs=[checkpoint.OutputRecord(o.relpath, o.cls) for o in outcome.outputs],
                timestamp_utc=checkpoint.utc_now(),
            )
            checkpoint.append_record(self.ledger_path, staged)
            self.new_records.append(staged)

        # Promote
        self._promote(io, outcome.outputs)
        shutil.rmtree(staging, ignore_errors=True)

        self.step_outputs[label] = outcome.outputs

        if outcome.qc:
            self.fragments.append((label, outcome.qc))

        if outcome.deferred_error:
            raise outcome.deferred_error

        return outcome

    # ---- Ledgered stage ----

    def stage_hash(self, spec):
        """Compute the hash payload for a stage spec."""
        entry_fields = {}
        config_fields = {}
        for f in spec.fields:
            entry_fields[f] = getattr(self.entry_config, f, None)
            config_fields[f] = getattr(self.config, f, None)

        derived_hashes = {}
        for p in spec.derived_files:
            derived_hashes[p] = checkpoint.sha256_file(p)

        upstream_hashes = {}
        for u in spec.upstream:
            if u not in self.stage_hashes:
                raise GuardError(
                    f"Upstream stage '{u}' not yet hashed in this invocation "
                    f"(required by '{spec.label}')."
                )
            upstream_hashes[u] = self.stage_hashes[u]

        payload = {
            "label": spec.label,
            "fields": {f: [entry_fields[f], config_fields[f]] for f in spec.fields},
            "derived_files": derived_hashes,
            "derived_values": spec.derived_values,
            "upstream": upstream_hashes,
            "versions": self.versions,
        }
        return checkpoint.compute_stage_hash(payload)

    def run_stage(self, spec, fn):
        """Execute a ledgered stage with reuse logic.

        Parameters
        ----------
        spec : StageSpec
        fn : callable
            ``fn(io: StepIO) -> Outcome``.

        Returns
        -------
        Outcome
        """
        label = spec.label
        self._track(label)
        self.dag_order.append(label)

        h = self.stage_hash(spec)
        latest = checkpoint.latest_completion(self.history, label)

        # Five rerun triggers
        rerun = (
            latest is None
            or latest.stage_hash != h
            or any(
                not os.path.exists(os.path.join(self.out_dir, o.path))
                for o in latest.outputs
            )
            or any(u in self.executed for u in spec.upstream)
            or bool(latest.qc.get("failed_runs"))
        )

        if not rerun:
            # Reuse
            self.stage_hashes[label] = h
            self.reused.append(label)
            self.stage_outputs[label] = latest.outputs
            if latest.qc:
                self.fragments.append((label, latest.qc))
            for w in latest.warnings:
                reemit_warning(w, self.logger, f"[reused stage {label}]")
            self.logger.info("Reusing stage %s", label)
            return Outcome(reused=True, qc=latest.qc)

        # Execute
        staging = os.path.join(self.out_dir, names.staging_dir(self.pre, label))
        if os.path.exists(staging):
            shutil.rmtree(staging)
        os.makedirs(staging)

        io = StepIO(label=label, staging=staging, out_dir=self.out_dir, pre=self.pre)
        n0 = warning_count()
        t0 = time.time()
        outcome = fn(io)
        elapsed = time.time() - t0
        stage_warnings = get_warnings()[n0:]

        # Validate
        for out in outcome.outputs:
            self._validate(io, out)

        # Staged record
        staged = checkpoint.StagedRecord(
            step=label,
            outputs=[checkpoint.OutputRecord(o.relpath, o.cls) for o in outcome.outputs],
            timestamp_utc=checkpoint.utc_now(),
        )
        checkpoint.append_record(self.ledger_path, staged)
        self.new_records.append(staged)

        # Promote
        self._promote(io, outcome.outputs)

        # Completion record
        completion = checkpoint.CompletionRecord(
            step=label,
            stage_hash=h,
            outputs=[checkpoint.OutputRecord(o.relpath, o.cls) for o in outcome.outputs],
            qc=outcome.qc,
            warnings=[
                {"code": w["code"], "severity": w["severity"],
                 "message": w["message"], "user_facing": w["user_facing"]}
                for w in stage_warnings
            ],
            versions=self.versions,
            timestamp_utc=checkpoint.utc_now(),
            wall_clock_s=elapsed,
        )
        checkpoint.append_record(self.ledger_path, completion)

        shutil.rmtree(staging, ignore_errors=True)

        self.stage_hashes[label] = h
        self.executed.append(label)
        self.stage_outputs[label] = [
            checkpoint.OutputRecord(o.relpath, o.cls) for o in outcome.outputs
        ]
        if outcome.qc:
            self.fragments.append((label, outcome.qc))

        return outcome

    def _track(self, label):
        if self.tracker is not None:
            self.tracker.step = label

    def record_stage_failure(self, label, qc_fragment):
        """Record a stage failure (e.g. rest per-run RUN_FAILED).

        The label is not added to stage_hashes (downstream stages must not
        declare it upstream). Pipelines route around failed stages via S_final.
        """
        self.failed[label] = qc_fragment
        self.fragments.append((label, qc_fragment))

    # ---- End-of-run ----

    def finish(self, *, expected, qc_step_fragment):
        """Run the end-of-run sequence and return FirstLevelResult.

        Parameters
        ----------
        expected : set of str
            Expected output relpaths (for cross-check).
        qc_step_fragment : callable
            ``qc_step_fragment(retired: list[str]) -> dict`` returning the
            {type}-qc fragment.

        Returns
        -------
        FirstLevelResult
        """
        # (1) Assemble listed outputs
        listed = {}  # relpath -> cls
        for label in self.dag_order:
            if label in self.failed:
                continue
            if label in self.stage_outputs:
                for out in self.stage_outputs[label]:
                    if out.path in listed:
                        raise GuardError(
                            f"Output '{out.path}' listed by both stages; "
                            f"refusing to continue."
                        )
                    listed[out.path] = out.cls
        for label, outs in self.step_outputs.items():
            for out in outs:
                if out.relpath in listed:
                    raise GuardError(
                        f"Output '{out.relpath}' listed by both steps/stages; "
                        f"refusing to continue."
                    )
                listed[out.relpath] = out.cls

        # Add ledger and qc_summary
        ledger_rel = names.ledger(self.pre)
        listed[ledger_rel] = "intermediate"
        qc_rel = names.qc_summary(self.pre)
        listed[qc_rel] = "final"

        # Verify all listed files except qc_summary exist
        for rel, cls in listed.items():
            if rel == qc_rel:
                continue
            full = os.path.join(self.out_dir, rel)
            if not os.path.exists(full):
                raise GuardError(
                    f"Listed output '{rel}' does not exist on disk."
                )

        # (2) Cross-check expected paths
        for rel in expected:
            full = os.path.join(self.out_dir, rel)
            if os.path.exists(full) and rel not in listed:
                raise GuardError(
                    f"Expected output '{rel}' exists but is not listed; "
                    f"refusing to retire anything."
                )

        # (3) Retirement sweep
        hist = checkpoint.read_history(self.ledger_path)
        recorded = checkpoint.recorded_paths(hist)
        frozen = names.frozen_names(self.analysis_type, self.pre)
        candidates = recorded - set(listed.keys()) - expected - frozen
        retired = []
        for rel in sorted(candidates):
            full = os.path.join(self.out_dir, rel)
            if os.path.lexists(full):
                try:
                    os.remove(full)
                    # Remove empty parent dirs
                    parent = os.path.dirname(full)
                    while parent != self.out_dir and parent:
                        try:
                            os.rmdir(parent)
                            parent = os.path.dirname(parent)
                        except OSError:
                            break
                    self.logger.info("Retired %s", rel)
                    retired.append(rel)
                except OSError as e:
                    graded_warning(
                        self.logger, "high", "RETIREMENT_FAILED",
                        f"Could not delete {rel}: {e}; retried next run.",
                        user_facing=True,
                    )

        if retired:
            checkpoint.append_record(
                self.ledger_path,
                checkpoint.RetiredRecord(
                    paths=retired,
                    timestamp_utc=checkpoint.utc_now(),
                ),
            )

        # (4) QC step
        frag = dict(qc_step_fragment(retired))
        status = "warning" if any(
            w["severity"] == "high" for w in get_warnings()
        ) else "success"
        frag["run_status"] = {"status": status, "error": None}
        merged = qc.merge_fragments(
            self.fragments + [(f"{self.type_label}-qc", frag)],
            self.analysis_type,
        )
        text = qc.qc_json_text(merged)

        def _write_qc(io):
            qc_path = io.path(qc_rel)
            with open(qc_path, "w", newline="") as f:
                f.write(text)
            return Outcome(
                outputs=[Output(
                    qc_rel, "final", "py_text",
                    producer="qc_summary writer",
                    expected_text=text,
                )],
            )

        self.run_step(f"{self.type_label}-qc", _write_qc)

        # (5) Build result
        output_files = sorted(
            os.path.join(self.out_dir, rel)
            for rel, cls in listed.items()
            if cls == "final"
        )
        intermediate_files = sorted(
            os.path.join(self.out_dir, rel)
            for rel, cls in listed.items()
            if cls == "intermediate"
        )

        return FirstLevelResult(
            status=status,
            output_dir=Path(self.out_dir),
            warnings=get_warnings(),
            qc_summary=merged,
            output_files=output_files,
            intermediate_files=intermediate_files,
        )


# ---------------------------------------------------------------------------
# Run status (success and failure records in qc_summary)
# ---------------------------------------------------------------------------

def write_failure_qc(out_dir, pre, analysis_type, exc, step, versions, logger):
    """Write a failure qc_summary: analysis_type, run_status and provenance only.

    Written only when out_dir exists, pre is a valid output prefix and
    analysis_type is known; partial QC metrics are never written. Errors
    while writing are logged and do not replace the original exception.
    """
    from .first_level_config import FILENAME_TOKEN_RE, VALID_TYPES

    if (not isinstance(out_dir, str) or not os.path.isdir(out_dir)
            or not isinstance(pre, str) or not FILENAME_TOKEN_RE.match(pre)
            or analysis_type not in VALID_TYPES):
        return
    frag = {
        "analysis_type": analysis_type,
        "run_status": {
            "status": "failed",
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "exit_code": exit_code(exc),
                "step": step,
            },
        },
    }
    if versions is not None:
        frag["provenance"] = versions
    try:
        merged = qc.merge_fragments([(f"{names.TYPE_LABEL[analysis_type]}-qc", frag)],
                                    analysis_type)
        dst = os.path.join(out_dir, names.qc_summary(pre))
        tmp = dst + ".tmp"
        with open(tmp, "w", newline="") as f:
            f.write(qc.qc_json_text(merged))
        os.replace(tmp, dst)
    except OSError as e:
        logger.error("Could not write failure qc_summary for '%s': %s", pre, e)


def run_with_status(analysis_type, config, logger, body):
    """Run a pipeline body, recording a failure in qc_summary before re-raising.

    Parameters
    ----------
    analysis_type : str
    config : ResolvedConfig
    logger : logging.Logger
    body : callable
        ``body(config, logger, tracker) -> FirstLevelResult``.

    Returns
    -------
    FirstLevelResult
    """
    tracker = RunTracker()
    try:
        return body(config, logger, tracker)
    except Exception as exc:
        write_failure_qc(config.out_dir, config.out_file_pre, analysis_type, exc,
                         tracker.step, tracker.versions, logger)
        raise
