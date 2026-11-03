"""In-process stand-in for the AFNI command-line tools used by the pipelines.

FakeAfni replaces ``run_afni_command`` in every module that imports it. Each
supported program writes the files the real tool would produce (NIfTI outputs
are placeholder bytes; 1D outputs are real numeric text in AFNI's transposed
orientation) and returns plausible stdout for query tools. Every call is
recorded so tests can assert on the command sequence.
"""

from pathlib import Path

import numpy as np

from fmri_first_level_proc import afni
from fmri_first_level_proc.exceptions import ToolExecutionError

# Modules that bind run_afni_command at import time and must all be patched.
PATCH_TARGETS = (
    "fmri_first_level_proc.afni",
    "fmri_first_level_proc.design",
    "fmri_first_level_proc.preprocessing",
    "fmri_first_level_proc.inputs",
    "fmri_first_level_proc.smoothing",
    "fmri_first_level_proc.templates",
    "fmri_first_level_proc.connectivity",
    "fmri_first_level_proc.pipelines.task_act",
    "fmri_first_level_proc.pipelines.task_conn",
    "fmri_first_level_proc.pipelines.rest_conn",
)

# Default 3dDeconvolve bucket layout reported by 3dinfo -label / -subbrick_info,
# as real 3dDeconvolve -fout -rout -tout writes it for two stimuli (AFNI 26.3.07).
DEFAULT_BUCKET_LABELS = [
    "Full_R^2", "Full_Fstat",
    "A#0_Coef", "A#0_Tstat", "A_R^2", "A_Fstat",
    "B#0_Coef", "B#0_Tstat", "B_R^2", "B_Fstat",
]

# statcode line 3dinfo -subbrick_info prints after a statistic sub-brick
_STATCODE = {"Tstat": "fitt;  statpar = 80", "Fstat": "fift;  statpar = 1 80", "R^2": "fibt;  statpar = 0.5 40"}


