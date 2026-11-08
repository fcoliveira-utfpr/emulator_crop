"""Pedotransfer functions and texture classes."""

from __future__ import annotations

import numpy as np
import pandas as pd


def saxton_rawls(sand, clay, om, bd=None):
    """Water retention and conductivity from texture (Saxton & Rawls 2006, SSSAJ 70:1569).

    Parameters are arrays: ``sand`` and ``clay`` in % (mass), ``om`` organic matter in %
    (mass), ``bd`` bulk density in g/cm³ (optional: with it, the density adjustment of
    the paper is applied). Returns ``ll`` (θ1500), ``dul`` (θ33), ``sat`` (θS) in
    cm³/cm³ and ``ksat`` in cm/h.
    """
    S, C = np.asarray(sand, float) / 100, np.asarray(clay, float) / 100
    OM = np.asarray(om, float)
    t1500 = -0.024 * S + 0.487 * C + 0.006 * OM + 0.005 * S * OM - 0.013 * C * OM + 0.068 * S * C + 0.031
    th1500 = t1500 + (0.14 * t1500 - 0.02)
    t33 = -0.251 * S + 0.195 * C + 0.011 * OM + 0.006 * S * OM - 0.027 * C * OM + 0.452 * S * C + 0.299
    th33 = t33 + (1.283 * t33**2 - 0.374 * t33 - 0.015)
    ts33 = 0.278 * S + 0.034 * C + 0.022 * OM - 0.018 * S * OM - 0.027 * C * OM - 0.584 * S * C + 0.078
    ths33 = ts33 + (0.636 * ts33 - 0.107)
    thS = th33 + ths33 - 0.097 * S + 0.043
    if bd is not None:                                  # density adjustment (eqs. 6-10)
        thS_df = 1 - np.asarray(bd, float) / 2.65
        th33 = th33 - 0.2 * (thS - thS_df)
        thS = thS_df
    B = (np.log(1500) - np.log(33)) / (np.log(th33) - np.log(th1500))
    lam = 1 / B
    ksat_mm_h = 1930 * np.clip(thS - th33, 1e-6, None) ** (3 - lam)
    return {"ll": th1500, "dul": th33, "sat": thS, "ksat": ksat_mm_h / 10}


def hydraulics(profile: pd.DataFrame, method: str = "soilgrids", min_gap: float = 0.02) -> pd.DataFrame:
    """Add ``ll``, ``dul``, ``sat`` and ``ksat`` to a standard soil profile.

    method
        ``"soilgrids"``: LL and DUL from the SoilGrids water retention maps
        (columns ``wv1500`` and ``wv0033``), saturation from bulk density and
        Ksat from Saxton & Rawls; layers without them fall back to Saxton & Rawls.
        ``"saxton_rawls"``: everything from texture, organic matter and density.

    The result always satisfies ``ll + min_gap <= dul`` and ``dul + min_gap <= sat``.
    """
    if method not in ("soilgrids", "saxton_rawls"):
        raise ValueError("method must be 'soilgrids' or 'saxton_rawls'")
    out = profile.copy()
    sr = saxton_rawls(out["sand"], out["clay"], out["soc"] * 1.724, out.get("bdod"))
    ll, dul, sat = sr["ll"], sr["dul"], sr["sat"]
    if method == "soilgrids" and {"wv1500", "wv0033"} <= set(out):
        ok = out["wv1500"].notna() & out["wv0033"].notna()
        ll = np.where(ok, out["wv1500"], ll)
        dul = np.where(ok, out["wv0033"], dul)
        if "bdod" in out:
            sat = np.where(ok & out["bdod"].notna(), 1 - out["bdod"] / 2.65, sat)
    ll = np.clip(ll, 0.01, 0.6)
    dul = np.maximum(dul, ll + min_gap)
    sat = np.maximum(sat, dul + min_gap)
    out["ll"], out["dul"], out["sat"], out["ksat"] = ll, dul, sat, sr["ksat"]
    return out


def texture_class(sand, clay) -> np.ndarray:
    """USDA texture class with DSSAT codes (S, LS, SL, L, SIL, SI, SCL, CL, SICL, SC, SIC, C).

    ``sand`` and ``clay`` in %; silt is the remainder.
    """
    sand, clay = np.asarray(sand, float), np.asarray(clay, float)
    silt = 100 - sand - clay
    conds = [
        silt + 1.5 * clay < 15,
        (silt + 1.5 * clay >= 15) & (silt + 2 * clay < 30),
        ((clay >= 7) & (clay < 20) & (sand > 52) & (silt + 2 * clay >= 30)) | ((clay < 7) & (silt < 50) & (silt + 2 * clay >= 30)),
        (clay >= 7) & (clay < 27) & (silt >= 28) & (silt < 50) & (sand <= 52),
        ((silt >= 50) & (clay >= 12) & (clay < 27)) | ((silt >= 50) & (silt < 80) & (clay < 12)),
        (silt >= 80) & (clay < 12),
        (clay >= 20) & (clay < 35) & (silt < 28) & (sand > 45),
        (clay >= 27) & (clay < 40) & (sand > 20) & (sand <= 45),
        (clay >= 27) & (clay < 40) & (sand <= 20),
        (clay >= 35) & (sand > 45),
        (clay >= 40) & (silt >= 40),
        (clay >= 40) & (sand <= 45) & (silt < 40),
    ]
    codes = ["S", "LS", "SL", "L", "SIL", "SI", "SCL", "CL", "SICL", "SC", "SIC", "C"]
    return np.select(conds, codes, default="-99")
