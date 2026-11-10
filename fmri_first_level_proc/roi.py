"""Parcel aggregation, template management and ROI-level QC.

Provides:

- ``extract_roi_stats``: parcellated time-series extraction via 3dROIstats
  with roi_zero_handling (exclude or include).
- ``check_template``, ``resample_template``: template validation and resampling.
- ``count_nonzero_by_roi``, ``median_by_roi``: voxel-count and
  summary-statistic helpers.
- ``nonconstant_mask``: per-run non-constant voxel mask via 3dTstat min/max.
- ``roi_qc``: ROI coverage and low-baseline QC records.

Definitions:

- **masked voxels**: voxels where max != min across the run (non-constant).
- **brain-mask median**: median across masked voxels of the temporal-mean volume
  (nonzero_only=False, i.e. includes zeros within the mask).
- **20% reporting convention**: low-baseline fraction counts voxels whose
  temporal mean is below 0.2 x the brain-mask median.
- **assumption**: input scans are brain-masked (non-brain voxels are zero or
  constant).
"""

import re

import numpy as np
import pandas as pd

from . import names
from .engine import Output, Outcome, StageSpec
from .exceptions import ConfigError, InputError, ToolExecutionError
from .first_level_utils import run_afni_command, get_3dinfo_properties


# ---------------------------------------------------------------------------
# 3dROIstats parsing
# ---------------------------------------------------------------------------

def _parse_roistats(stdout, column_regex, description):
    """Parse 3dROIstats -1Dformat output into a DataFrame.

    Parameters
    ----------
    stdout : str
        Captured stdout from 3dROIstats.
    column_regex : str
        Regex with one capture group for the ROI label (e.g. ``r'^NZMean_(\\d+)$'``).
    description : str
        Description for error messages.

    Returns
    -------
    pd.DataFrame
        Columns named ``ROI_{label}`` in label order; rows = sub-bricks.
    """
    lines = stdout.split("\n")
    # 3dROIstats -1Dformat output: line 0 is the "#File" title; line 1 is the
    # indented column-name line ("\t\t#\tNZMean_1...", not "#" at position 0);
    # the remaining lines alternate a "#"-prefixed row-identifier line
    # (skipped) and a data line.
    if len(lines) < 2:
        raise ToolExecutionError(
            f"3dROIstats output for {description}: expected at least 2 lines, "
            f"found {len(lines)}"
        )
    header_line = lines[1].strip()
    if header_line.startswith("#"):
        header_line = header_line[1:]
    header_tokens = [t.strip() for t in header_line.split("\t")]
    header_tokens = [t for t in header_tokens if t != ""]

    # Match column regex
    pat = re.compile(column_regex)
    col_map = {}  # position -> ROI label (int)
    for i, token in enumerate(header_tokens):
        m = pat.match(token)
        if m:
            col_map[i] = int(m.group(1))

    # Data lines: every line after the header block that does not start
    # with '#' (the per-row identifier lines are skipped).
    data_lines = [l for l in lines[2:] if l.strip() and not l.startswith("#")]

    if not col_map:
        if not data_lines:
            # AFNI legitimately emits an empty column header and no data
            # lines when the mask has zero voxels matching any ROI label
            # (e.g. an all-zero indicator mask). This is not a parse error.
            return pd.DataFrame()
        raise ToolExecutionError(
            f"3dROIstats output for {description}: no columns matched "
            f"pattern {column_regex}. Header: {header_tokens}"
        )

    rows = []
    for dl in data_lines:
        tokens = [t.strip() for t in dl.strip().split("\t")]
        row = {}
        for pos, label in col_map.items():
            if pos < len(tokens):
                try:
                    row[f"ROI_{label}"] = float(tokens[pos])
                except ValueError:
                    row[f"ROI_{label}"] = np.nan
        rows.append(row)

    if not rows:
        raise ToolExecutionError(
            f"3dROIstats output for {description}: no data rows found."
        )

    # Sort columns by label
    sorted_labels = sorted(col_map.values())
    col_order = [f"ROI_{lbl}" for lbl in sorted_labels]
    df = pd.DataFrame(rows, columns=col_order)
    return df


# ---------------------------------------------------------------------------
# Public ROI functions
# ---------------------------------------------------------------------------