class FakeAfni:
    """Callable replacement for ``run_afni_command``.

    Parameters
    ----------
    n_trs : int
        Length of 3dToutcount output.
    n_rois : int
        ROI count reported by 3dROIstats and 3dinfo -dmax for parcellations.
    bucket_labels : list of str
        Sub-brick labels of the 3dDeconvolve bucket dataset.
    tr : float
        Header TR reported by 3dinfo -tr.
    nonzero_counts : dict of str to int
        3dBrickStat -count result by substring of the dataset name, added to
        the defaults: 0 voxels for the PSC QC masks, 1000 for anything else.
    fail_on : set of str
        Program names that raise ToolExecutionError instead of running.
    """

    def __init__(self, n_trs=100, n_rois=3, bucket_labels=None, fail_on=(), tr=2.0, nonzero_counts=None):
        self.tr = tr
        self.nonzero_counts = {"guarded": 0, "capped": 0, "nonpositive": 0, **(nonzero_counts or {})}
        self.n_trs = n_trs
        self.n_rois = n_rois
        self.bucket_labels = list(bucket_labels or DEFAULT_BUCKET_LABELS)
        self.fail_on = set(fail_on)
        self.calls: list[list[str]] = []
        self.budgets: list[int | None] = []  # OMP thread budget in effect for each call

    # -- public helpers ------------------------------------------------------

    def install(self, monkeypatch):
        for module in PATCH_TARGETS:
            monkeypatch.setattr(f"{module}.run_afni_command", self)
        return self

    def programs(self):
        """Program names in call order."""
        return [c[0] for c in self.calls]

    def calls_to(self, program):
        return [c for c in self.calls if c[0] == program]

    # -- dispatch ------------------------------------------------------------

    def __call__(self, command, capture_output=False, description="", logger=None):
        command = [str(c) for c in command]
        self.calls.append(command)
        self.budgets.append(afni._thread_budget.get())
        program = command[0]
        if program in self.fail_on:
            raise ToolExecutionError(f"fake failure: {' '.join(command)}")
        handlers = {
            "3dinfo": self._info,
            "3dToutcount": self._toutcount,
            "3dROIstats": self._roistats,
            "3dAttribute": self._attribute,
            "3dbucket": self._prefix_producer,
            "3dcalc": self._prefix_producer,
            "3dTstat": self._prefix_producer,
            "3dMean": self._prefix_producer,
            "3dBlurToFWHM": self._prefix_producer,
            "3dTcorr1D": self._prefix_producer,
            "3dFWHMx": self._fwhmx,
            "3dBrickStat": self._brickstat,
            "3dresample": self._prefix_producer,
            "3dTcat": self._prefix_producer,
            "3dLSS": self._prefix_producer,
            "3dTproject": self._tproject,
            "3dBandpass": self._bandpass,
            "3dDeconvolve": self._deconvolve,
            "3dNetCorr": self._netcorr,
            "1dtranspose": self._transpose,
        }
        if program not in handlers:
            raise NotImplementedError(f"FakeAfni has no handler for {program}")
        out = handlers[program](command)
        return (out or "") if capture_output else None

    # -- argument helpers ----------------------------------------------------

    @staticmethod
    def _opt(command, flag, default=None):
        return command[command.index(flag) + 1] if flag in command else default

    @staticmethod
    def _touch(path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"fake nifti")

    @staticmethod
    def _strip_selector(path):
        """Drop AFNI sub-brick selectors and the transpose quote from a dataset argument."""
        return path.split("[")[0].rstrip("'")

    def _write_transposed_1d(self, src, prefix):
        # Like AFNI, only a .1D path is read as 1D data (otherwise "Can't open dataset")
        if not self._strip_selector(src).endswith(".1D"):
            raise ToolExecutionError(f"fake 3d*: Can't open dataset '{src}'")
        # AFNI reads .1D as rows=voxels, cols=time; output is written in that orientation.
        data = np.loadtxt(self._strip_selector(src), ndmin=2)
        np.savetxt(prefix, data.T, fmt="%.6f")

    # -- query tools ---------------------------------------------------------

    def _info(self, command):
        flags = command[1:-1]
        if len(flags) > 1:
            # 3dinfo prints multiple requested values on one tab-separated line
            values = [self._info([command[0], flag, command[-1]]).strip() for flag in flags]
            return "\t".join(values) + "\n"
        target = self._strip_selector(command[-1])
        flag = flags[0]
        if flag == "-space":
            return "MNI\n"
        if flag == "-orient":
            return "RAI\n"
        if flag == "-ad3":
            return "2.000000\t2.000000\t2.000000\n"
        if flag == "-dmax":
            return "1\n" if "seed" in Path(target).name else f"{self.n_rois}\n"
        if flag == "-label":
            return "|".join(self.bucket_labels) + "\n"
        if flag == "-nt":
            return f"{self.n_trs}\n"
        if flag == "-tr":
            return f"{self.tr:.6f}\n"
        if flag == "-nijk":
            return "5000\n"
        if flag == "-subbrick_info":
            # Real format: labels are single-quoted; stat sub-bricks get a statcode line
            lines = ["++ 3dinfo: AFNI version=AFNI_26.3.07 (Oct 31 2026) [64-bit]"]
            for i, label in enumerate(self.bucket_labels):
                lines.append(f"  -- At sub-brick #{i} '{label}' datum type is float:   -1 to 1")
                stat = next((s for s in _STATCODE if label.endswith(s)), None)
                if stat:
                    lines.append(f"     statcode = {_STATCODE[stat]}")
            return "\n".join(lines) + "\n"
        raise NotImplementedError(f"3dinfo flag {flag}")

    def _fwhmx(self, command):
        # Real output: a line of classic FWHMs, then the ACF parameters and estimate
        return " 0  0  0    0\n 0.5  2.5  10    6.0\n"

    def _brickstat(self, command):
        name = Path(command[-1]).name
        count = next((n for key, n in self.nonzero_counts.items() if key in name), 1000)
        return f"{count}          \n"

    def _toutcount(self, command):
        fractions = np.linspace(0.2, 0.01, self.n_trs)
        return " ".join(f"{v:.4f}" for v in fractions) + "\n"

    def _roistats(self, command):
        # Real -1Dformat: a Mean_i column precedes each NZMean_i / NZMed_i column
        n = 1 if "seed" in Path(self._opt(command, "-mask")).name else self.n_rois
        stat = "NZMed" if "-nzmedian" in command else "NZMean" if "-nzmean" in command else None
        if stat is None:
            # Without a non-zero statistic, one column per ROI: -median after -nomeanout, else the mean
            stat = "Med" if "-median" in command else "Mean"
            header = "\t\t#\t" + "\t".join(f"{stat}_{i + 1}  " for i in range(n))
            row = "\t\t\t" + "\t".join(f"{0.1 * (i + 1):.6f}" for i in range(n))
            return f"#File\tSub-brick\n{header}\n#{command[-1]}\t0[?]\n{row}\n"
        header = "\t\t#\t" + "\t".join(f"Mean_{i + 1}  \t{stat}_{i + 1}" for i in range(n))
        row = "\t\t\t" + "\t".join(f"{0.2 * (i + 1):.6f}\t{0.1 * (i + 1):.6f}" for i in range(n))
        return f"#File\tSub-brick\n{header}\n#{command[-1]}\t0[?]\n{row}\n"

    def _attribute(self, command):
        # BRICK_STATAUX records: index, stat code (3 = Tstat), n params, params (DOF)
        return " ".join(f"{i} 3 1 80" for i, lbl in enumerate(self.bucket_labels) if lbl.endswith("Tstat")) + "\n"

    # -- dataset producers ---------------------------------------------------

    def _prefix_producer(self, command):
        self._touch(self._opt(command, "-prefix"))

    def _tproject(self, command):
        src, prefix = self._opt(command, "-input"), self._opt(command, "-prefix")
        if src.endswith("'"):
            self._write_transposed_1d(src, prefix)
        else:
            self._touch(prefix)

    def _bandpass(self, command):
        src, prefix = command[-1], self._opt(command, "-prefix")
        if src.endswith("'"):
            self._write_transposed_1d(src, prefix)
        else:
            self._touch(prefix)

    def _deconvolve(self, command):
        if "-nodata" in command:
            self._nodata_design(command)
            return
        for flag in ("-bucket", "-errts"):
            if flag in command:
                self._touch(self._opt(command, flag))
        if "-x1D" in command:
            self._lss_design(command)
        Path("3dDeconvolve.err").write_text("")

    def _lss_design(self, command):
        """Write a censored design matrix: 3 polynomials, the motion columns, and each stimulus."""
        n_rows = int(np.loadtxt(self._opt(command, "-censor")).sum())
        labels = ["Run#1Pol#0", "Run#1Pol#1", "Run#1Pol#2"]
        i = command.index("-ortvec")
        labels += [f"motion#{k}" for k in range(np.loadtxt(command[i + 1], ndmin=2).shape[1])]
        for i, flag in enumerate(command):
            if flag.startswith("-stim_times"):
                stim_label = command[command.index("-stim_label", i) + 2]
                n = len(Path(command[i + 2]).read_text().split()) if flag == "-stim_times_IM" else 1
                labels += [f"{stim_label}#{k}" for k in range(n)]
        row = " ".join("1" for _ in labels)
        body = "\n".join(row for _ in range(n_rows))
        Path(self._opt(command, "-x1D")).write_text(f'# ColumnLabels = "{" ; ".join(labels)}"\n{body}\n')

    def _nodata_design(self, command):
        """Write an IM design: each trial is one column, a 15 s response from its onset."""
        n_rows, tr = int(self._opt(command, "-nodata")), float(command[command.index("-nodata") + 2])
        columns, labels = [], []
        positions = [i for i, flag in enumerate(command) if flag == "-stim_times_IM"]
        for i in positions:
            onsets = [float(tok.split("*")[0]) for tok in Path(command[i + 2]).read_text().split()]
            stim_label = command[command.index("-stim_label", i) + 2]
            for j, onset in enumerate(onsets):
                t = np.arange(n_rows) * tr - onset
                columns.append(((t > 0) & (t <= 15)).astype(float))
                labels.append(f"{stim_label}#{j}")
        header = f'# ColumnLabels = "{" ; ".join(labels)}"\n'
        body = "\n".join(" ".join(f"{v:g}" for v in row) for row in np.column_stack(columns))
        Path(self._opt(command, "-x1D")).write_text(header + body + "\n")

    def _netcorr(self, command):
        prefix = self._opt(command, "-prefix")
        for ext in ("_000.niml.dset", "_000.roidat"):
            Path(prefix + ext).write_text("")
        n = self.n_rois
        eye = "\n".join("  " + "  ".join("1.000000" if i == j else "0.250000" for j in range(n)) for i in range(n))
        sections = ["CC"] + (["FZ"] if "-fish_z" in command else []) + (["PC", "PCB"] if "-part_corr" in command else [])
        body = "".join(f"# {name}\n{eye}\n" for name in sections)
        # Real header: ROI counts, WITH_ROI_LABELS, then label and index rows before the matrices
        labels = "  ".join(f"{i + 1:03d}" for i in range(n)) + "\n" + "  ".join(str(i + 1) for i in range(n))
        Path(prefix + "_000.netcc").write_text(
            f"# {n}  # Number of network ROIs\n# {len(sections)}  # Number of netcc matrices\n"
            f"# WITH_ROI_LABELS\n{labels}\n{body}"
        )
        if "-ts_wb_corr" in command:
            indiv = Path(prefix + "_000_INDIV")
            indiv.mkdir(exist_ok=True)
            self._touch(indiv / "WB_CORR_ROI_001.nii.gz")
            if "-ts_wb_Z" in command:
                self._touch(indiv / "WB_Z_ROI_001.nii.gz")

    # -- 1D tools ------------------------------------------------------------

    def _transpose(self, command):
        np.savetxt(command[2], np.loadtxt(command[1], ndmin=2).T, fmt="%.6f")
