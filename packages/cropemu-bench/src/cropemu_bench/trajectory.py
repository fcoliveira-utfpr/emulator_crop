"""Daily trajectories as emulator targets: curve shapes in phenological time.

Phenological time ``tau`` is 0 at emergence, 1 at flowering and 2 at maturity (linear in days within
each phase). Each growth curve is sampled at :data:`GRID` (``PHASE_POINTS`` per phase, 23 points) and
divided by its season value (leaf area by its maximum, biomass and grain by their final value), so the
emulated curve is ``shape x emulated season output`` placed on days by the emulated dates, and stays
coherent with the season outputs. The water stress (0 none .. 1 full) is the mean over each of the
22 intervals of the grid (it changes from day to day). Seasons that do not reach maturity have NaN
targets (masked in training); see ``planing.md`` 5.2.3 for the pilot that chose this representation.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .dataset import model_of
from .pipeline import load

PHASE_POINTS = 12
GRID = np.concatenate([np.linspace(0, 1, PHASE_POINTS), np.linspace(1, 2, PHASE_POINTS)[1:]])

#: per model: daily table, growth curves as {daily column: (name, season column used as scale)},
#: water stress (daily column, divisor to 0..1), emulator outputs of emergence/flowering/maturity
#: (days after sowing).
SPECS = {
    "dssat": dict(table="daily_PlantGro", stress=("WSPD", 1.0), dates=("EDAT_dap", "ADAT_dap", "MDAT_dap"),
                  growth={"LAID": ("leaf", "LAIX"), "CWAD": ("biomass", "CWAM"), "GWAD": ("grain", "HWAM")}),
    "aquacrop": dict(table="daily_day", stress=("StSto", 100.0), dates=("EMR_dap", "FLO_dap", "MAT_dap"),
                     growth={"CC": ("leaf", "CC_max"), "Biomass": ("biomass", "BioMass"),
                             "Y(dry)": ("grain", "Y(dry)")}),
}


def target_names(model: str) -> list[str]:
    """Column names of the trajectory targets: ``<curve>_t00..t22`` and ``stress_b00..b21``."""
    names = [f"{n}_t{i:02d}" for n, _ in SPECS[model]["growth"].values() for i in range(len(GRID))]
    return names + [f"stress_b{i:02d}" for i in range(len(GRID) - 1)]


def season_dates(summary: pd.DataFrame, model: str) -> pd.DataFrame:
    """Emergence ``E``, flowering ``A`` and maturity ``M`` in days after sowing (index ``sample``),
    in the day convention of the model's daily table."""
    s = summary.set_index("sample")
    if model == "aquacrop":
        return s[["EMR_dap", "FLO_dap", "MAT_dap"]].set_axis(["E", "A", "M"], axis=1).astype(float)
    pdat = pd.to_datetime(s["PDAT"].astype("Int64").astype(str), format="%Y%j", errors="coerce")
    out = {n: (pd.to_datetime(s[c].astype("Int64").astype(str), format="%Y%j", errors="coerce") - pdat).dt.days
           for c, n in (("EDAT", "E"), ("ADAT", "A"), ("MDAT", "M"))}
    return pd.DataFrame(out, index=s.index).astype(float)


def phen_time(dap, e, a, m):
    """Days after sowing -> phenological time (0 emergence, 1 flowering, 2 maturity)."""
    dap = np.asarray(dap, float)
    return np.where(dap <= a, (dap - e) / max(a - e, 1), 1 + (dap - a) / max(m - a, 1))


def season_targets(day: pd.DataFrame, dates, scales: dict, model: str) -> np.ndarray:
    """Targets of one season (``day``: its daily rows, sorted by DAP)."""
    spec = SPECS[model]
    n = len(GRID)
    out = np.full(len(spec["growth"]) * n + n - 1, np.nan)
    e, a, m = dates
    if not (np.isfinite([e, a, m]).all() and e < a < m):
        return out
    g = day[(day["DAP"] >= e) & (day["DAP"] <= m)]
    if model == "aquacrop":                  # last day: AquaCrop sets CC to 0 (end of cycle, not senescence)
        g = g.iloc[:-1]
    if len(g) < 10:
        return out
    tau = phen_time(g["DAP"].to_numpy(), e, a, m)
    for k, (col, (_, scale_col)) in enumerate(spec["growth"].items()):
        y = g[col].to_numpy(float)
        scale = scales[scale_col]
        if np.isnan(y).any() or not np.isfinite(scale) or scale <= 0:
            continue
        out[k * n:(k + 1) * n] = np.interp(GRID, tau, y) / scale
    col, div = spec["stress"]
    w = np.clip(np.nan_to_num(g[col].to_numpy(float)) / div, 0, 1)
    idx = np.clip(np.digitize(tau, GRID) - 1, 0, n - 2)
    counts = np.bincount(idx, minlength=n - 1)
    sums = np.bincount(idx, weights=w, minlength=n - 1)
    filled = counts > 0
    means = np.full(n - 1, np.nan)
    means[filled] = sums[filled] / counts[filled]
    if (~filled).any() and filled.any():     # short phases: an interval without a day takes its neighbours'
        means = np.interp(np.arange(n - 1), np.flatnonzero(filled), means[filled])
    out[len(spec["growth"]) * n:] = means
    return out


