"""Test 4 data: new DSSAT seasons at new points of the Americas' soybean area.

New 0.5° cells with soybean (GAEZ harvested area >= 500 ha), not used by dssat_v1, sampled with
probability proportional to the square root of the soybean area: 160 in the USA, 160 in
Argentina/Uruguay/Paraguay, 80 in Brazil. Same season design as dssat_v1 (60 seasons per point,
GGCMI calendar, MG around the latitude's, 30 % perturbed, 20 % without water stress), another seed.

Usage (repository root env: CROPEMU_DSSAT_EXE, CROPEMU_DSSAT_HOME):
    python exp4_generate.py --prepare-only     # downloads (weather, soil) only
    python exp4_generate.py                    # downloads if needed, then simulates
"""
import argparse
import time

import numpy as np
import pandas as pd

from cropemu_bench.design import SeasonDesign
from cropemu_bench.inputs.points import add_strata, grid_table
from cropemu_bench.pipeline import generate, prepare_inputs

from common import DATA, ROOT

OUT = ROOT / "data" / "dssat_americas"
REGIONS = {  # name: (query on the 0.5° grid, number of new points)
    "USA": ("lat >= 25 and lat <= 50 and lon >= -110 and lon <= -65", 160),
    "Argentina/Uruguay/Paraguay": ("lat >= -40 and lat <= -19 and lon >= -66 and lon <= -53", 160),
    "Brazil": ("lat >= -34 and lat <= 5 and lon > -53 and lon <= -34", 80),
}


def new_points(seed=20261114):
    rng = np.random.default_rng(seed)
    g = add_strata(grid_table())
    g = g[(g["soy_ha"] >= 500) & ~g["koppen"].isin(["ET", "EF"])]
    used = pd.read_parquet(DATA / "points.parquet")
    taken = set(zip(used["lat"].round(2), used["lon"].round(2)))
    g = g[[(a, b) not in taken for a, b in zip(g["lat"].round(2), g["lon"].round(2))]]
    rows = []
    for name, (q, n) in REGIONS.items():
        cells = g.query(q)
        p = np.sqrt(cells["soy_ha"].to_numpy())
        pick = rng.choice(len(cells), size=min(n, len(cells)), replace=False, p=p / p.sum())
        for c in cells.iloc[pick].itertuples():
            rows.append({"id": f"am:{c.lat:+.2f}_{c.lon:+.2f}", "lat": c.lat, "lon": c.lon, "kind": "soy", "koppen": c.koppen,
                         "stratum": c.stratum, "block": c.block, "soy_ha": c.soy_ha, "region": name})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare-only", action="store_true")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    prepared = OUT / "points_prepared.parquet"
    t0 = time.time()
    if prepared.exists():
        pts = pd.read_parquet(prepared)
    else:
        pts = new_points()
        print(pts["region"].value_counts().to_string(), flush=True)
        pts = prepare_inputs(pts.drop(columns="region"), n_jobs_weather=4, n_jobs_soil=16)
        pts.to_parquet(prepared)
    print(f"{pts['ok'].sum()} usable points of {len(pts)} ({(time.time() - t0) / 60:.1f} min)", flush=True)
    if args.prepare_only:
        return
    meta = __import__("json").loads((DATA / "meta.json").read_text())["design"]
    design = SeasonDesign(**{**meta, "seed": 20261114})
    generate(pts, OUT, design, points_per_batch=50, n_jobs=args.jobs)
    print(f"done in {(time.time() - t0) / 60:.1f} min -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
