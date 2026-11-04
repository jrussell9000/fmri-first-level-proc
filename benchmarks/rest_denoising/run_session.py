"""Run one ABCD session through every denoising arm and keep parcel time series.

Staging is shared, so arms differ only in their rest_conn settings. Each arm otherwise uses
the production block from abcd/data/proc_config_final.yaml, through the production CLI.

Local:   run_session.py --subj sub-X --ses ses-00A --input-dir DIR --atlas A --workdir W --out X.npz
Cluster: run_session.py --bucket B --sessions-key K --index I --output-prefix P --atlas A --workdir W
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
# Above Nyquist, so 3dTproject keeps every frequency over the low cutoff.
HIGHPASS_TOP_HZ = 99.0
ARMS = {
    "bandpass": {},
    "sequenced": {"use_sequenced_bandpass": True},
    "highpass": {"bandpass": [0.01, HIGHPASS_TOP_HZ]},
    # 6 motion parameters, CSF, WM and global signal. Set the margins, then became a test arm.
    "anchor_9p": {"motion_deriv_degree": 1, "use_tissue_derivs": False},
}
TEST_ARMS = ("bandpass", "sequenced", "highpass", "anchor_9p")
EXIT_RUN_FINISHED = (0, 3)  # 3 = finished with high-severity warnings
EXIT_TEMPFAIL = 75  # Retried by the workflow, as in cloudpipe's runner


def log(event, **fields):
    print(json.dumps({"event": event, **fields}, default=str), flush=True)


def arm_block(arm, paths, out_dir, template=staging.PROC_TEMPLATE):
    """The production rest block, with arm settings and per-run residuals kept for extraction."""
    blocks = yaml.safe_load(Path(template).read_text())["analyses"]
    block = copy.deepcopy(next(b for b in blocks if b["name"] == "rest_conn"))
    block.update(ARMS[arm])
    block.update(paths=paths, out_dir=str(out_dir), out_file_pre="s", keep_run_res_dtseries=True)
    block["extraction"].update(extract_ptseries=False, extract_raw_ptseries=False, extract_out_file_pre="s_parc")
    block["connectivity"].update(calc_conn=None, conn_out_file_pre="s_parc")
    return block


def run_arm(arm, paths, atlas, work):
    """Run one arm. Returns (exit code, its output directory)."""
    out_dir = work / f"arm_{arm}"
    out_dir.mkdir(parents=True)
    cores = os.environ.get("OMP_NUM_THREADS", "1")
    config = {"global": {"num_cores": int(cores), "tr": TR, "template_path": str(atlas), "force_diff_atlas": True},
              "analyses": [arm_block(arm, paths, out_dir)]}  # fmt: skip
    path = work / f"{arm}.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    cmd = ["fmri-first-level-proc", "--config", str(path), "--analyses", "0", "--log-file", str(out_dir / "log.txt")]
    return subprocess.run(cmd, cwd=out_dir, capture_output=True, text=True).returncode, out_dir


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
    subprocess.run(["3dresample", "-master", str(master), "-rmode", "NN", "-input", str(atlas), "-prefix", str(out)],
                   check=True, capture_output=True)  # fmt: skip
    img = nib.load(str(out))
    labels = np.asarray(img.dataobj).astype(int)
    parcels = np.arange(1, labels.max() + 1)
    voxel_xyz = nib.affines.apply_affine(img.affine, np.argwhere(labels > 0))
    centroids = np.stack([voxel_xyz[labels[labels > 0] == p].mean(axis=0) if (labels == p).any()
                          else np.full(3, np.nan) for p in parcels])  # fmt: skip
    return labels, centroids


def process_session(subj, ses, input_dir, atlas, work, state="fixed", arms=TEST_ARMS):
    """Everything saved for one session: per-arm series and censor masks, FD and timing."""
    sess = staging.Session(subj, ses, Path(input_dir), state, work)
    work.mkdir(parents=True, exist_ok=True)
    by_task = sess.runs_by_task(sess.read_marker())
    runs, raws = sess.stage_task("rest", by_task.get("rest", []), TR)
    paths, reason = sess.rest_paths(runs, raws)
    if paths is None:
        return None, {"skipped": reason}
    used = [r for r in runs if not r.excluded]
    labels, centroids = resample_atlas(atlas, used[0].bold, work)
    n_parcels = len(centroids)
    arrays = {"centroids": centroids.astype(np.float32)}
    mean_fd = []
    for run in used:
        confounds = pd.read_csv(raws[run.rid]["confounds"], sep="\t", na_values=["n/a"])
        mean_fd.append(float(confounds["framewise_displacement"].iloc[run.n_remove + 1 :].mean()))
    summary = {"runs": [r.rid for r in used], "mean_fd": mean_fd, "n_frames": [r.n_frames for r in used], "arms": {}}
    for arm in arms:
        started = time.monotonic()
        code, out_dir = run_arm(arm, paths, atlas, work)
        finished = code in EXIT_RUN_FINISHED
        kept_runs = []
        for i, _ in enumerate(used):
            residual = out_dir / f"s_run{i + 1}_residual_dtseries.nii.gz"
            censor = out_dir / f"s_run{i + 1}_censor.1D"
            if censor.exists():
                arrays[f"{arm}_censor{i}"] = np.loadtxt(censor).astype(np.int8)
            if residual.exists():
                arrays[f"{arm}_series{i}"] = parcel_means(residual, labels, n_parcels).astype(np.float32)
                kept_runs.append(i)
        qc_path = out_dir / "s_qc_summary.json"
        qc = json.loads(qc_path.read_text()) if qc_path.exists() else {}
        summary["arms"][arm] = {"exit_code": code, "finished": finished, "kept_runs": kept_runs,
                                "n_censored": [r["n_trs_censored"] for r in qc.get("per_run_censoring", [])],
                                "seconds": round(time.monotonic() - started)}  # fmt: skip
        log("arm-done", arm=arm, exit_code=code, kept_runs=len(kept_runs), of=len(used),
            seconds=summary["arms"][arm]["seconds"])  # fmt: skip
        shutil.rmtree(out_dir)  # Residuals and sequenced intermediates are large
    return arrays, summary


def save(path, arrays, summary):
    np.savez_compressed(path, summary=json.dumps(summary), **(arrays or {}))


def run_from_bucket(args):
    """One row of the sessions table, identified by index so IDs stay out of pod specs."""
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
            arrays, summary = process_session(subj, ses, raw, args.atlas, args.workdir / "work", state, args.arms)
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
    ap.add_argument("--subj")
    ap.add_argument("--ses")
    ap.add_argument("--input-dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--make", default="unknown")
    ap.add_argument("--bucket")
    ap.add_argument("--metrics-bucket", default="cloudpipe-metrics")
    ap.add_argument("--sessions-key")
    ap.add_argument("--output-prefix")
    ap.add_argument("--index", type=int)
    ap.add_argument("--arms", type=lambda text: tuple(text.split(",")), default=TEST_ARMS)
    args = ap.parse_args(argv)
    unknown = set(args.arms) - set(ARMS)
    if unknown:
        ap.error(f"unknown arms: {sorted(unknown)}")
    if args.bucket:
        return run_from_bucket(args)
    arrays, summary = process_session(args.subj, args.ses, args.input_dir, args.atlas, args.workdir, arms=args.arms)
    summary["make"] = args.make
    save(args.out, arrays, summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
