"""Emulator training tables (X, Y) from a generated simulation dataset (see ``pipeline``)."""

from __future__ import annotations

import json
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
#: Ratio outputs computed from predicted outputs instead of emulated: name -> (numerator,
#: denominator, factor). Per-mm-of-rain ratios explode where the season rain is near zero
#: (up to ~80,000 kg/ha/mm in deserts), which no regression learns; computed from the
#: predicted yield/biomass and rain their median error is ~40x smaller (plan, 4.7).
#: The other ratios (YPEM, HIAM, HWUM...) are emulated better directly.
DERIVED = {"YPPM": ("HWAM", "PRCP", 1.0), "DMPPM": ("CWAM", "PRCP", 1.0)}
#: Smallest denominator used for derived ratios (mm of rain).
DERIVED_FLOOR = 1.0


def _doy_date(v) -> date | None:
    if not np.isfinite(v):
        return None
    v = int(v)
    return date(v // 1000, 1, 1) + pd.Timedelta(days=v % 1000 - 1)


def targets(summary: pd.DataFrame, min_valid: float = 0.5, derived: bool = False) -> pd.DataFrame:
    """Every numeric Summary.OUT output that varies, indexed by ``sample``.

    Dates become days after planting (``EDAT_dap``...). Missing values (e.g. no
    maturity) stay NaN: emulators must mask them. When the crop ended before maturity
    (``CRST`` != 1, e.g. 39 early end, 32 cold kill) DSSAT writes the end date as MDAT;
    it is set to NaN (censored), the status is a classifier target (:func:`labels`). Columns with fewer than
    ``min_valid`` non-missing values or no variance are dropped. The :data:`DERIVED`
    ratios are left out unless ``derived`` is True (they are computed with :func:`derive`).
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
        if (c in NOT_TARGETS or c in DATE_TARGETS or (c in DERIVED and not derived)
                or not pd.api.types.is_numeric_dtype(s[c])):
            continue
        out[c] = s[c].astype(float)
    y = pd.DataFrame(out, index=s.index)
    if "CRST" in s and "MDAT_dap" in y:
        y.loc[s["CRST"].to_numpy() != 1, "MDAT_dap"] = np.nan
    keep = [c for c in y if y[c].notna().mean() >= min_valid and y[c].std(skipna=True) > 0]
    return y[keep]


#: DSSAT end-of-season crop status codes (``CRST``; CROPGRO RStages/GROW, CERES GROSUB).
CROP_STATUS = {1: "matured", 32: "cold_kill", 33: "water_kill", 39: "ended_before_maturity"}


def labels(summary: pd.DataFrame, model: str = "dssat") -> pd.DataFrame:
    """Categorical outputs, by ``sample``: ``matured`` (bool) and, for DSSAT, ``crop_status``."""
    s = summary.set_index("sample")
    if model == "aquacrop":
        return pd.DataFrame({"matured": s["matured"].fillna(False).astype(bool)}, index=s.index)
    st = s["CRST"].map(lambda v: CROP_STATUS.get(int(v), f"code_{int(v)}") if pd.notna(v) else "missing")
    return pd.DataFrame({"matured": (s["CRST"] == 1).to_numpy(), "crop_status": st.to_numpy()}, index=s.index)


#: AquaCrop summary columns that are dates of the simulation period, flags or errors.
AQ_NOT_TARGETS = {"Day1", "Month1", "Year1", "DayN", "MonthN", "YearN", "error", "matured", "germination_delay"}


def targets_aquacrop(summary: pd.DataFrame, min_valid: float = 0.5) -> pd.DataFrame:
    """Every numeric AquaCrop output that varies (season file + crop-period summary), by ``sample``.

    The maturity day is NaN for seasons that did not reach maturity (censored), as in DSSAT.
    """
    s = summary.set_index("sample")
    y = pd.DataFrame({c: s[c].astype(float) for c in s.columns
                      if c not in AQ_NOT_TARGETS and pd.api.types.is_numeric_dtype(s[c])
                      and not pd.api.types.is_bool_dtype(s[c])}, index=s.index)
    if "matured" in s and "MAT_dap" in y:
        y.loc[~s["matured"].fillna(False).astype(bool), "MAT_dap"] = np.nan
    y = y.where(y > -9)                               # AquaCrop writes -9 / -9.9 for undefined values
    keep = [c for c in y if y[c].notna().mean() >= min_valid and y[c].std(skipna=True) > 0]
    return y[keep]


def model_of(out_dir) -> str:
    """``"aquacrop"`` or ``"dssat"``, from the dataset's ``meta.json``."""
    meta = Path(out_dir) / "meta.json"
    if meta.exists() and json.loads(meta.read_text()).get("model", "").lower().startswith("aquacrop"):
        return "aquacrop"
    return "dssat"


def derive(P: pd.DataFrame) -> pd.DataFrame:
    """The :data:`DERIVED` ratios computed from predicted outputs (columns added to a copy of ``P``)."""
    P = P.copy()
    for name, (num, den, f) in DERIVED.items():
        if num in P and den in P:
            P[name] = f * P[num].clip(lower=0) / P[den].clip(lower=DERIVED_FLOOR)
    return P


def aquacrop_thermal(r) -> tuple[dict, float, float]:
    """Thermal requirements of an AquaCrop design row (FAO SoybeanGDD scaled by the cycle):
    emergence, flowering, start of senescence and maturity (GDD), Tbase, Tupper."""
    f = float(r["gdd_maturity"]) / 2700.0
    return ({"td_emergence": 200.0, "td_flowering": 1500.0 * f, "td_senescence": 2200.0 * f,
             "td_maturity": float(r["gdd_maturity"])}, 5.0, 30.0)


def features(design: pd.DataFrame, points: pd.DataFrame, cultivar_features=CULTIVAR_FEATURES,
             thermal=None, water: bool = True, initial_water: float = 0.5) -> pd.DataFrame:
    """Emulator inputs of every season (index ``sample``): site, soil, weather windows,
    water balance (window ETo and bucket stress, with ``water``), cultivar, water regime,
    CO2 and, with ``thermal`` (row -> (requirements, tbase, tupper)), the days after sowing
    to accumulate each thermal requirement. Weather and soil are read from the cropemu cache."""
    pts = points.set_index("id")
    rows = []
    for pid, seasons in design.groupby("point", sort=False):
        p = pts.loc[pid]
        w = WeatherSeries(fill_gaps(fetch(p["lat"], p["lon"], WEATHER_START, WEATHER_END)), p["lat"], p["elev"])
        soil = soil_features(hydraulics(soilgrids.fetch(p["lat"], p["lon"])))
        site = site_features(p["lat"], p["elev"])
        for r in seasons.to_dict("records"):          # dicts keep names like "EM-FL"
            # CO2 of the season: the replaced value, or Mauna Loa ~60 days after sowing
            co2 = r["co2"] if r["perturbed"] else co2_at(pd.Timestamp(r["sowing"]) + pd.Timedelta(days=60))
            rec = {"sample": r["sample"], **site, **soil,
                   **season_features(w, r["sowing"], r["dt"], r["rain_factor"],
                                     paw_mm=soil["paw_mm"] if water else None, initial_water=initial_water),
                   **{c: float(r[c]) for c in cultivar_features},
                   "water": float(r["water"]), "co2": float(co2)}
            if thermal is not None:
                req, tb, tu = thermal(r)
                rec.update(w.thermal_days(r["sowing"], req, tb, tu, dt=r["dt"]))
            rows.append(rec)
    return pd.DataFrame(rows).set_index("sample")


#: AquaCrop: germination later than this many days after the thermal-time estimate is a
#: failed/delayed establishment (classifier output); the dates of those seasons are censored.
DELAYED_GERMINATION_DAYS = 10
AQ_DATES = ("EMR_dap", "FLO_dap", "YLD_dap", "MAT_dap")


def build(out_dir, cache: bool = True, derived: bool = False,
          features_file: str = "features.parquet") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """X (features), Y (targets) and ``info`` (point, block, koppen, kind and the
    categorical outputs of :func:`labels`) of a dataset, aligned on ``sample``. Features are cached in ``<out_dir>/<features_file>``
    (another file, e.g. an older feature set, is read as is).
    With ``derived``, Y also has the true :data:`DERIVED` ratios (to evaluate :func:`derive`)."""
    out = Path(out_dir)
    model = model_of(out)
    t = load(out)
    design = t["design"]
    done = t["summary"]["sample"].unique()
    design = design[design["sample"].isin(done)]
    fpath = out / features_file
    if cache and fpath.exists():
        X = pd.read_parquet(fpath)
    else:
        if model == "aquacrop":
            from .design.aquacrop import AQ_PERTURBATIONS
            X = features(design, t["points"], ("cycle_factor", "gdd_maturity", *AQ_PERTURBATIONS),
                         thermal=aquacrop_thermal)
        else:
            X = features(design, t["points"], CULTIVAR_FEATURES)
        X.to_parquet(fpath)
    Y = targets_aquacrop(t["summary"]) if model == "aquacrop" else targets(t["summary"], derived=derived)
    info = design.set_index("sample")[["point"]].join(
        t["points"].set_index("id")[["block", "koppen", "kind"]], on="point").join(labels(t["summary"], model))
    idx = X.index.intersection(Y.index)
    X, Y, info = X.loc[idx], Y.loc[idx].copy(), info.loc[idx].copy()
    if model == "aquacrop" and "td_emergence" in X and "EMR_dap" in Y:
        delay = Y["EMR_dap"] - X["td_emergence"]
        delayed = (delay > DELAYED_GERMINATION_DAYS) | Y["EMR_dap"].isna()
        info["delayed_germination"] = delayed.to_numpy()
        Y.loc[delayed, [c for c in AQ_DATES if c in Y]] = np.nan
    return X, Y, info
