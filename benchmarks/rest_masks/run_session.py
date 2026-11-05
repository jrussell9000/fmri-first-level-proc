"""Run one ABCD session's rest data through each mask arm and keep parcel time series.

Staging is shared, so arms differ only in their WM, CSF and global signal regressors. Each arm
otherwise uses the production rest block, through the production CLI. Runs from a table row, by
index, so subject IDs stay out of pod specs and logs.

    run_session.py --bucket B --sessions-key K --index I --output-prefix P --atlas A --workdir W
"""

import argparse
import copy
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd
import yaml

from fmri_first_level_proc.abcd import staging

TR = 0.8
SPACE_RES1 = "space-MNI152NLin2009cAsym_res-1"
# arm: (whose WM and CSF masks, global signal regression)
ARMS = {
    "taylor_off": ("taylor", False),  # the orchestrator's setup: the reference
    "ours_off": ("ours", False),
    "ours_on": ("ours", True),  # positive control: GSR should weaken the link to motion
}
EXIT_RUN_FINISHED = (0, 3)  # 3 = finished with high-severity warnings
EXIT_TEMPFAIL = 75  # Retried by the workflow, as in cloudpipe's runner


def log(event, **fields):
    print(json.dumps({"event": event, **fields}, default=str), flush=True)


def run_cmd(*cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def arm_block(paths, labels, out_dir, template=staging.PROC_TEMPLATE):
    """The production rest block, keeping per-run residuals so parcel series can be read."""
    blocks = yaml.safe_load(Path(template).read_text())["analyses"]
    block = copy.deepcopy(next(b for b in blocks if b["name"] == "rest_conn"))
    block.update(paths=paths, run_labels=labels, out_dir=str(out_dir), out_file_pre="s", keep_run_res_dtseries=True)
    block["extraction"].update(extract_ptseries=False, extract_raw_ptseries=False, extract_out_file_pre="s_parc")
    block["connectivity"].update(calc_conn=None, conn_out_file_pre="s_parc")
    return block


def taylor_regressors(runs, raws, input_dir, subj, ses, work):
    """The orchestrator's WM and CSF: FastSurfer's label, nearest-neighbour to the BOLD grid, brain-masked."""
    out = {"WM_paths": [], "CSF_paths": []}
    voxels = []
    for run in runs:
        counts = {}
        for tissue, key in (("WM", "WM_paths"), ("CSF", "CSF_paths")):
            label = input_dir / f"{subj}_{ses}_{SPACE_RES1}_label-{tissue}_mask.nii.gz"
            resampled = work / f"{run.rid}_{tissue}_t_res.nii.gz"
            mask = work / f"{run.rid}_{tissue}_t_mask.nii.gz"
            run_cmd("3dresample", "-master", str(run.bold), "-rmode", "NN", "-input", str(label), "-prefix", str(resampled))
            run_cmd("3dcalc", "-a", str(resampled), "-b", str(raws[run.rid]["brainmask"]), "-expr", "step(a)*step(b)", "-prefix", str(mask))
            counts[tissue] = int((np.asarray(nib.load(str(mask)).dataobj) > 0).sum())
            series = work / f"{run.rid}_{tissue}_t.1D"
            series.write_text(run_cmd("3dmaskave", "-quiet", "-mask", str(mask), str(run.bold)))
            out[key].append(str(series))
        voxels.append(counts)
    return out, voxels


def global_signals(runs, raws, work):
    """The trimmed BOLD's mean within each run's brain mask."""
    paths = []
    for run in runs:
        series = work / f"{run.rid}_gs.1D"
        series.write_text(run_cmd("3dmaskave", "-quiet", "-mask", str(raws[run.rid]["brainmask"]), str(run.bold)))
        paths.append(str(series))
    return paths


def run_arm(arm, paths, labels, atlas, work):
    """Run one arm. Returns (exit code, its output directory)."""
    out_dir = work / f"arm_{arm}"
    out_dir.mkdir(parents=True)
    cores = os.environ.get("OMP_NUM_THREADS", "1")
    config = {"global": {"num_cores": int(cores), "tr": TR, "template_path": str(atlas), "force_diff_atlas": True},
              "analyses": [arm_block(paths, labels, out_dir)]}  # fmt: skip
    path = work / f"{arm}.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    result = subprocess.run(["fmri-first-level-proc", "--config", str(path), "--analyses", "0"],
                            cwd=out_dir, capture_output=True, text=True)  # fmt: skip
    (work / f"{arm}.log").write_text(result.stdout + result.stderr)
    return result.returncode, out_dir


