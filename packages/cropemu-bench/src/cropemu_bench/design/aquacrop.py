"""AquaCrop seasons: the same seasons as the DSSAT design, with AquaCrop crop parameters.

The year, sowing date, water regime and climate perturbation of every season are
taken from the DSSAT design, so both models are compared on identical seasons.
AquaCrop's soybean has no photoperiod response: the crop cycle is a thermal time.
The role of the maturity group is played by a cycle length fitted to the local
calendar, as in GGCMI: the GDD from the GGCMI planting to the GGCMI maturity day
(mean of 1985-2024) times a factor that follows the sampled MG relative to the
typical MG of the latitude (MG ±2 -> factor 0.75-1.25). Other crop parameters are
perturbed in provisional ranges (plan, 4.1.4; to be replaced by literature ranges).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import qmc

from ..models.aquacrop.crop import CropFile
from .cultivars import mg_center

#: AquaCrop crop parameter -> (kind, low, high): "set" absolute value, "mul" factor applied after
#: the cycle scaling (the design stores the factor).
AQ_PERTURBATIONS = {
    "ccx": ("set", 0.80, 0.99),
    "cgc_gdd": ("mul", 0.8, 1.2),
    "cdc_gdd": ("mul", 0.8, 1.2),
    "wp": ("set", 13.0, 18.0),
    "hio": ("set", 30.0, 48.0),
    "zmax": ("set", 1.0, 2.0),
    "kctr": ("set", 1.00, 1.15),
    "p_exp_upper": ("set", 0.10, 0.20),
    "p_exp_lower": ("set", 0.55, 0.75),
    "p_sto": ("set", 0.45, 0.70),
    "p_sen": ("set", 0.60, 0.80),
}
#: Cycle factor per MG unit away from the typical MG of the latitude.
CYCLE_PER_MG = 0.125
#: Fixed: plants per hectare (30 plants/m², as in the DSSAT design).
PLANTS = 300_000


def gdd(tmax, tmin, tbase: float, tupper: float) -> np.ndarray:
    """Daily growing degrees as AquaCrop (method 3): temperatures capped at ``tupper``,
    Tmax floored at ``tbase``, mean floored at ``tbase``."""
    tx = np.clip(tmax, tbase, tupper)
    tn = np.minimum(tmin, tupper)
    return np.maximum((tx + tn) / 2 - tbase, 0.0)


def climatological_gdd(weather: pd.DataFrame, planting_doy: int, maturity_doy: int, tbase: float,
                       tupper: float, years=range(1985, 2025)) -> float:
    """Mean GDD from the planting to the maturity day of the calendar (season may cross the year)."""
    g = pd.Series(gdd(weather["tmax"].to_numpy(float), weather["tmin"].to_numpy(float), tbase, tupper),
                  index=weather.index)
    length = (maturity_doy - planting_doy) % 365 or 365
    sums = []
    for y in years:
        s = pd.Timestamp(y, 1, 1) + pd.Timedelta(days=min(int(planting_doy), 365) - 1)
        e = s + pd.Timedelta(days=int(length))
        if e <= g.index[-1]:
            sums.append(g.loc[s:e].sum())
    return float(np.mean(sums))


def aquacrop_design(dssat_design: pd.DataFrame, points: pd.DataFrame, gdd_clim: dict,
                    seed: int = 20261109) -> pd.DataFrame:
    """AquaCrop parameters of every season of the DSSAT design.

    ``gdd_clim``: point id -> climatological GDD of the calendar season. Returns the DSSAT
    design columns shared by both models plus ``cycle_factor``, ``gdd_maturity`` and the
    perturbed AquaCrop parameters.
    """
    lat = points.set_index("id")["lat"]
    keep = ["sample", "point", "year", "sowing", "sowing_offset", "mg", "water", "perturbed",
            "dt", "rain_factor", "co2", "planting_doy"]
    d = dssat_design[keep].copy()
    rel = d["mg"].to_numpy() - mg_center(d["point"].map(lat).to_numpy())
    d["cycle_factor"] = 1 + CYCLE_PER_MG * np.clip(rel, -2, 2)
    d["gdd_maturity"] = d["point"].map(gdd_clim).to_numpy() * d["cycle_factor"]
    names = list(AQ_PERTURBATIONS)
    parts = []
    for k, (pid, g) in enumerate(d.groupby("point", sort=False)):
        u = qmc.LatinHypercube(d=len(names), seed=seed + k).random(len(g))
        vals = {}
        for j, n in enumerate(names):
            kind, lo, hi = AQ_PERTURBATIONS[n]
            x = lo + u[:, j] * (hi - lo)
            vals[n] = x
        parts.append(pd.DataFrame(vals, index=g.index))
    return pd.concat([d, pd.concat(parts)], axis=1)


def season_crop(base: CropFile, row) -> CropFile:
    """The crop file of one design row."""
    c = base.copy()
    c.scale_cycle(float(row["gdd_maturity"]) / base["gdd_maturity"])
    for n, (kind, _, _) in AQ_PERTURBATIONS.items():
        c[n] = c[n] * float(row[n]) if kind == "mul" else float(row[n])
    c["plants"] = PLANTS
    return c
