"""Run identity and run-set state management.

Defines four run sets:

- **K_supplied** (``supplied``): all runs the user provides, in acquisition
  order. Run identity is an integer label, never a list position.
- **S_pre**: supplied runs minus pre-model exclusions (insufficient
  uncensored TRs or DOF < 1). Set once by set_s_pre.
- **K_model** (``len(s_pre)``): number of model runs.
- **S_final**: S_pre minus runs that failed during model estimation (rest
  run_failed). Set once by set_s_final.

Only ``set_s_pre`` and ``set_s_final`` assign the two mutable sets (single
source). Reading ``s_pre`` or ``s_final`` before they are set raises
GuardError.
"""

import dataclasses

import numpy as np

from .exceptions import GuardError, InputError
from .first_level_utils import run_afni_command, load_numeric_table


@dataclasses.dataclass(frozen=True)
class RunInfo:
    """Identity and volume geometry for one run.

    Attributes
    ----------
    label : int
        Integer run label (user-supplied or BIDS-derived).
    position : int
        0-based acquisition order among supplied runs.
    n_vols : int
        Number of volumes in this run.
    source_path : str
        Absolute path to the source NIfTI.
    start : int
        First volume index in source_path (0 for Mode A / rest).
    whole_file : bool
        True when source_path holds exactly this run's volumes (task Mode A
        and rest); False for task Mode B, where source_path is the
        concatenation of all runs.
    """
    label: int
    position: int
    n_vols: int
    source_path: str
    start: int
    whole_file: bool

    @property
    def spec(self) -> str:
        """AFNI input specification for this run's volumes only.

        The bare path when the file is this run alone; otherwise an explicit
        sub-brick selector, including for a Mode B run that starts at volume 0.
        """
        if self.whole_file:
            return self.source_path
        return f"{self.source_path}[{self.start}..{self.start + self.n_vols - 1}]"


class RunSets:
    """Run-set state container.

    Parameters
    ----------
    runs : list of RunInfo
        All supplied runs in acquisition order.
    input_mode : str
        ``'A'`` (per-run files) or ``'B'`` (single concatenated file).
    tr : float
        Repetition time in seconds.
    grid_ref : str
        Path to the reference scan for grid checks.
    """

    def __init__(self, runs, input_mode, tr, grid_ref):
        self._runs = {r.label: r for r in runs}
        self._ordered = tuple(r.label for r in runs)
        self._input_mode = input_mode
        self._tr = tr
        self.grid_ref = grid_ref
        self._s_pre = None
        self._s_final = None

    # ---- Supplied ----

    @property
    def supplied(self):
        """Labels in acquisition order."""
        return self._ordered

    @property
    def k_supplied(self):
        """Number of supplied runs."""
        return len(self._ordered)

    # ---- S_pre ----

    @property
    def s_pre(self):
        """Labels of runs entering the model (supplied minus pre-model exclusions)."""
        if self._s_pre is None:
            raise GuardError("s_pre has not been set yet.")
        return self._s_pre

    def set_s_pre(self, labels):
        """Set S_pre. Must be a subsequence of supplied in acquisition order."""
        if self._s_pre is not None:
            raise GuardError("s_pre has already been set.")
        labels = tuple(labels)
        # Validate subsequence
        it = iter(self._ordered)
        for lbl in labels:
            if lbl not in self._runs:
                raise GuardError(
                    f"Label {lbl} in s_pre is not a supplied run."
                )
            found = False
            for o in it:
                if o == lbl:
                    found = True
                    break
            if not found:
                raise GuardError(
                    f"Labels {labels} are not a subsequence of supplied "
                    f"runs {self._ordered} in acquisition order."
                )
        self._s_pre = labels

    @property
    def k_model(self):
        """Number of runs in S_pre."""
        return len(self.s_pre)

    # ---- S_final ----

    @property
    def s_final(self):
        """Labels of S_pre runs that completed model estimation."""
        if self._s_final is None:
            raise GuardError("s_final has not been set yet.")
        return self._s_final

    def set_s_final(self, labels):
        """Set S_final. Must be a subsequence of S_pre."""
        if self._s_final is not None:
            raise GuardError("s_final has already been set.")
        _ = self.s_pre  # ensure s_pre is set
        labels = tuple(labels)
        it = iter(self._s_pre)
        for lbl in labels:
            if lbl not in self._runs:
                raise GuardError(
                    f"Label {lbl} in s_final is not a supplied run."
                )
            found = False
            for o in it:
                if o == lbl:
                    found = True
                    break
            if not found:
                raise GuardError(
                    f"Labels {labels} are not a subsequence of s_pre "
                    f"{self._s_pre}."
                )
        self._s_final = labels

    # ---- Lookups ----

    @property
    def input_mode(self):
        """``'A'`` (per-run files) or ``'B'`` (single concatenated file)."""
        return self._input_mode

    @property
    def tr(self):
        """Repetition time in seconds."""
        return self._tr

    def run(self, label):
        """Return RunInfo for a single label."""
        return self._runs[label]

    def runs(self, labels):
        """Return a list of RunInfo for the given labels (acquisition order)."""
        return [self._runs[lbl] for lbl in labels]

    def run_lengths(self, labels):
        """Return n_vols for each label in order."""
        return [self._runs[lbl].n_vols for lbl in labels]

    def total_vols(self, labels):
        """Return the total number of volumes across labels."""
        return sum(self.run_lengths(labels))

    def offsets(self, labels):
        """Return a dict mapping each label to its cumulative start offset."""
        result = {}
        pos = 0
        for lbl in labels:
            result[lbl] = pos
            pos += self._runs[lbl].n_vols
        return result

    def run_starts(self, labels):
        """Return the list of start offsets in order."""
        offs = self.offsets(labels)
        return [offs[lbl] for lbl in labels]

    def mode_b_selector(self, labels):
        """Return an AFNI sub-brick selector for Mode B covering *labels*."""
        if self._input_mode != "B":
            raise GuardError("mode_b_selector is only valid for Mode B.")
        labels = list(labels)
        ranges = []
        for lbl in labels:
            r = self._runs[lbl]
            ranges.append(f"{r.start}..{r.start + r.n_vols - 1}")
        source = self._runs[labels[0]].source_path
        return f"{source}[{','.join(ranges)}]"

    def d_max_seconds(self):
        """Return max(n_vols over supplied) * tr."""
        return max(r.n_vols for r in self._runs.values()) * self._tr


