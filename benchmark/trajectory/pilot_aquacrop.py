"""Phase 2 pilot: AquaCrop on the seasons of the DSSAT pilot, with the daily trajectories kept.

Simulated twice, with the daily table written (data/traj_pilot_aquacrop) and without
(data/traj_pilot_aquacrop_nodaily), to measure the extra cost.

Usage (repository root, after pilot_dssat.py; env CROPEMU_AQUACROP_EXE):
    python benchmark/trajectory/pilot_aquacrop.py --jobs 8
"""
import argparse
import time
from pathlib import Path

import pandas as pd

from cropemu_bench.models.aquacrop import AquaCrop
from cropemu_bench.pipeline_aquacrop import TRAJECTORY_COLUMNS, generate

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CROPS = ROOT / "packages" / "cropemu-bench" / "tests" / "data" / "aquacrop"   # FAO SoybeanGDD.CRO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()
    model = AquaCrop(crop_dir=CROPS)
    times = {}
    for name, daily in (("traj_pilot_aquacrop", TRAJECTORY_COLUMNS), ("traj_pilot_aquacrop_nodaily", None)):
        t0 = time.time()
        generate(DATA / "traj_pilot_dssat", DATA / name, model=model, points_per_batch=20, n_jobs=args.jobs,
                 daily=daily)
        times[name] = time.time() - t0
    n = len(pd.read_parquet(DATA / "traj_pilot_aquacrop" / "design.parquet"))
    for name, dt in times.items():
        print(f"{name}: {n} seasons in {dt:.0f}s ({1000 * dt / n:.0f} ms/season)", flush=True)


if __name__ == "__main__":
    main()
