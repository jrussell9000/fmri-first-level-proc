"""Read-only input checks for --dry-run.

Applies the same validators a run applies before its first step: run-set
construction (volume counts, header TR, grids, motion and tissue rows,
motion columns, finite motion and tissue values), the rest_conn path-list
guard, events parsing with onset validation and duplicate-trial detection,
and template properties. Nothing is written.
"""

from . import events, roi
from .exceptions import ConfigError, InputError
from .runsets import build_runsets


def _template_use(config):
    """Return (template_used, conn_types) with the same rules as each pipeline."""
    conn_types = set()
    if config.analysis_type == "task_act":
        used = bool(
            (config.stat_buckets and config.extract_out_file_pre)
            or config.extract_resids or config.extract_raw_ptseries
        )
        conn_types.add("extract")
    elif config.analysis_type == "task_conn":
        used = bool(
            (config.extract_pbseries and config.extract_out_file_pre)
            or config.extract_raw_ptseries or config.calc_conn is not None
        )
        if config.extract_pbseries or config.extract_raw_ptseries:
            conn_types.add("extract")
        if config.calc_conn:
            conn_types.add(config.calc_conn)
    else:
        used = bool(
            config.extract_ptseries or config.extract_raw_ptseries
            or config.calc_conn is not None
        )
        if config.extract_ptseries or config.extract_raw_ptseries:
            conn_types.add("extract")
        if config.calc_conn:
            conn_types.add(config.calc_conn)
    return config.template_path is not None and used, conn_types


def check_inputs(config, logger):
    """Validate one resolved analysis block's inputs without writing anything.

    Parameters
    ----------
    config : ResolvedConfig
    logger : logging.Logger

    Raises
    ------
    ConfigError, InputError, ToolExecutionError
        The same errors a run raises for these inputs.
    """
    if config.analysis_type == "rest_conn":
        n_runs = len(config.scan_paths)
        for name_, lst in [("motion_paths", config.motion_paths),
                           ("CSF_paths", config.CSF_paths),
                           ("WM_paths", config.WM_paths),
                           ("GS_paths", config.GS_paths)]:
            if lst is not None and len(lst) != n_runs:
                raise ConfigError(
                    f"{name_} has {len(lst)} entries but scan_paths has {n_runs}."
                )

    runsets = build_runsets(config, config.analysis_type, logger)

    if config.analysis_type in ("task_act", "task_conn"):
        required = (config.cond_labels if config.analysis_type == "task_act"
                    else config.cond_beta_labels)
        _, check = events.build_event_table(config, runsets, required)
        if check.violations:
            record = events.timing_record(config.analysis_type, runsets.input_mode,
                                          config.tr, check)
            raise InputError(
                events.timing_error_message(record, "(not written in --dry-run)"),
                context=record,
            )

    used, conn_types = _template_use(config)
    if used:
        roi.check_template(config.template_path, runsets.grid_ref,
                           config.force_diff_atlas, conn_types, logger)