def build_runsets(config, analysis_type, logger):
    """Construct RunSets from config and validate run structure (run-consistency checks).

    This is an always-run, non-writing step that runs before the engine
    context is created.

    Parameters
    ----------
    config : ResolvedConfig
    analysis_type : str
    logger : logging.Logger

    Returns
    -------
    RunSets
    """
    labels = list(config.run_labels)
    tr = config.tr
    runs = []

    is_task = analysis_type in ("task_act", "task_conn")

    if is_task and config.scan_paths is not None:
        # Task Mode A
        input_mode = "A"
        for i, lbl in enumerate(labels):
            path = config.scan_paths[i]
            nv = _nv(path, logger)
            runs.append(RunInfo(label=lbl, position=i, n_vols=nv,
                                source_path=path, start=0, whole_file=True))
    elif is_task:
        # Task Mode B
        input_mode = "B"
        path = config.scan_path
        total_file_vols = _nv(path, logger)
        if sum(config.run_lengths) != total_file_vols:
            raise InputError(
                f"run_lengths sum to {sum(config.run_lengths)} but "
                f"'{path}' has {total_file_vols} volumes."
            )
        offset = 0
        for i, lbl in enumerate(labels):
            nv = config.run_lengths[i]
            runs.append(RunInfo(label=lbl, position=i, n_vols=nv,
                                source_path=path, start=offset, whole_file=False))
            offset += nv
    else:
        # rest_conn: always Mode A
        input_mode = "A"
        for i, lbl in enumerate(labels):
            path = config.scan_paths[i]
            nv = _nv(path, logger)
            runs.append(RunInfo(label=lbl, position=i, n_vols=nv,
                                source_path=path, start=0, whole_file=True))

    grid_ref = runs[0].source_path
    rs = RunSets(runs, input_mode, tr, grid_ref)

    # Run-consistency checks
    _run_consistency_checks(rs, config, analysis_type, logger)

    return rs


def _nv(path, logger):
    """Return the number of volumes (3dinfo -nv) of a NIfTI file."""
    out = run_afni_command(
        ["3dinfo", "-nv", path],
        capture_output=True,
        description=f"3dinfo -nv {path}",
        logger=logger,
    )
    return int(out.strip())


def _check_header_tr(path, config_tr, logger):
    """Raise InputError if the NIfTI header TR differs from the configured tr.

    3dDeconvolve and 3dLSS place stimulus times using the dataset header TR,
    while the package's event, censoring, estimability and filtering steps
    use the configured tr, so the two must agree.
    """
    out = run_afni_command(
        ["3dinfo", "-tr", path],
        capture_output=True,
        description=f"3dinfo -tr {path}",
        logger=logger,
    )
    header_tr = float(out.strip())
    if abs(header_tr - float(config_tr)) > 1e-4:
        raise InputError(
            f"TR mismatch: '{path}' header TR is {header_tr} s but the configured "
            f"tr is {config_tr} s. Correct tr in the config or fix the header "
            "with 3drefit -TR."
        )