def extract_roi_stats(input_spec, template_path, average_type,
                      roi_zero_handling, logger, cwd=None):
    """Extract parcellated statistics from a NIfTI file via 3dROIstats.

    Parameters
    ----------
    input_spec : str
        Input NIfTI (or AFNI sub-brick selector).
    template_path : str
        Path to the ROI template.
    average_type : str
        ``'mean'`` or ``'median'``.
    roi_zero_handling : str
        ``'exclude'`` (use -nz prefix) or ``'include'``.
    logger : logging.Logger
    cwd : str or None

    Returns
    -------
    pd.DataFrame
        Rows = sub-bricks, columns = ROI_{label}.
    """
    if roi_zero_handling == "exclude":
        if average_type == "mean":
            cmd = ["3dROIstats", "-nzmean", "-nomeanout", "-1Dformat",
                   "-mask", template_path, input_spec]
            regex = r"^NZMean_(\d+)$"
        else:
            cmd = ["3dROIstats", "-nzmedian", "-nomeanout", "-1Dformat",
                   "-mask", template_path, input_spec]
            regex = r"^NZMed_(\d+)$"
    else:
        if average_type == "mean":
            cmd = ["3dROIstats", "-1Dformat",
                   "-mask", template_path, input_spec]
            regex = r"^Mean_(\d+)$"
        else:
            cmd = ["3dROIstats", "-median", "-nomeanout", "-1Dformat",
                   "-mask", template_path, input_spec]
            regex = r"^Med_(\d+)\s*$"

    stdout = run_afni_command(
        cmd, capture_output=True,
        description=f"3dROIstats {average_type} {roi_zero_handling}",
        logger=logger, cwd=cwd,
    )
    return _parse_roistats(stdout, regex, f"{average_type} {roi_zero_handling}")


def count_nonzero_by_roi(mask_spec, data_spec, logger, cwd=None):
    """Count nonzero voxels per ROI via 3dROIstats -nzvoxels.

    Returns
    -------
    dict[int, int]
        ROI label -> count.
    """
    stdout = run_afni_command(
        ["3dROIstats", "-nomeanout", "-nzvoxels", "-1Dformat",
         "-mask", mask_spec, data_spec],
        capture_output=True,
        description="3dROIstats nzvoxels",
        logger=logger, cwd=cwd,
    )
    df = _parse_roistats(stdout, r"^NZcount_(\d+)$", "nzvoxels")
    result = {}
    for col in df.columns:
        label = int(col.replace("ROI_", ""))
        result[label] = int(df[col].iloc[0])
    return result


def median_by_roi(mask_spec, data_spec, nonzero_only, logger, cwd=None):
    """Compute median per ROI via 3dROIstats.

    Returns
    -------
    dict[int, float]
        ROI label -> median.
    """
    if nonzero_only:
        cmd = ["3dROIstats", "-nomeanout", "-nzmedian", "-1Dformat",
               "-mask", mask_spec, data_spec]
        regex = r"^NZMed_(\d+)$"
    else:
        cmd = ["3dROIstats", "-nomeanout", "-median", "-1Dformat",
               "-mask", mask_spec, data_spec]
        regex = r"^Med_(\d+)\s*$"

    stdout = run_afni_command(
        cmd, capture_output=True,
        description="3dROIstats median",
        logger=logger, cwd=cwd,
    )
    df = _parse_roistats(stdout, regex, "median")
    result = {}
    for col in df.columns:
        label = int(col.replace("ROI_", ""))
        result[label] = float(df[col].iloc[0])
    return result


# ---------------------------------------------------------------------------
# Template checks and resampling
# ---------------------------------------------------------------------------

