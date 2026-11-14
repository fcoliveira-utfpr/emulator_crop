"""Shared setup of the emulator improvement tests (DSSAT dssat_v1, 5-fold validation by 5° blocks).

Every test uses the same folds as the published benchmark (cropemu_bench.evaluate.splits with the
blocks and seed 0), so the out-of-fold errors are directly comparable with the current emulator.
Results are appended to benchmark/improve/results/results.csv (one row per test).
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from cropemu_bench.dataset import build
from cropemu_bench.evaluate import cross_validate, metrics, within_site_sd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "dssat_v1"
OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(exist_ok=True)

#: Outputs reported in the comparison table.
KEY = ["HWAM", "CWAM", "LAIX", "HIAM", "ETCM", "DRCM", "EDAT_dap", "ADAT_dap", "MDAT_dap"]
PHENOLOGY = ["EDAT_dap", "ADAT_dap", "MDAT_dap", "HDAT_dap"]


def load():
    """X, Y, info of dssat_v1 (the published emulator's inputs and outputs)."""
    X, Y, info = build(DATA, derived=False)
    pts = pd.read_parquet(DATA / "points.parquet").set_index("id")
    info = info.join(pts[["lat", "lon"]], on="point")
    info["region"] = region(info["lat"].to_numpy(), info["lon"].to_numpy())
    return X, Y, info


def region(lat, lon):
    """Coarse regions of the Americas (the rest is "other")."""
    lat, lon = np.asarray(lat), np.asarray(lon)
    out = np.full(len(lat), "other", dtype=object)
    out[(lon < -30)] = "other Americas"
    out[(lat >= 25) & (lat <= 50) & (lon >= -110) & (lon <= -65)] = "USA"
    out[(lat > -56) & (lat < -22) & (lon >= -73) & (lon < -53)] = "Argentina/Uruguay"
    out[(lat >= -35) & (lat <= 5) & (lon >= -75) & (lon <= -34) & ~((lat < -22) & (lon < -53))] = "Brazil"
    return out


def baseline_oof():
    """Out-of-fold predictions of the published emulator (MLP by groups, block validation)."""
    return pd.read_parquet(DATA / "benchmark" / "mlp_grouped_block_oof.parquet")


def evaluate(name: str, oof: pd.DataFrame, Y: pd.DataFrame, info: pd.DataFrame, minutes: float = np.nan,
             note: str = "") -> dict:
    """Key metrics of out-of-fold predictions; appended to results.csv and returned."""
    cols = [c for c in Y.columns if c in oof]
    m = metrics(Y[cols], oof.loc[Y.index, cols])
    row = {"test": name, "note": note, "minutes": round(minutes, 1), "median_r2": m["r2"].median()}
    for c in KEY:
        if c in m.index:
            row[f"rmse_{c}"] = m.loc[c, "rmse"]
    y, p = Y["HWAM"], oof.loc[Y.index, "HWAM"]
    row["yield_r2"] = m.loc["HWAM", "r2"]
    row["yield_rel_within_sd"] = m.loc["HWAM", "rmse"] / within_site_sd(y, info["point"])
    e = (p - y).to_numpy()
    low, high = y < y.quantile(1 / 3), y > y.quantile(2 / 3)
    row["yield_bias_low"], row["yield_bias_high"] = float(e[low].mean()), float(e[high].mean())
    for r in ("Brazil", "USA", "Argentina/Uruguay"):
        k = (info["region"] == r).to_numpy()
        row[f"yield_rmse_{r}"] = float(np.sqrt(np.nanmean(e[k] ** 2)))
    path = OUT / "results.csv"
    old = pd.read_csv(path) if path.exists() else pd.DataFrame()
    old = old[old.get("test", pd.Series(dtype=str)) != name] if len(old) else old
    pd.concat([old, pd.DataFrame([row])], ignore_index=True).to_csv(path, index=False)
    print(f"[{name}] yield RMSE {row['rmse_HWAM']:.1f} kg/ha (R² {row['yield_r2']:.4f}, "
          f"rel {row['yield_rel_within_sd']:.3f}); maturity {row['rmse_MDAT_dap']:.2f} d; "
          f"median R² {row['median_r2']:.4f}", flush=True)
    return row


def run_cv(name: str, factory, X: pd.DataFrame, Y: pd.DataFrame, info: pd.DataFrame, note: str = ""):
    """5-fold block cross-validation of ``factory()``; saves the out-of-fold predictions."""
    t0 = time.time()
    _, oof, cost = cross_validate(factory, X, Y, groups=info["block"], n_splits=5, seed=0)
    oof.to_parquet(OUT / f"{name}_oof.parquet")
    cost.to_csv(OUT / f"{name}_cost.csv", index=False)
    return evaluate(name, oof, Y, info, (time.time() - t0) / 60, note), oof


def cv_custom(name: str, fit_predict, X: pd.DataFrame, Y: pd.DataFrame, info: pd.DataFrame, note: str = ""):
    """Block cross-validation with a free-form ``fit_predict(train_index, test_index) -> DataFrame``
    (test rows x outputs); same folds as ``run_cv``. Saves and evaluates the out-of-fold predictions."""
    from cropemu_bench.evaluate import splits

    t0 = time.time()
    oof = pd.DataFrame(np.nan, index=Y.index, columns=Y.columns)
    for k, (tr, te) in enumerate(splits(len(X), info["block"], 5, 0)):
        p = fit_predict(tr, te)
        oof.loc[p.index, p.columns] = p.to_numpy()
        print(f"  {name}: fold {k + 1}/5 ({(time.time() - t0) / 60:.1f} min)", flush=True)
    oof.to_parquet(OUT / f"{name}_oof.parquet")
    return evaluate(name, oof, Y, info, (time.time() - t0) / 60, note), oof