def _motion_columns(config, analysis_type):
    """Return the number of motion columns the model uses."""
    if analysis_type == "rest_conn":
        return 6 * config.motion_deriv_degree
    return 12 if config.include_motion_derivs else 6


def _check_motion_table(m, path, use_cols):
    """InputError when a motion table has too few columns or non-finite values."""
    if m.shape[1] < use_cols:
        raise InputError(
            f"Motion file '{path}' has {m.shape[1]} columns, expected >= {use_cols}."
        )
    _check_finite(m[:, :use_cols], path, "motion")


def _check_finite(values, path, what):
    """InputError naming the first rows of *values* that contain NaN or inf."""
    bad = np.flatnonzero(~np.isfinite(values).all(axis=1) if values.ndim > 1
                         else ~np.isfinite(values))
    if bad.size:
        rows = [int(i) + 1 for i in bad[:5]]
        raise InputError(
            f"{what.capitalize()} file '{path}' contains non-finite values (NaN or inf) "
            f"in rows {rows}{' and more' if bad.size > 5 else ''}."
        )


def _run_consistency_checks(rs, config, analysis_type, logger):
    """Run run-consistency validation checks.

    Covers motion and tissue row counts, motion column counts, finite motion
    and tissue values (first tissue column), header TR and grid identity.
    """
    is_rest = analysis_type == "rest_conn"
    is_task = analysis_type in ("task_act", "task_conn")
    use_cols = _motion_columns(config, analysis_type)

    if rs.input_mode == "A" or is_rest:
        # Per-run checks
        for lbl in rs.supplied:
            ri = rs.run(lbl)
            pos = ri.position

            # Motion rows == n_vols
            motion = config.motion_paths[pos]
            m = load_numeric_table(motion, "motion")
            if m.shape[0] != ri.n_vols:
                raise InputError(
                    f"Motion file '{motion}' has {m.shape[0]} rows but "
                    f"run {lbl} has {ri.n_vols} volumes."
                )
            _check_motion_table(m, motion, use_cols)

            # Tissue rows
            for tissue_list, name in [
                (getattr(config, "CSF_paths", None), "CSF"),
                (getattr(config, "WM_paths", None), "WM"),
                (getattr(config, "GS_paths", None) if is_rest else None, "GS"),
            ]:
                if tissue_list is not None and pos < len(tissue_list) and tissue_list[pos] is not None:
                    t = load_numeric_table(tissue_list[pos], name)
                    if t.shape[0] != ri.n_vols:
                        raise InputError(
                            f"{name} file '{tissue_list[pos]}' has {t.shape[0]} rows but "
                            f"run {lbl} has {ri.n_vols} volumes."
                        )
                    _check_finite(t[:, 0], tissue_list[pos], name)

            # TR check (per-run, against the configured tr)
            _check_header_tr(ri.source_path, config.tr, logger)

            # Grid check (per-run, against first scan)
            if pos > 0:
                grid_out = run_afni_command(
                    ["3dinfo", "-same_grid", rs.grid_ref, ri.source_path],
                    capture_output=True,
                    description=f"3dinfo -same_grid {ri.source_path}",
                    logger=logger,
                )
                if grid_out.strip().split()[0] != "1":
                    raise InputError(
                        f"Grid mismatch: run {lbl} ({ri.source_path}) has a "
                        f"different grid than the first run ({rs.grid_ref})."
                    )

    elif rs.input_mode == "B":
        # Mode B: header TR of the concatenated file against the configured tr
        _check_header_tr(config.scan_path, config.tr, logger)

        # Mode B: motion and tissue rows == total volumes
        total = rs.total_vols(rs.supplied)
        if is_task:
            m = load_numeric_table(config.motion_path, "motion")
            if m.shape[0] != total:
                raise InputError(
                    f"Motion file '{config.motion_path}' has {m.shape[0]} rows but "
                    f"total run volumes = {total}."
                )
            _check_motion_table(m, config.motion_path, use_cols)
            for path_attr, name in [("CSF_path", "CSF"), ("WM_path", "WM")]:
                path = getattr(config, path_attr, None)
                if path is not None:
                    t = load_numeric_table(path, name)
                    if t.shape[0] != total:
                        raise InputError(
                            f"{name} file '{path}' has {t.shape[0]} rows but "
                            f"total run volumes = {total}."
                        )
                    _check_finite(t[:, 0], path, name)
