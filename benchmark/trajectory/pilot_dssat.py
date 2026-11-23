"""Phase 2 pilot: DSSAT seasons with the daily trajectories (PlantGro) kept.

A spread subset of the dssat_v1 points (same point sampling, same season design: 60 seasons per
point), simulated twice: with the daily tables written (data/traj_pilot_dssat) and without
(data/traj_pilot_dssat_nodaily), to measure the extra cost of the daily output.

Usage (repository root; env CROPEMU_DSSAT_EXE, CROPEMU_DSSAT_HOME):
    python benchmark/trajectory/pilot_dssat.py --points 40 --jobs 8
"""
import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

from cropemu_bench.design import SeasonDesign
from cropemu_bench.inputs.points import PointDesign, grid_table, sample_points
from cropemu_bench.pipeline import TRAJECTORY_COLUMNS, generate, prepare_inputs

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def pilot_points(n: int, seed: int = 7) -> pd.DataFrame:
    """``n`` of the dssat_v1 fill points, spread over latitude bands (equal share per 10° band)."""
    pts = sample_points(grid_table(), PointDesign(n_total=2000))
    pts = pts.assign(band=(pts["lat"] // 10).astype(int))
    rng = np.random.default_rng(seed)
    bands = sorted(pts["band"].unique())
    per = max(1, n // len(bands))
    pick = [g.iloc[rng.choice(len(g), size=min(per, len(g)), replace=False)] for _, g in pts.groupby("band")]
    return pd.concat(pick).drop(columns="band").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", type=int, default=40)
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()
    out = DATA / "traj_pilot_dssat"
    out.mkdir(parents=True, exist_ok=True)
    prepared = out / "points_prepared.parquet"
    t0 = time.time()
    if prepared.exists():
        pts = pd.read_parquet(prepared)
    else:
        pts = prepare_inputs(pilot_points(args.points), n_jobs_weather=4, n_jobs_soil=8)
        pts.to_parquet(prepared)
    print(f"{pts['ok'].sum()} usable points of {len(pts)} ({(time.time() - t0) / 60:.1f} min)", flush=True)

    design = SeasonDesign(seasons_per_point=60)
    times = {}
    for name, daily in (("traj_pilot_dssat", TRAJECTORY_COLUMNS), ("traj_pilot_dssat_nodaily", None)):
        t0 = time.time()
        generate(pts, DATA / name, design, points_per_batch=20, n_jobs=args.jobs, daily=daily)
        times[name] = time.time() - t0
    n = len(pd.read_parquet(DATA / "traj_pilot_dssat" / "design.parquet"))
    for name, dt in times.items():
        print(f"{name}: {n} seasons in {dt:.0f}s ({1000 * dt / n:.0f} ms/season)", flush=True)


if __name__ == "__main__":
    main()