def trajectory_targets(out_dir, cache: bool = True, file: str = "trajectory_targets.parquet") -> pd.DataFrame:
    """Trajectory targets of every season of a dataset with daily tables (index ``sample``),
    cached in ``<out_dir>/<file>``."""
    out = Path(out_dir)
    fpath = out / file
    if cache and fpath.exists():
        return pd.read_parquet(fpath)
    model = model_of(out)
    spec = SPECS[model]
    t = load(out)
    if spec["table"] not in t:
        raise FileNotFoundError(f"{out} has no {spec['table']} (generate with daily=TRAJECTORY_COLUMNS)")
    summary = t["summary"]
    dates = season_dates(summary, model)
    scale_cols = [c for _, c in spec["growth"].values()]
    scales = summary.set_index("sample")[scale_cols].astype(float)   # same units as the daily columns
    cols = ["sample", "DAP", *spec["growth"], spec["stress"][0]]
    day = t[spec["table"]][cols].sort_values(["sample", "DAP"])
    rows, index = [], []
    for sid, g in day.groupby("sample", sort=True):
        if sid not in dates.index:
            continue
        rows.append(season_targets(g, dates.loc[sid].to_numpy(), scales.loc[sid].to_dict(), model))
        index.append(sid)
    T = pd.DataFrame(np.vstack(rows), index=pd.Index(index, name="sample"), columns=target_names(model))
    T.to_parquet(fpath)
    return T


def curves(shapes: pd.DataFrame, season: pd.DataFrame, dates: pd.DataFrame, model: str) -> dict:
    """Daily curves from predicted shapes: ``{curve: DataFrame (sample x day after sowing)}``.

    ``shapes``: predicted targets (:func:`target_names`); ``season``: the season outputs used as
    scales (e.g. ``LAIX``, ``CWAM``, ``HWAM``); ``dates``: ``E``, ``A``, ``M`` in days after sowing.
    """
    spec = SPECS[model]
    n = len(GRID)
    days = np.arange(0, int(np.nanmax(dates["M"])) + 1)
    out = {}
    for k, (name, scale_col) in enumerate(spec["growth"].values()):
        rows = []
        for sid in shapes.index:
            e, a, m = dates.loc[sid, ["E", "A", "M"]]
            tau = phen_time(days, e, a, m)
            shape = shapes.loc[sid].to_numpy()[k * n:(k + 1) * n]
            y = np.interp(tau, GRID, shape, left=0.0, right=np.nan) * season.loc[sid, scale_col]
            rows.append(np.where(days <= m, y, np.nan))
        out[name] = pd.DataFrame(rows, index=shapes.index, columns=days)
    return out


def card_entry(model: str, metrics: pd.DataFrame | None = None) -> dict:
    """``card["trajectory"]`` of an exported emulator: how to turn the shapes into daily curves."""
    spec = SPECS[model]
    out = {"description": "curve shapes in phenological time (0 emergence, 1 flowering, 2 maturity, linear in "
                          "days within each phase): growth curves at the grid points divided by the season "
                          "output named in 'curves'; water stress (0 none to 1 full) as the mean of each "
                          "grid interval",
           "grid": [float(g) for g in GRID], "phase_points": PHASE_POINTS,
           "curves": {name: {"daily": col, "scale": scale} for col, (name, scale) in spec["growth"].items()},
           "stress": {"daily": spec["stress"][0], "intervals": len(GRID) - 1},
           "dates": dict(zip(("emergence", "flowering", "maturity"), spec["dates"]))}
    if metrics is not None:
        m = metrics[metrics["part"] == "all"].set_index("curve")
        out["validation"] = {c: {"rmse": float(r["rmse"]), "r2": float(r["r2"])} for c, r in m.iterrows()}
    return out
