"""Draw the comparison's sessions: a simple random sample of complete v7 baseline sessions.

Writes the table to a local path outside the repository, because it holds subject IDs.
Prints counts only. Needs the AWS CLI.

    draw_sample.py --n 200 --seed 20261103 --out /scratch/anchor.csv
    draw_sample.py --n 300 --skip 200 --seed 20261103 --out /scratch/test.csv

One seed gives one shuffled order, so the two slices never share a subject.
"""

import argparse
import csv
import io
import random
import subprocess
from pathlib import Path


def choose(sessions, makes, n, seed, skip=0):
    """A slice of one shuffled order. Sorting first means one seed always gives one order."""
    eligible = sorted(s for s in sessions if s in makes)
    random.Random(seed).shuffle(eligible)
    return eligible[skip : skip + n]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--bucket", default="abcd-v7")
    ap.add_argument("--session", default="ses-00A")
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    listing = subprocess.run(["aws", "s3", "ls", f"s3://{args.bucket}/derivatives/func/"],
                             check=True, capture_output=True, text=True).stdout  # fmt: skip
    subjects = [line.split()[-1].rstrip("/") for line in listing.splitlines() if "sub-" in line]
    table = subprocess.run(["aws", "s3", "cp", f"s3://{args.bucket}/config/nss_volumes.csv", "-"],
                           check=True, capture_output=True, text=True).stdout  # fmt: skip
    makes = {}
    for row in csv.DictReader(io.StringIO(table)):
        if row["session"] == args.session:
            subject = row["subject_id"]
            makes[subject if subject.startswith("sub-") else f"sub-{subject}"] = row["scanner_make"]
    picked = choose(subjects, makes, args.n, args.seed, args.skip)
    with args.out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["subject_id", "session", "make"])
        writer.writerows((s, args.session, makes[s]) for s in picked)
    counts = {}
    for s in picked:
        counts[makes[s]] = counts.get(makes[s], 0) + 1
    print(f"drew {len(picked)} of {len(subjects)} subjects; by make: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