def parcel_means(residual, labels, n_parcels):
    """(T, P) means of voxels with signal, because brain masking leaves some parcel voxels at zero."""
    data = np.asarray(nib.load(str(residual)).dataobj, dtype=np.float32)
    voxels = (labels > 0) & np.any(data != 0, axis=3)
    x, lab = data[voxels], labels[voxels] - 1
    counts = np.bincount(lab, minlength=n_parcels).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.stack([np.bincount(lab, weights=x[:, t], minlength=n_parcels) / counts for t in range(x.shape[1])])


def resample_atlas(atlas, master, work):
    out = work / "atlas_on_bold.nii.gz"
    run_cmd("3dresample", "-master", str(master), "-rmode", "NN", "-input", str(atlas), "-prefix", str(out))
    img = nib.load(str(out))
    labels = np.asarray(img.dataobj).astype(int)
    parcels = np.arange(1, labels.max() + 1)
    voxel_xyz = nib.affines.apply_affine(img.affine, np.argwhere(labels > 0))
    centroids = np.stack([voxel_xyz[labels[labels > 0] == p].mean(axis=0) if (labels == p).any()
                          else np.full(3, np.nan) for p in parcels])  # fmt: skip
    return labels, centroids


def process_session(subj, ses, input_dir, atlas, work, arms):
    """Everything saved for one session: per-arm series and censor masks, FD and timing."""
    sess = staging.Session(subj, ses, Path(input_dir), "fixed", work)
    work.mkdir(parents=True, exist_ok=True)
    by_task = sess.runs_by_task(sess.read_marker())
    runs, raws = sess.stage_task("rest", by_task.get("rest", []), TR)
    ours, reason = sess.rest_paths(runs, raws)
    if ours is None:
        return None, {"skipped": reason}
    used = [r for r in runs if not r.excluded]
    run_labels = ours.pop("run_labels")
    ours.pop("GS_paths", None)  # the image under test may or may not pass it; each arm decides
    taylor, taylor_voxels = taylor_regressors(used, raws, Path(input_dir), subj, ses, work)
    gs = global_signals(used, raws, work)
    labels, centroids = resample_atlas(atlas, used[0].bold, work)
    n_parcels = len(centroids)
    arrays = {"centroids": centroids.astype(np.float32)}
    mean_fd = []
    for run in used:
        confounds = pd.read_csv(raws[run.rid]["confounds"], sep="\t", na_values=["n/a"])
        mean_fd.append(float(confounds["framewise_displacement"].iloc[run.n_remove + 1 :].mean()))
    summary = {"runs": [r.rid for r in used], "run_labels": run_labels, "mean_fd": mean_fd,
               "n_frames": [r.n_frames for r in used], "taylor_voxels": taylor_voxels,
               "our_voxels": [r.extra.get("mask_voxels") for r in used], "arms": {}}  # fmt: skip
    for arm in arms:
        masks, use_gs = ARMS[arm]
        paths = {**copy.deepcopy(ours), **(copy.deepcopy(taylor) if masks == "taylor" else {})}
        if use_gs:
            paths["GS_paths"] = gs
        started = time.monotonic()
        code, out_dir = run_arm(arm, paths, run_labels, atlas, work)
        kept_runs = []
        for i, label in enumerate(run_labels):
            residual = out_dir / f"s_run{label}_residual_dtseries.nii.gz"
            censor = out_dir / f"s_run{label}_censor.1D"
            if censor.exists():
                arrays[f"{arm}_censor{i}"] = np.loadtxt(censor).astype(np.int8)
            if residual.exists():
                series = parcel_means(residual, labels, n_parcels).astype(np.float32)
                if series.shape[0] != len(arrays[f"{arm}_censor{i}"]):
                    raise RuntimeError(f"{arm} run {label}: {series.shape[0]} residual frames, censor has {len(arrays[f'{arm}_censor{i}'])}")
                arrays[f"{arm}_series{i}"] = series
                kept_runs.append(i)
        qc_path = out_dir / "s_qc_summary.json"
        qc = json.loads(qc_path.read_text()) if qc_path.exists() else {}
        summary["arms"][arm] = {"exit_code": code, "finished": code in EXIT_RUN_FINISHED, "kept_runs": kept_runs,
                                "excluded": qc.get("excluded_runs"), "per_run_dof": [r.get("dof") for r in qc.get("per_run_dof") or []],
                                "seconds": round(time.monotonic() - started)}  # fmt: skip
        log("arm-done", arm=arm, exit_code=code, kept_runs=len(kept_runs), of=len(used), seconds=summary["arms"][arm]["seconds"])
        if code not in EXIT_RUN_FINISHED and code != 5:  # 5 = every run lost, a result here
            raise RuntimeError(f"{arm} exited {code}: {(work / f'{arm}.log').read_text()[-2000:]}")
        shutil.rmtree(out_dir)  # Residuals are large
    return arrays, summary