def check_template(template_path, scan_ref, force_diff_atlas, conn_types, logger):
    """Validate template properties (always-run, non-writing).

    Parameters
    ----------
    template_path : str
    scan_ref : str
        Reference scan path for grid comparison.
    force_diff_atlas : bool
    conn_types : set of str
        Connectivity types that will use the template.
    logger : logging.Logger

    Returns
    -------
    bool
        True if template and scan are on the same grid.

    Raises
    ------
    InputError, ConfigError
    """
    props = get_3dinfo_properties(template_path, logger, keys=("space", "dmax"))
    if props.get("dmax") is None:
        raise InputError(
            f"Template '{template_path}': could not retrieve dmax via 3dinfo."
        )

    try:
        dmax = float(props["dmax"])
    except (ValueError, TypeError):
        raise InputError(
            f"Template '{template_path}': dmax '{props['dmax']}' is not numeric."
        )

    if dmax != int(dmax):
        raise InputError(
            f"Template '{template_path}': dmax {dmax} is not an integer "
            f"(template must contain integer ROI labels)."
        )

    if dmax == 0:
        raise InputError(
            f"Template '{template_path}': dmax is 0 (empty template)."
        )

    if "parcellated" in conn_types and dmax < 2:
        raise ConfigError(
            f"Template '{template_path}': parcellated connectivity requires "
            f"at least 2 ROIs (dmax={int(dmax)})."
        )

    if "seed_to_voxel" in conn_types and dmax > 1:
        raise ConfigError(
            f"Template '{template_path}': seed-to-voxel connectivity requires "
            f"a single-ROI mask (dmax={int(dmax)}). Use calc_conn='parcellated' "
            f"for multi-ROI templates."
        )

    # Atlas space check
    scan_props = get_3dinfo_properties(scan_ref, logger, keys=("space",))
    if props.get("space") and scan_props.get("space"):
        if props["space"] != scan_props["space"]:
            if force_diff_atlas:
                logger.warning(
                    "Template space '%s' differs from scan space '%s'; "
                    "force_diff_atlas=True overrides this check.",
                    props["space"], scan_props["space"],
                )
            else:
                raise InputError(
                    f"Template space '{props['space']}' differs from scan "
                    f"space '{scan_props['space']}'. Set force_diff_atlas=True "
                    f"to override (USE WITH CAUTION)."
                )

    # Grid check
    grid_out = run_afni_command(
        ["3dinfo", "-same_grid", scan_ref, template_path],
        capture_output=True,
        description="3dinfo -same_grid template",
        logger=logger,
    )
    return grid_out.strip().split()[0] == "1"


def resample_template(io, template_path, scan_ref, rel, logger):
    """Resample template to match scan grid.

    Returns
    -------
    Output
    """
    run_afni_command(
        ["3dresample", "-master", scan_ref, "-rmode", "NN", "-overwrite",
         "-input", template_path, "-prefix", io.path(rel)],
        description="3dresample template",
        logger=logger,
        cwd=io.staging,
    )
    return Output(rel, "intermediate", "nifti", producer="3dresample template")


def template_stage(ctx, config, runsets, pre, same_grid, analysis, logger):
    """Run the ledgered template-check stage shared by task_act, task_conn
    and rest_conn, and return the resolved template path.

    Resamples the template onto the scan grid when *same_grid* is false.

    Returns
    -------
    str
        config.template_path when same_grid, else the absolute resampled path.
    """
    scan_grid = " ".join(run_afni_command(
        ["3dinfo", "-n3", "-aform_real", runsets.grid_ref],
        capture_output=True, description="3dinfo scan grid", logger=logger,
    ).split())

    template_spec = StageSpec(
        label=f"{analysis}-template",
        fields=("template_path",),
        derived_files=(config.template_path,),
        derived_values={"same_grid": same_grid, "scan_grid": scan_grid},
        share_as="template",
    )

    def _template_stage(io):
        if not same_grid:
            out = resample_template(
                io, config.template_path, runsets.grid_ref,
                names.template_resampled(pre, config.template_path), logger,
            )
            return Outcome(outputs=[out])
        return Outcome(outputs=[])

    ctx.run_stage(template_spec, _template_stage)

    if not same_grid:
        return f"{config.out_dir}/{names.template_resampled(pre, config.template_path)}"
    return config.template_path


# ---------------------------------------------------------------------------
# Non-constant mask
# ---------------------------------------------------------------------------

def nonconstant_mask(io, run_spec, rel, logger):
    """Create a non-constant voxel mask (max != min) for a run.

    Returns
    -------
    str
        Absolute path to the mask file.
    """
    mm_path = io.path(rel + "_mm.nii")  # a temporary, so uncompressed
    run_afni_command(
        ["3dTstat", "-max", "-min", "-prefix", mm_path, run_spec],
        description="3dTstat max/min for nonconstant mask",
        logger=logger,
        cwd=io.staging,
    )
    mask_path = io.path(rel)
    run_afni_command(
        ["3dcalc", "-a", f"{mm_path}[0]", "-b", f"{mm_path}[1]",
         "-expr", "step(a-b)", "-prefix", mask_path],
        description="3dcalc nonconstant mask",
        logger=logger,
        cwd=io.staging,
    )
    return mask_path


