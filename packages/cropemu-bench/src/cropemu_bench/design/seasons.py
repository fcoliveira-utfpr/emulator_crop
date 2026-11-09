"""Design of the simulated seasons: one Latin hypercube per point.

Each sampled season has its own year, sowing date (GGCMI planting day + offset),
cultivar (maturity group around the typical MG of the latitude + coefficient
perturbations), water regime and, for a share of seasons, a climate perturbation
(ΔT, rain factor, CO2). Everything else is fixed (see :class:`SeasonDesign`).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd
from scipy.stats import qmc

from ..models.dssat._fmt import code
from .cultivars import MG_MAX, MG_MIN, PERTURBATIONS, MGTable, cultivar_from_mg, mg_center


@dataclass
class SeasonDesign:
    seasons_per_point: int = 20
    first_year: int = 1985           # NASA POWER radiation starts in 1984; leave room for the start date
    last_year: int = 2024            # sowing year; maturity may fall in 2025
    sowing_half_width: int = 30      # days around the GGCMI planting day
    mg_half_width: float = 2.0       # MG sampled in mg_center(lat) ± this
    potential_share: float = 0.2     # seasons without water stress (water balance off)
    perturbed_share: float = 0.3     # seasons with a climate perturbation
    dt_range: tuple = (-1.0, 4.0)    # °C added to TMAX and TMIN
    rain_factor_range: tuple = (0.7, 1.3)
    co2_range: tuple = (350.0, 800.0)
    initial_water: float = 0.5       # fixed: unknown to library users
    population: float = 30.0         # fixed, plants/m²
    row_spacing: int = 50            # fixed, cm
    start_days_before_sowing: int = 30
    seed: int = 20261108
    perturbed_coefficients: tuple = field(default_factory=lambda: tuple(PERTURBATIONS))


def design_seasons(points: pd.DataFrame, calendar: pd.DataFrame, table: MGTable,
                   design: SeasonDesign = SeasonDesign()) -> tuple[pd.DataFrame, list]:
    """Sampled seasons of every point.

    ``points`` has ``id`` and ``lat``; ``calendar`` (from ``CropCalendar.table``) has
    ``id`` and ``planting_doy``. Points without a calendar are skipped.
    Returns the design table (one row per season, with every input that varies)
    and the list of cultivars to write (IDs ``Z`` + 5 base-36 characters).
    """
    cal = calendar.set_index("id")["planting_doy"]
    names = ["year", "sowing", "mg", "regime", "perturbed", "dt", "rain", "co2", *design.perturbed_coefficients]
    rows, cultivars = [], []
    for k, p in enumerate(points.itertuples()):
        doy = cal.get(p.id, np.nan)
        if not np.isfinite(doy):
            continue
        u = qmc.LatinHypercube(d=len(names), seed=design.seed + k).random(design.seasons_per_point)
        u = pd.DataFrame(u, columns=names)
        years = design.first_year + np.floor(u["year"] * (design.last_year - design.first_year + 1)).astype(int)
        offsets = np.round((u["sowing"] * 2 - 1) * design.sowing_half_width).astype(int)
        mgs = np.clip(mg_center(p.lat) + (u["mg"] * 2 - 1) * design.mg_half_width, MG_MIN, MG_MAX)
        for s in range(design.seasons_per_point):
            sid = len(rows)
            sowing = date(int(years[s]), 1, 1) + timedelta(days=min(int(doy), 365) - 1 + int(offsets[s]))
            perturbed = bool(u.loc[s, "perturbed"] < design.perturbed_share)
            cid = "Z" + code(sid, 5)
            cul = cultivar_from_mg(table, cid, float(mgs[s]),
                                   {c: u.loc[s, c] for c in design.perturbed_coefficients})
            cultivars.append(cul)
            lo_dt, hi_dt = design.dt_range
            lo_r, hi_r = design.rain_factor_range
            lo_c, hi_c = design.co2_range
            rows.append({"sample": sid, "point": p.id, "year": int(years[s]), "sowing": sowing,
                         "sowing_offset": int(offsets[s]), "mg": float(mgs[s]), "cultivar": cid,
                         "ecotype": cul.ecotype, "water": bool(u.loc[s, "regime"] >= design.potential_share),
                         "perturbed": perturbed,
                         "dt": lo_dt + u.loc[s, "dt"] * (hi_dt - lo_dt) if perturbed else 0.0,
                         "rain_factor": lo_r + u.loc[s, "rain"] * (hi_r - lo_r) if perturbed else 1.0,
                         "co2": lo_c + u.loc[s, "co2"] * (hi_c - lo_c) if perturbed else np.nan,
                         **cul.coefficients})
    table_ = pd.DataFrame(rows)
    table_.attrs["design"] = asdict(design)
    return table_, cultivars


def to_treatments(seasons: pd.DataFrame, soil_ids: dict, design: SeasonDesign = SeasonDesign()) -> list:
    """DSSAT treatments of the design table (weather key = point id; soil from ``soil_ids``)."""
    from ..models.dssat import EnvironmentModification, Treatment

    out = []
    for r in seasons.itertuples():
        env = None
        if r.perturbed:
            env = EnvironmentModification(tmax_add=r.dt, tmin_add=r.dt, rain_factor=r.rain_factor, co2=r.co2)
        out.append(Treatment(r.point, soil_ids[r.point], r.cultivar, r.sowing,
                             start=r.sowing - timedelta(days=design.start_days_before_sowing),
                             water=bool(r.water), initial_water=design.initial_water,
                             population=design.population, row_spacing=design.row_spacing,
                             environment=env, name=f"S{r.sample}"))
    return out