def save(path, arrays, summary):
    np.savez_compressed(path, summary=json.dumps(summary), **(arrays or {}))


def run_from_bucket(args):
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    sys.path.insert(0, "/app")
    from stage_first_level import download_session, list_sessions

    s3 = boto3.client("s3")
    try:
        table = s3.get_object(Bucket=args.bucket, Key=args.sessions_key)["Body"].read().decode()
        row = list(csv.DictReader(io.StringIO(table)))[args.index]
        subj, ses = row["subject_id"], row["session"]
        key = f"{args.output_prefix}/sessions/{args.index:05d}.npz"
        if s3.list_objects_v2(Bucket=args.bucket, Prefix=key).get("KeyCount"):
            log("already-done", index=args.index)
            return 0
        states = {s["ses"]: s["probseg_state"] for s in list_sessions(s3, args.bucket, args.metrics_bucket, subj)}
        state = states.get(ses, "no-func-marker")
        out = args.workdir / "out.npz"
        args.workdir.mkdir(parents=True, exist_ok=True)
        if state != "fixed":
            arrays, summary = None, {"skipped": f"probseg-{state}"}
        else:
            raw = args.workdir / "raw"
            download_session(s3, args.bucket, subj, ses, state, raw)
            wm = f"{subj}_{ses}_{SPACE_RES1}_label-WM_mask.nii.gz"  # the runner fetches only CSF's
            s3.download_file(args.bucket, f"derivatives/func/{subj}/{ses}/{wm}", str(raw / wm))
            arrays, summary = process_session(subj, ses, raw, args.atlas, args.workdir / "work", args.arms)
        summary.update(make=row["make"], index=args.index)
        save(out, arrays, summary)
        s3.upload_file(str(out), args.bucket, key)
        log("saved", index=args.index, skipped=summary.get("skipped"))
        return 0
    except (ClientError, BotoCoreError) as exc:
        log("s3-error", error=type(exc).__name__)
        return EXIT_TEMPFAIL


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--atlas", type=Path, required=True)
    ap.add_argument("--workdir", type=Path, required=True)
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--metrics-bucket", default="cloudpipe-metrics")
    ap.add_argument("--sessions-key", required=True)
    ap.add_argument("--output-prefix", required=True)
    ap.add_argument("--index", type=int, required=True)
    ap.add_argument("--arms", type=lambda text: tuple(text.split(",")), default=tuple(ARMS))
    args = ap.parse_args(argv)
    unknown = set(args.arms) - set(ARMS)
    if unknown:
        ap.error(f"unknown arms: {sorted(unknown)}")
    return run_from_bucket(args)


if __name__ == "__main__":
    sys.exit(main())
