"""Crop model runs of the monitoring hindcast: the 7 independent sites x seasons 1995-2024, rainfed and
without water stress, with the actual weather of each season (reference B of analises/06_hindcast.py).

    python benchmark/hindcast_sims.py [--work data/hindcast/sims]

Same pipeline as the training data, with the sampling replaced by fixed seasons: GGCMI planting day (no
offset), typical maturity group of the latitude with the default coefficients (no perturbation), 30
plants/m², observed CO2, no climate perturbation; AquaCrop with the middle of the range of its perturbed
parameters and the climatological thermal time of the calendar (cycle factor 1). Writes the cultivars of
each site to ``<work>/cultivars.json`` (emulator keys), read by web/tests/hindcast_monitor.mjs so the
emulator and the crop models receive the same inputs.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

import cropemu
from cropemu_bench import pipeline, pipeline_aquacrop
from cropemu_bench.dataset import build
from cropemu_bench.design import aquacrop as aq_design
from cropemu_bench.design.cultivars import cultivar_from_mg, mg_center
from cropemu_bench.models.aquacrop import AquaCrop

ROOT = Path(__file__).resolve().parents[1]
CROP_DIR = ROOT / "packages" / "cropemu-bench" / "tests" / "data" / "aquacrop"
SITES = pd.DataFrame([
    ("Londrina-PR", -23.19, -51.18), ("Rio Verde-GO", -17.80, -50.92), ("Sorriso-MT", -12.55, -55.71),
    ("Passo Fundo-RS", -28.26, -52.41), ("Pergamino-AR", -33.89, -60.57), ("Ames-IA", 42.03, -93.62),
    ("Harbin-CN", 46.20, 126.50)], columns=["id", "lat", "lon"])
SITES["block"], SITES["koppen"], SITES["kind"] = "new", "", "new_site"
YEARS = range(1995, 2025)


def fixed_seasons(points, calendar, table, design):
    """Replaces design_seasons: every year, GGCMI planting day, typical MG, default coefficients."""
    cal = calendar.set_index("id")["planting_doy"]
    rows, cultivars = [], []
    for p in points.itertuples():
        doy = int(cal[p.id])
        md = date(2001, 1, 1) + timedelta(days=min(doy, 365) - 1)
        mg = float(mg_center(p.lat))
        cid = f"H{len(cultivars):05d}"
        cul = cultivar_from_mg(table, cid, mg)                 # no perturbation
        cultivars.append(cul)
        for y in YEARS:
            for water in (True, False):                        # rainfed, no water stress
                rows.append({"sample": len(rows), "point": p.id, "year": y,
                             # same day and month every year (as the app and hindcast_monitor.mjs)
                             "sowing": date(y, md.month, md.day), "sowing_offset": 0,
                             "mg": mg, "cultivar": cid, "ecotype": cul.ecotype, "water": water, "perturbed": False,
                             "dt": 0.0, "rain_factor": 1.0, "co2": np.nan, **cul.coefficients})
    return pd.DataFrame(rows), cultivars


_aq_original = aq_design.aquacrop_design


def middle_parameters(dssat_design, points, gdd_clim, seed=0):
    d = _aq_original(dssat_design, points, gdd_clim)
    for n, (kind, lo, hi) in aq_design.AQ_PERTURBATIONS.items():
        d[n] = (lo + hi) / 2
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "hindcast" / "sims")
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()
    pipeline.design_seasons = fixed_seasons
    pipeline_aquacrop.aquacrop_design = middle_parameters
    d = pipeline.generate(SITES, args.work / "dssat", progress=True, n_jobs=args.jobs, points_per_batch=len(SITES))
    a = pipeline_aquacrop.generate(d, args.work / "aquacrop", model=AquaCrop(crop_dir=CROP_DIR),
                                   points_per_batch=len(SITES), progress=True, n_jobs=args.jobs)

    # cultivars in emulator keys, one per site and model, and the simulated yields
    out, sims = {}, []
    for name, folder, emu in (("dssat", d, "dssat-soybean-v3"), ("aquacrop", a, "aquacrop-soybean-v3")):
        e = cropemu.load(emu)
        design = pd.read_parquet(folder / "design.parquet")
        for pid, g in design.groupby("point"):
            r = g.iloc[0]
            cul = {k: float(r[k]) for k in e.cultivar_ if k in r and pd.notna(r[k])}
            cul.setdefault("population", 30.0)
            out.setdefault(pid, {})[name] = cul
        _, Y, info = build(folder, derived=True)
        ycol, mcol, scale = {"dssat": ("HWAM", "MDAT_dap", 1e-3), "aquacrop": ("Y(dry)", "MAT_dap", 1.0)}[name]
        dz = design.set_index("sample").loc[Y.index]
        sims.append(pd.DataFrame({"site": dz["point"], "model": name, "year": dz["year"],
                                  "rainfed": dz["water"].astype(bool), "yield": Y[ycol] * scale,
                                  "maturity": Y.get(mcol)}))
    (args.work / "cultivars.json").write_text(json.dumps(out, indent=1))
    s = pd.concat(sims)
    s.to_csv(args.work / "sim_yields.csv", index=False)
    print(s.groupby(["model", "rainfed"])["yield"].describe().round(2).to_string())
    print("wrote", args.work / "cultivars.json", args.work / "sim_yields.csv")


if __name__ == "__main__":
    main()
