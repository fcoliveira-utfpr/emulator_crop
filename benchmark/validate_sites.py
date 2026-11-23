"""v3 emulators against the crop models at the 7 independent sites (not in the training data).

    python benchmark/validate_sites.py [--seasons 60] [--work data/sites_v3]

Same steps as examples/compare_emulator_simulator.ipynb, for the v3 emulators and without plots:
seasons drawn with the training design (plant population sampled in 15-50 plants/m², no climate
perturbations), run with the DSSAT and AquaCrop executables with daily tables, predicted through the
public API of ``cropemu``. Also reruns the same seasons at 15 and 50 plants/m² (every other input
unchanged) to compare the population response of simulators and emulators.

Writes to ``<work>/results``: ``outputs_<model>.csv`` (error per output vs the card's block
validation), ``curves_<model>.csv`` (error of the curve shapes), ``population.csv`` (yield change
from 15 to 50 plants/m², simulator vs emulator, by site and water regime).
Needs the executables (CROPEMU_DSSAT_EXE, CROPEMU_DSSAT_HOME, CROPEMU_AQUACROP_EXE) and internet or
the cache for NASA POWER and SoilGrids.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import cropemu
from cropemu.soil import soilgrids
from cropemu.weather import fetch, fill_gaps
from cropemu_bench import pipeline, pipeline_aquacrop
from cropemu_bench.models.aquacrop import AquaCrop
from cropemu_bench.dataset import build
from cropemu_bench.design.seasons import SeasonDesign
from cropemu_bench.trajectory import trajectory_targets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark" / "trajectory"))
from train_trajectory import metrics as curve_metrics  # noqa: E402

SITES = pd.DataFrame([
    ("Londrina-PR", -23.19, -51.18), ("Rio Verde-GO", -17.80, -50.92), ("Sorriso-MT", -12.55, -55.71),
    ("Passo Fundo-RS", -28.26, -52.41), ("Pergamino-AR", -33.89, -60.57), ("Ames-IA", 42.03, -93.62),
    ("Harbin-CN", 46.20, 126.50)], columns=["id", "lat", "lon"])
SITES["block"], SITES["koppen"], SITES["kind"] = "new", "", "new_site"
EMULATORS = {"dssat": "dssat-soybean-v3", "aquacrop": "aquacrop-soybean-v3"}
YIELD = {"dssat": ("HWAM", 1e-3), "aquacrop": ("Y(dry)", 1.0)}     # t/ha
CROP_DIR = ROOT / "packages" / "cropemu-bench" / "tests" / "data" / "aquacrop"


def simulate(work: Path, design: SeasonDesign, jobs: int) -> dict[str, Path]:
    d = pipeline.generate(SITES, work / "dssat", design, points_per_batch=len(SITES), progress=False,
                          n_jobs=jobs, daily=pipeline.TRAJECTORY_COLUMNS)
    a = pipeline_aquacrop.generate(d, work / "aquacrop", model=AquaCrop(crop_dir=CROP_DIR), points_per_batch=len(SITES),
                                   progress=False, n_jobs=jobs, daily=pipeline_aquacrop.TRAJECTORY_COLUMNS)
    return {"dssat": d, "aquacrop": a}


def emulate(emu, folder: Path):
    design = pd.read_parquet(folder / "design.parquet")
    pts = pd.read_parquet(folder / "points.parquet").set_index("id")
    outs, shapes, used = [], [], []
    for pid, seasons in design.groupby("point"):
        p = pts.loc[pid]
        weather = fill_gaps(fetch(p["lat"], p["lon"], pipeline.WEATHER_START, pipeline.WEATHER_END))
        soil = soilgrids.fetch(p["lat"], p["lon"])
        for r in seasons.to_dict("records"):
            res = emu.predict(weather, lat=p["lat"], elev=p["elev"], soil=soil, sowing=r["sowing"],
                              cultivar={k: r[k] for k in emu.cultivar_}, irrigated=not r["water"])
            outs.append(res.outputs.assign(sample=r["sample"]))
            shapes.append(res.shapes.assign(sample=r["sample"]))
            used.append(res.inputs.assign(sample=r["sample"], point=pid, water=r["water"],
                                          out_of_domain=len(res.out_of_domain.iloc[0]),
                                          rare=len(res.rare_inputs.iloc[0])))
    return tuple(pd.concat(t).set_index("sample") for t in (outs, shapes, used))


def output_table(Y: pd.DataFrame, P: pd.DataFrame, acc: dict) -> pd.DataFrame:
    rows = []
    for c in P.columns:
        if c not in Y:
            continue
        y, p = Y[c], P.loc[Y.index, c]
        ok = y.notna() & p.notna()
        if ok.sum() < 5:
            continue
        e = p[ok] - y[ok]
        ss = ((y[ok] - y[ok].mean()) ** 2).sum()
        rows.append({"output": c, "n": int(ok.sum()), "mean_sim": y[ok].mean(), "bias": e.mean(),
                     "rmse": np.sqrt((e ** 2).mean()), "r2": 1 - (e ** 2).sum() / ss if ss > 0 else np.nan,
                     "card_rmse": acc.get(c, {}).get("rmse", np.nan), "card_r2": acc.get(c, {}).get("r2", np.nan),
                     "card_level": acc.get(c, {}).get("level", "")})
    t = pd.DataFrame(rows).set_index("output")
    return t.assign(ratio=t["rmse"] / t["card_rmse"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons", type=int, default=60, help="seasons per site")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "sites_v3")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    res_dir = args.work / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    emus = {k: cropemu.load(v) for k, v in EMULATORS.items()}
    print("cropemu", cropemu.__version__, {k: str(e) for k, e in emus.items()}, flush=True)

    # 1. sampled population: outputs and curves
    t0 = time.time()
    design = SeasonDesign(seasons_per_point=args.seasons, perturbed_share=0.0, seed=args.seed, population_range=(15, 50))
    folders = simulate(args.work / "sampled", design, args.jobs)
    print(f"simulations: {time.time() - t0:.0f} s", flush=True)
    summary = []
    for name, emu in emus.items():
        X, Y, info = build(folders[name], derived=True)
        P, S, used = emulate(emu, folders[name])
        cols = emu.inputs_
        diff = (used.loc[X.index, cols] - X[cols]).abs().max()
        print(f"{name}: {len(Y)} seasons | max |library - pipeline| input diff {diff.max():.2g} ({diff.idxmax()}) | "
              f"out of domain {int((used['out_of_domain'] > 0).sum())} | rare {int((used['rare'] > 0).sum())}", flush=True)
        t = output_table(Y, P, emu.card.get("acceptance", {}))
        t.to_csv(res_dir / f"outputs_{name}.csv")
        T = trajectory_targets(folders[name]).reindex(S.index)
        T = T[T.notna().any(axis=1)]
        cm = curve_metrics(T, S.loc[T.index, T.columns])
        cm.to_csv(res_dir / f"curves_{name}.csv", index=False)
        ycol, scale = YIELD[name]
        e = (P.loc[Y.index, ycol] - Y[ycol]) * scale
        by_site = pd.DataFrame({"site": info["point"], "e": e}).groupby("site")["e"].agg(
            bias="mean", rmse=lambda v: np.sqrt(np.mean(v ** 2))).reindex(SITES["id"])
        by_site.to_csv(res_dir / f"yield_by_site_{name}.csv")
        print(t.loc[[c for c in t.index if c in (ycol, "MDAT_dap", "MAT_dap", "CWAM", "BioMass", "ADAT_dap", "FLO_dap")]]
              .round(3).to_string(), flush=True)
        print(f"  median rmse/card_rmse over {t['ratio'].notna().sum()} outputs: {t['ratio'].median():.2f}", flush=True)
        print(cm[cm["part"] == "all"].round(3).to_string(index=False), flush=True)
        print(by_site.round(3).to_string(), flush=True)
        summary.append((name, t, cm))

    # 2. population response: same seasons at 15 and 50 plants/m²
    rows = []
    sim_pop, emu_pop = {}, {}
    for pop in (15.0, 50.0):
        d = SeasonDesign(seasons_per_point=args.seasons, perturbed_share=0.0, seed=args.seed, population_range=(pop, pop))
        f = simulate(args.work / f"pop{int(pop)}", d, args.jobs)
        for name, emu in emus.items():
            _, Y, info = build(f[name], derived=True)
            P = emulate(emu, f[name])[0]
            ycol, scale = YIELD[name]
            sim_pop[name, pop] = Y[ycol] * scale
            emu_pop[name, pop] = P.loc[Y.index, ycol] * scale
            water = pd.read_parquet(f[name] / "design.parquet").set_index("sample").loc[Y.index, "water"]
            sim_pop[name, "site"], sim_pop[name, "water"] = info["point"], water
    for name in emus:
        ds = sim_pop[name, 50.0] - sim_pop[name, 15.0]
        de = emu_pop[name, 50.0] - emu_pop[name, 15.0]
        t = pd.DataFrame({"site": sim_pop[name, "site"], "rainfed": sim_pop[name, "water"], "sim": ds, "emu": de}).dropna()
        for (site, rf), g in t.groupby(["site", "rainfed"]):
            rows.append({"model": name, "site": site, "regime": "rainfed" if rf else "irrigated", "n": len(g),
                         "sim_change": g["sim"].mean(), "emu_change": g["emu"].mean(),
                         "r_season": g["sim"].corr(g["emu"]) if len(g) > 2 else np.nan})
        for rf, g in t.groupby("rainfed"):
            rows.append({"model": name, "site": "all", "regime": "rainfed" if rf else "irrigated", "n": len(g),
                         "sim_change": g["sim"].mean(), "emu_change": g["emu"].mean(), "r_season": g["sim"].corr(g["emu"])})
    pop = pd.DataFrame(rows)
    pop.to_csv(res_dir / "population.csv", index=False)
    print("\nyield change 15 -> 50 plants/m² (t/ha):")
    print(pop[pop["site"] == "all"].round(3).to_string(index=False))
    print(f"done in {(time.time() - t0) / 60:.1f} min -> {res_dir}")


if __name__ == "__main__":
    main()
