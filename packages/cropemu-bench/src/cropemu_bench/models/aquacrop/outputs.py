"""Readers of AquaCrop v7 outputs (``OUTP/<project>PROseason.OUT``, ``...PROday.OUT``)."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd


def _unique(names: list) -> list:
    seen, out = {}, []
    for n in names:
        k = seen.get(n, 0)
        out.append(n if k == 0 else f"{n}_{k + 1}")
        seen[n] = k + 1
    return out


def read_season(path) -> pd.DataFrame:
    """Season totals (one row per run): every column of the season file, plus ``RunNr``."""
    lines = Path(path).read_text(encoding="latin-1").splitlines()
    i = next(k for k, s in enumerate(lines) if s.strip().startswith("RunNr"))
    names = _unique(lines[i].split())
    rows = []
    for s in lines[i + 2:]:
        t = s.split()
        if not t or not t[0].startswith("Tot"):
            continue
        vals = [t[0]] + [float(x) for x in t[1:len(names)]]
        rows.append(dict(zip(names, vals)))
    return pd.DataFrame(rows)


def read_daily(path) -> pd.DataFrame:
    """Daily table of a single-run project (every selected output group)."""
    lines = Path(path).read_text(encoding="latin-1").splitlines()
    i = next(k for k, s in enumerate(lines) if s.strip().startswith("Day Month"))
    header = re.sub(r"\b(WC|ECe) (\d)\b", r"\1\2", lines[i])
    names = _unique(header.split())
    data = [s.split() for s in lines[i + 2:] if s.strip()]
    data = [r[:len(names)] for r in data if len(r) >= len(names)]
    return pd.DataFrame(np.array(data, dtype=float), columns=names)


#: Daily fluxes summed over the crop period (sowing to maturity).
FLUXES = ("Rain", "Irri", "Infilt", "RO", "Drain", "CR", "E", "Tr", "ET", "ETo", "GD")
#: Daily stress indices averaged over the crop period (%).
STRESSES = ("StExp", "StSto", "StSen", "StTr")


def crop_period_summary(daily: pd.DataFrame) -> dict:
    """Development dates (days after sowing), crop-period totals, means and maxima from the daily table.

    Stage codes (``run.f90``): 1 sown to emergence, 2 vegetative, 3 flowering, 4 yield
    formation, 0 before/after the crop, -9 no growth stage. ``MAT_dap`` is the last day of
    the crop cycle; ``matured`` is False when the run ended before it (censored season).
    """
    d = daily[daily["DAP"] > 0]
    crop = d[d["Stage"].isin([1, 2, 3, 4])]
    # after the crop cycle AquaCrop writes DAP = -9 and Stage 0
    out = {}
    first = lambda st: float(crop.loc[crop["Stage"] == st, "DAP"].min()) if (crop["Stage"] == st).any() else np.nan
    out["EMR_dap"] = first(2)
    out["FLO_dap"] = first(3)
    out["YLD_dap"] = first(4)
    out["MAT_dap"] = float(crop["DAP"].max()) if len(crop) else np.nan
    out["matured"] = bool(len(crop) and (daily.loc[crop.index[-1] + 1:, "Stage"] == 0).any())
    for c in FLUXES:
        if c in crop:
            out[f"{c}_crop"] = float(crop[c].sum())
    for c in STRESSES:
        if c in crop:
            out[f"{c}_mean"] = float(crop[c].clip(lower=0).mean())
    for c in ("CC", "Z"):                          # final biomass, HI and yield are in the season file
        if c in crop:
            out[f"{c}_max"] = float(crop[c].max())
    return out
