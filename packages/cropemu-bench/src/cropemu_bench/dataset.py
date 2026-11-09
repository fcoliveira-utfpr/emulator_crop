"""Emulator training tables (X, Y) from a generated simulation dataset (see ``pipeline``)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from cropemu.features import WeatherSeries, co2_at, season_features, site_features, soil_features
from cropemu.soil import hydraulics, soilgrids
from cropemu.weather import fetch, fill_gaps

from .design.cultivars import PERTURBATIONS
from .pipeline import WEATHER_END, WEATHER_START, load

#: Summary.OUT columns that are identifiers or inputs, not model outputs.
NOT_TARGETS = {"RUNNO", "TRNO", "R#", "O#", "P#", "CR", "MODEL", "EXNAME", "TNAM", "FNAM", "WSTA", "WYEAR",
               "SOIL_ID", "XLAT", "LONG", "ELEV", "SDAT", "PDAT", "HYEAR"}
#: Categorical outputs (codes): left to classifiers, not regression targets.
CATEGORICAL = {"CRST"}
NOT_TARGETS |= CATEGORICAL
#: Date outputs (YYYYDDD) converted to days after planting.
DATE_TARGETS = ("EDAT", "ADAT", "MDAT", "HDAT")
CULTIVAR_FEATURES = ("mg",) + tuple(PERTURBATIONS)


def _doy_date(v) -> date | None:
    if not np.isfinite(v):
        return None
    v = int(v)
    return date(v // 1000, 1, 1) + pd.Timedelta(days=v % 1000 - 1)


def targets(summary: pd.DataFrame, min_valid: float = 0.5) -> pd.DataFrame:
    """Every numeric Summary.OUT output that varies, indexed by ``sample``.

    Dates become days after planting (``EDAT_dap``...). Missing values (e.g. no
    maturity) stay NaN: emulators must mask them. Columns with fewer than
    ``min_valid`` non-missing values or no variance are dropped.
    """
    s = summary.set_index("sample")
    planting = s["PDAT"].map(_doy_date)
    out = {}
    for c in DATE_TARGETS:
        if c in s:
            d = s[c].map(_doy_date)
            out[f"{c}_dap"] = [(a - p).days if a is not None and p is not None else np.nan
                               for a, p in zip(d, planting)]
    for c in s.columns:
        if c in NOT_TARGETS or c in DATE_TARGETS or not pd.api.types.is_numeric_dtype(s[c]):
            continue
        out[c] = s[c].astype(float)
    y = pd.DataFrame(out, index=s.index)
    keep = [c for c in y if y[c].notna().mean() >= min_valid and y[c].std(skipna=True) > 0]
    return y[keep]


def features(design: pd.DataFrame, points: pd.DataFrame) -> pd.DataFrame:
    """Emulator inputs of every season (index ``sample``): site, soil, weather windows,
    cultivar, water regime, CO2. Weather and soil are read from the cropemu cache."""
    pts = points.set_index("id")
    rows = []
    for pid, seasons in design.groupby("point", sort=False):
        p = pts.loc[pid]
        w = WeatherSeries(fill_gaps(fetch(p["lat"], p["lon"], WEATHER_START, WEATHER_END)), p["lat"])
        soil = soil_features(hydraulics(soilgrids.fetch(p["lat"], p["lon"])))
        site = site_features(p["lat"], p["elev"])
        for r in seasons.to_dict("records"):          # dicts keep names like "EM-FL"
            # CO2 of the season: the replaced value, or Mauna Loa ~60 days after sowing
            co2 = r["co2"] if r["perturbed"] else co2_at(pd.Timestamp(r["sowing"]) + pd.Timedelta(days=60))
            rows.append({"sample": r["sample"], **site, **soil,
                         **season_features(w, r["sowing"], r["dt"], r["rain_factor"]),
                         **{c: float(r[c]) for c in CULTIVAR_FEATURES},
                         "water": float(r["water"]), "co2": float(co2)})
    return pd.DataFrame(rows).set_index("sample")


def build(out_dir, cache: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """X (features), Y (targets) and ``info`` (point, block, koppen, kind) of a dataset,
    aligned on ``sample``. Features are cached in ``<out_dir>/features.parquet``."""
    out = Path(out_dir)
    t = load(out)
    design = t["design"]
    done = t["summary"]["sample"].unique()
    design = design[design["sample"].isin(done)]
    fpath = out / "features.parquet"
    if cache and fpath.exists():
        X = pd.read_parquet(fpath)
    else:
        X = features(design, t["points"])
        X.to_parquet(fpath)
    Y = targets(t["summary"])
    info = design.set_index("sample")[["point"]].join(
        t["points"].set_index("id")[["block", "koppen", "kind"]], on="point")
    idx = X.index.intersection(Y.index)
    return X.loc[idx], Y.loc[idx], info.loc[idx]
