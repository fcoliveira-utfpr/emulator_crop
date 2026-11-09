"""Generate a DSSAT CROPGRO-Soybean simulation dataset on global points.

Usage (from the repository root, with CROPEMU_DSSAT_EXE and CROPEMU_DSSAT_HOME set):

    python benchmark/generate_dssat.py --name dssat_v0 --points 2000 --seasons 20

Inputs are downloaded once into $CROPEMU_CACHE (default ~/.cache/cropemu); the dataset
goes to data/<name>/ (git-ignored). Interrupted runs resume where they stopped.
"""

import argparse
import time
from pathlib import Path

import pandas as pd

from cropemu_bench.design import SeasonDesign
from cropemu_bench.inputs.points import PointDesign, grid_table, sample_points
from cropemu_bench.pipeline import generate, prepare_inputs

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="dssat_v0")
    ap.add_argument("--points", type=int, default=2000)
    ap.add_argument("--seasons", type=int, default=20, help="seasons per point")
    ap.add_argument("--seed", type=int, default=20261108)
    ap.add_argument("--jobs", type=int, default=8, help="DSSAT processes")
    ap.add_argument("--sites", type=Path, help="sites.csv from the systematic review (optional)")
    args = ap.parse_args()

    out = ROOT / "data" / args.name
    out.mkdir(parents=True, exist_ok=True)
    prepared = out / "points_prepared.parquet"
    t0 = time.time()
    if prepared.exists():
        pts = pd.read_parquet(prepared)
    else:
        sites = None
        if args.sites:
            from cropemu_bench.inputs.sites import load_sites
            sites = load_sites(args.sites)
        pts = sample_points(grid_table(), PointDesign(n_total=args.points, seed=args.seed), sites)
        pts = prepare_inputs(pts)
        pts.to_parquet(prepared)
    print(f"{pts['ok'].sum()} usable points of {len(pts)} ({time.time() - t0:.0f}s)", flush=True)
    print(pts.loc[~pts["ok"], ["id", "problem"]].to_string(), flush=True)

    generate(pts, out, SeasonDesign(seasons_per_point=args.seasons, seed=args.seed), points_per_batch=50,
             n_jobs=args.jobs)
    print(f"done in {(time.time() - t0) / 60:.1f} min -> {out}", flush=True)


if __name__ == "__main__":
    main()
