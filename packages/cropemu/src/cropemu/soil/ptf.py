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


def reichert(clay, silt, om, bd):
    """Water retention of southern Brazilian soils (Reichert et al. 2009, RBCS 33:1547, Table 4).

    ``clay``, ``silt`` and ``om`` (organic matter) in kg/kg, ``bd`` bulk density in g/cm³.
    The equations give gravimetric water (kg/kg), converted here to volumetric with ``bd``.
    Fitted on 725 samples from Rio Grande do Sul (OM <= 0.10 kg/kg; R² 0.56-0.67).
    Returns ``ll`` (θ1500), ``dul10`` (θ10 kPa) and ``dul33`` (θ33 kPa) in cm³/cm³.
    """
    C, CS = np.asarray(clay, float), np.asarray(clay, float) + np.asarray(silt, float)
    OM, BD = np.asarray(om, float), np.asarray(bd, float)
    w10 = 0.268 + 0.05 * C + 0.24 * CS + 0.85 * OM - 0.127 * BD
    w33 = 0.106 + 0.29 * CS + 0.93 * OM - 0.048 * BD
    w1500 = -0.04 + 0.15 * C + 0.17 * CS + 0.91 * OM + 0.026 * BD
    return {"ll": w1500 * BD, "dul10": w10 * BD, "dul33": w33 * BD}


#: Default water retention method (plan, 5.2.1; decision of 09/11/2026). The SoilGrids retention
#: maps give very little available water in clayey tropical soils (0.03 cm³/cm³ in a Paraná Oxisol
#: with 52 % clay); Saxton & Rawls, fitted on US soils, gives 0.10-0.12. "hybrid" uses the
#: Brazilian PTF of Reichert et al. (2009), with field capacity at 10 kPa (the usual value for
#: well-structured tropical soils), in the tropics and subtropics, and Saxton & Rawls elsewhere.
DEFAULT_METHOD = "hybrid"
METHODS = ("hybrid", "saxton_rawls", "reichert", "soilgrids")
#: Organic matter (%) above which Saxton & Rawls is not fitted (their data: OM <= 8 %); larger
#: values (organic topsoils, 24 % of the dssat_v1 points in some layer) are capped.
MAX_OM = 8.0
#: Same for Reichert et al. (2009): OM <= 10 %.
MAX_OM_REICHERT = 10.0
#: "hybrid": Reichert up to |lat| = HYBRID_LAT[0], Saxton & Rawls from HYBRID_LAT[1], a linear
#: blend between them (no jump in the soil inputs). Rio Grande do Sul spans 27-34 °S.
HYBRID_LAT = (30.0, 40.0)


def reichert_weight(lat: float) -> float:
    """Weight of Reichert et al. (2009) in the "hybrid" method at latitude ``lat``."""
    a, b = HYBRID_LAT
    return float(np.clip((b - abs(lat)) / (b - a), 0.0, 1.0))


def hydraulics(profile: pd.DataFrame, method: str = DEFAULT_METHOD, lat: float | None = None,
               min_gap: float = 0.02) -> pd.DataFrame:
    """Add ``ll``, ``dul``, ``sat`` and ``ksat`` to a standard soil profile.

    method
        ``"hybrid"`` (default): ``"reichert"`` in the tropics and subtropics (|lat| <= 30°),
        ``"saxton_rawls"`` from 40°, a linear blend between them (:data:`HYBRID_LAT`).
        ``lat`` defaults to ``profile.attrs["lat"]`` (set by :mod:`cropemu.soil.soilgrids`).
        ``"saxton_rawls"``: everything from texture, organic matter and density
        (Saxton & Rawls 2006, with the density adjustment).
        ``"reichert"``: LL (1500 kPa) and DUL (10 kPa) from Reichert et al. (2009);
        saturation and Ksat from Saxton & Rawls.
        ``"soilgrids"``: LL and DUL from the SoilGrids water retention maps
        (columns ``wv1500`` and ``wv0033``), saturation from bulk density and
        Ksat from Saxton & Rawls; layers without them fall back to Saxton & Rawls.

    The result always satisfies ``ll + min_gap <= dul`` and ``dul + min_gap <= sat``.
    """
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    out = profile.copy()
    soc = out["soc"]
    sr = saxton_rawls(out["sand"], out["clay"], np.minimum(soc * 1.724, MAX_OM), out.get("bdod"))
    ll, dul, sat = sr["ll"], sr["dul"], sr["sat"]
    w = {"saxton_rawls": 0.0, "soilgrids": 0.0, "reichert": 1.0}.get(method)
    if method == "hybrid":
        lat = profile.attrs.get("lat") if lat is None else lat
        if lat is None:
            raise ValueError('method "hybrid" needs the latitude (argument lat or profile.attrs["lat"])')
        w = reichert_weight(lat)
    if w > 0:
        silt = out["silt"] if "silt" in out else 100 - out["sand"] - out["clay"]
        re = reichert(out["clay"] / 100, silt / 100, np.minimum(soc * 1.724, MAX_OM_REICHERT) / 100, out["bdod"])
        ll = w * re["ll"] + (1 - w) * ll
        dul = w * re["dul10"] + (1 - w) * dul
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


def fill_from(profile: pd.DataFrame, other: pd.DataFrame, columns=None) -> pd.DataFrame:
    """Complete the missing values of ``profile`` (e.g. a measured profile without organic carbon)
    with ``other`` (e.g. :func:`cropemu.soil.soilgrids.fetch` at the same point): each missing
    value takes the value of the ``other`` layer that contains the middle of the layer (the
    deepest layer of ``other`` below its bottom). ``attrs["filled_from"]`` counts the values taken."""
    cols = [c for c in (other.columns if columns is None else columns) if c not in ("top", "bottom")]
    out = profile.copy()
    mid = ((out["top"] + out["bottom"]) / 2).to_numpy(float)
    k = np.clip(np.searchsorted(other["bottom"].to_numpy(float), mid, side="left"), 0, len(other) - 1)
    filled = {}
    for c in cols:
        if c not in other:
            continue
        if c not in out:
            out[c] = np.nan
        src = other[c].to_numpy(float)[k]
        miss = out[c].isna().to_numpy() & np.isfinite(src)
        if miss.any():
            out.loc[miss, c] = src[miss]
            filled[c] = int(miss.sum())
    out.attrs = {**dict(profile.attrs), "filled_from": {"source": other.attrs.get("source", "other"), **filled}}
    return out
