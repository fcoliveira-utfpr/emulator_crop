"""Shared loaders and figure style of the paper analyses."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from cropemu_bench.dataset import build

ROOT = Path(__file__).resolve().parents[1]
FIG, TAB = ROOT / "analises" / "figures", ROOT / "analises" / "tables"
FIG.mkdir(exist_ok=True)
TAB.mkdir(exist_ok=True)

MODELS = {
    "dssat": dict(data="dssat_v1", emulator="mlp_grouped", label="DSSAT CROPGRO-Soybean",
                  yld="HWAM", yscale=1e-3, mat="MDAT_dap", flo="ADAT_dap", et="ETCM", bio="CWAM"),
    "aquacrop": dict(data="aquacrop_v1", emulator="mlp_offset", label="AquaCrop 7.3",
                     yld="Y(dry)", yscale=1.0, mat="MAT_dap", flo="FLO_dap", et="ET_crop", bio="BioMass"),
}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
LEVEL_COLOR = {"recommended": "#0ca30c", "caution": "#fab219", "not recommended": "#d03b3b"}

plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "0.9", "grid.linewidth": 0.6, "axes.edgecolor": "0.5",
                     "axes.titlesize": 9, "axes.labelsize": 8.5, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
                     "legend.fontsize": 7.5, "legend.frameon": False, "figure.dpi": 150, "savefig.dpi": 300,
                     "savefig.bbox": "tight", "font.family": "DejaVu Sans",
                     "axes.prop_cycle": plt.cycler(color=SERIES)})


def load(model: str):
    """X, Y (simulated), P (out-of-fold emulated, spatial blocks), info (point, block, koppen, kind + design
    and point columns) of a model."""
    m = MODELS[model]
    folder = ROOT / "data" / m["data"]
    X, Y, info = build(folder, derived=True)
    P = pd.read_parquet(folder / "benchmark" / f"{m['emulator']}_block_oof.parquet").loc[Y.index]
    design = pd.read_parquet(folder / "design.parquet").set_index("sample")
    cols = [c for c in ("year", "sowing", "mg", "water", "perturbed", "dt", "rain_factor", "co2") if c in design]
    info = info.join(design[cols])
    pts = pd.read_parquet(folder / "points.parquet").set_index("id")
    info = info.join(pts[["lat", "lon", "elev", "paw_mm"]], on="point")
    return X, Y, P, info


def rmse(e):
    e = np.asarray(e, float)
    e = e[np.isfinite(e)]
    return float(np.sqrt(np.mean(e ** 2))) if len(e) else np.nan


def r2(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    ok = np.isfinite(y) & np.isfinite(p)
    y, p = y[ok], p[ok]
    return float(1 - np.mean((p - y) ** 2) / np.var(y)) if len(y) > 2 and np.var(y) > 0 else np.nan


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)
    print("figure:", name)
