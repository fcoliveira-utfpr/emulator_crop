"""Reference evapotranspiration, FAO-56 Penman-Monteith (Allen et al., 1998).

Daily, short grass reference. Needs ``srad``, ``tmax``, ``tmin`` and, when
available, ``dewp`` (preferred), or ``rhum``, and ``wind``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def saturation_vapour_pressure(t):
    """e°(T) in kPa (FAO-56 eq. 11)."""
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def extraterrestrial_radiation(lat: float, doy):
    """Ra in MJ/m²/d (FAO-56 eq. 21)."""
    phi = np.radians(lat)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    dec = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(dec), -1, 1))
    return 24 * 60 / np.pi * 0.0820 * dr * (ws * np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.sin(ws))


def actual_vapour_pressure(df: pd.DataFrame):
    """ea in kPa: from the dew point, else from the mean relative humidity, else ea = e°(Tmin)."""
    if "dewp" in df and df["dewp"].notna().all():
        return saturation_vapour_pressure(df["dewp"].to_numpy(float))
    es = (saturation_vapour_pressure(df["tmax"].to_numpy(float)) + saturation_vapour_pressure(df["tmin"].to_numpy(float))) / 2
    if "rhum" in df and df["rhum"].notna().all():
        return df["rhum"].to_numpy(float) / 100 * es
    return saturation_vapour_pressure(df["tmin"].to_numpy(float))


def eto_fao56(df: pd.DataFrame, lat: float, elev: float, ea=None, albedo: float = 0.23) -> pd.Series:
    """Daily ETo (mm/d) of a cropemu weather table (index: dates).

    ``ea`` (kPa) overrides the humidity of ``df``: e.g. keep the observed vapour
    pressure when temperatures are shifted in a climate perturbation.
    Missing wind is taken as 2 m/s (FAO-56 recommendation).
    """
    tmax, tmin = df["tmax"].to_numpy(float), df["tmin"].to_numpy(float)
    rs = df["srad"].to_numpy(float)
    u2 = df["wind"].to_numpy(float) if "wind" in df else np.full(len(df), 2.0)
    u2 = np.where(np.isfinite(u2), u2, 2.0)
    ea = actual_vapour_pressure(df) if ea is None else np.asarray(ea, float)
    tmean = (tmax + tmin) / 2
    p = 101.3 * ((293 - 0.0065 * elev) / 293) ** 5.26
    gamma = 0.000665 * p
    delta = 4098 * saturation_vapour_pressure(tmean) / (tmean + 237.3) ** 2
    es = (saturation_vapour_pressure(tmax) + saturation_vapour_pressure(tmin)) / 2
    ea = np.minimum(ea, es)
    doy = pd.DatetimeIndex(df.index).dayofyear.to_numpy()
    ra = extraterrestrial_radiation(lat, doy)
    rso = (0.75 + 2e-5 * elev) * ra
    rns = (1 - albedo) * rs
    ratio = np.clip(np.divide(rs, rso, out=np.ones_like(rs), where=rso > 0), 0.3, 1.0)
    sigma = 4.903e-9
    rnl = sigma * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2 * (0.34 - 0.14 * np.sqrt(ea)) * (1.35 * ratio - 0.35)
    rn = rns - rnl
    eto = (0.408 * delta * rn + gamma * 900 / (tmean + 273) * u2 * (es - ea)) / (delta + gamma * (1 + 0.34 * u2))
    return pd.Series(np.maximum(eto, 0.0), index=df.index, name="eto")