def nonconstant_intersection(io, specs, rel, tag, logger):
    """Write the intersection of per-run non-constant masks to *rel* and
    return its absolute path. Each indicator is exactly 0 or 1
    (step(max - min)), so the voxelwise minimum is the intersection.
    """
    indicators = [nonconstant_mask(io, s, f"_{tag}_nc_{i}.nii", logger)
                  for i, s in enumerate(specs)]
    if len(indicators) == 1:
        run_afni_command(
            ["3dcalc", "-a", indicators[0], "-expr", "a", "-prefix", io.path(rel)],
            description="3dcalc nonconstant intersection (single run)",
            logger=logger, cwd=io.staging,
        )
    else:
        run_afni_command(
            ["3dMean", "-min", "-datum", "float", "-prefix", io.path(rel)] + indicators,
            description="3dMean nonconstant intersection",
            logger=logger, cwd=io.staging,
        )
    return io.path(rel)


# ---------------------------------------------------------------------------
# ROI QC
# ---------------------------------------------------------------------------

def roi_qc(io, config, runsets, labels, template_resolved, unscaled_spec,
           model_series_spec, mean_volume, logger):
    """Compute ROI coverage and low-baseline QC records.

    Parameters
    ----------
    io : StepIO
    config : ResolvedConfig
    runsets : RunSets
    labels : list of int
        Run labels to QC.
    template_resolved : str
        Path to the (possibly resampled) template.
    unscaled_spec : callable
        ``unscaled_spec(label) -> str`` returning the AFNI selector for the
        unscaled run.
    model_series_spec : callable
        ``model_series_spec(label) -> str`` returning the AFNI selector for
        the model series of a run.
    mean_volume : callable
        ``mean_volume(label) -> str or None`` returning the path to the
        pre-computed temporal mean, or None.
    logger : logging.Logger

    Returns
    -------
    dict
        ``{'roi_coverage': [...], 'low_baseline': [...]}``.
    """
    n_vox = count_nonzero_by_roi(template_resolved, template_resolved, logger)
    tlabels = sorted(n_vox)

    coverage_records = []
    lowbase_records = []

    for label_n in labels:
        # Non-constant mask. The _roiqc_ temporaries are uncompressed: gzip costs
        # a full compression to write and a full decompression on every read.
        m_rel = f"_roiqc_mask_run{label_n}.nii"
        mask_path = nonconstant_mask(io, unscaled_spec(label_n), m_rel, logger)

        # Mean volume
        mean_path = mean_volume(label_n)
        if mean_path is None:
            mean_rel = f"_roiqc_mean_run{label_n}.nii"
            run_afni_command(
                ["3dTstat", "-mean", "-prefix", io.path(mean_rel),
                 unscaled_spec(label_n)],
                description="3dTstat mean for roi_qc",
                logger=logger, cwd=io.staging,
            )
            mean_path = io.path(mean_rel)

        # Sentinel check: fraction of masked voxels with mean <= 0
        total_masked_counts = count_nonzero_by_roi(mask_path, mask_path, logger)
        total_masked = total_masked_counts.get(1, 0)

        np_rel = f"_roiqc_nonpos_run{label_n}.nii"
        run_afni_command(
            ["3dcalc", "-a", mask_path, "-b", mean_path,
             "-expr", "step(a)*not(ispositive(b))",
             "-prefix", io.path(np_rel)],
            description="3dcalc nonpositive indicator",
            logger=logger, cwd=io.staging,
        )
        nonpos_counts = count_nonzero_by_roi(
            io.path(np_rel), io.path(np_rel), logger
        )
        nonpos_count = nonpos_counts.get(1, 0)
        sentinel_fail = (
            total_masked > 0
            and nonpos_count / total_masked >= 0.25
        )

        # Brain-mask median
        med_dict = median_by_roi(mask_path, mean_path, False, logger)
        med = med_dict.get(1, 0.0)

        # ROI coverage
        absmax_rel = f"_roiqc_absmax_run{label_n}.nii"
        run_afni_command(
            ["3dTstat", "-absmax", "-prefix", io.path(absmax_rel),
             model_series_spec(label_n)],
            description="3dTstat absmax for roi_coverage",
            logger=logger, cwd=io.staging,
        )
        indicator_rel = f"_roiqc_indicator_run{label_n}.nii"
        run_afni_command(
            ["3dcalc", "-a", io.path(absmax_rel), "-expr", "step(a)",
             "-prefix", io.path(indicator_rel)],
            description="3dcalc roi coverage indicator",
            logger=logger, cwd=io.staging,
        )
        nz = count_nonzero_by_roi(
            template_resolved, io.path(indicator_rel), logger
        )
        for roi in tlabels:
            coverage_records.append({
                "run": label_n,
                "roi": roi,
                "n_voxels": n_vox.get(roi, 0),
                "nonzero_fraction": (
                    nz.get(roi, 0) / n_vox[roi] if n_vox.get(roi, 0) > 0 else 0.0
                ),
            })

        # Low baseline per ROI. The indicator and masked-mean volumes do not
        # depend on the ROI, and each 3dROIstats call reports every ROI, so
        # both are computed once per run and read per ROI below.
        masked_counts = count_nonzero_by_roi(template_resolved, mask_path, logger)
        low_counts = {}
        roi_med_dict = {}
        threshold = 0.2 * med
        if not sentinel_fail and any(masked_counts.get(r, 0) > 0 for r in tlabels):
            low_rel = f"_roiqc_low_run{label_n}.nii"
            run_afni_command(
                ["3dcalc", "-a", mask_path, "-b", mean_path,
                 "-expr", f"a*step({threshold}-b)",
                 "-prefix", io.path(low_rel)],
                description="3dcalc low baseline indicator",
                logger=logger, cwd=io.staging,
            )
            low_counts = count_nonzero_by_roi(
                template_resolved, io.path(low_rel), logger
            )
            v_rel = f"_roiqc_masked_mean_run{label_n}.nii"
            run_afni_command(
                ["3dcalc", "-a", mask_path, "-b", mean_path,
                 "-expr", "a*b", "-prefix", io.path(v_rel)],
                description="3dcalc masked mean",
                logger=logger, cwd=io.staging,
            )
            roi_med_dict = median_by_roi(
                template_resolved, io.path(v_rel), True, logger
            )

        for roi in tlabels:
            if sentinel_fail:
                lowbase_records.append({
                    "run": label_n,
                    "roi": roi,
                    "low_baseline_fraction": None,
                    "median_baseline_ratio": None,
                    "low_baseline_null_reason": "nonpositive_baseline",
                })
            elif masked_counts.get(roi, 0) == 0:
                lowbase_records.append({
                    "run": label_n,
                    "roi": roi,
                    "low_baseline_fraction": None,
                    "median_baseline_ratio": None,
                    "low_baseline_null_reason": "no_masked_voxels",
                })
            else:
                low_frac = low_counts.get(roi, 0) / masked_counts[roi]
                roi_med = roi_med_dict.get(roi)

                med_ratio = None
                med_null_reason = None
                if med <= 0:
                    med_null_reason = "nonpositive_baseline"
                elif roi_med is not None:
                    med_ratio = roi_med / med

                lowbase_records.append({
                    "run": label_n,
                    "roi": roi,
                    "low_baseline_fraction": low_frac,
                    "median_baseline_ratio": med_ratio,
                    "low_baseline_null_reason": med_null_reason,
                })

    return {"roi_coverage": coverage_records, "low_baseline": lowbase_records}


def task_roi_qc(io, config, runsets, s_pre, template_resolved, pre, logger):
    """ROI QC stage body shared by task_act and task_conn."""
    def unscaled_spec(lbl):
        return runsets.run(lbl).spec

    def model_series_spec(lbl):
        if config.scale_to_psc:
            return f"{config.out_dir}/{names.run_psc(pre, None if runsets.k_supplied == 1 else lbl)}"
        return runsets.run(lbl).spec

    def mean_volume(lbl):
        if config.scale_to_psc:
            return f"{config.out_dir}/{names.run_mean(pre, None if runsets.k_supplied == 1 else lbl)}"
        return None

    qc_frag = roi_qc(
        io, config, runsets, list(s_pre), template_resolved,
        unscaled_spec, model_series_spec, mean_volume, logger,
    )
    return Outcome(outputs=[], qc=qc_frag)
