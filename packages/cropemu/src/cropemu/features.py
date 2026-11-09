"""Emulator inputs ("features") from daily weather, soil and season settings.

This code is shared by training (cropemu-bench) and use (cropemu): an emulator is
only valid with inputs computed exactly as here. Climate perturbations (ΔT, rain
factor) are applied to the weather before the features are computed, as the crop
model does.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from importlib import resources

import numpy as np
import pandas as pd

#: Windows in days after sowing (start inclusive, end exclusive).
WINDOWS = ((-30, 0), (0, 30), (30, 60), (60, 90), (90, 130))
WINDOW_VARIABLES = ("tmax", "tmin", "srad", "rain", "vpd", "dayl", "hot32", "hot35")
#: Water balance variables per window (when the soil water capacity is given): reference ET (mm)
#: and mean stress index (0-1) of a one-layer bucket (see :meth:`WeatherSeries.bucket_stress`).
WATER_VARIABLES = ("eto", "wstr")
SOIL_FEATURES = ("paw_mm", "paw30_mm", "clay30", "sand30", "soc30", "bdod30", "depth_cm")


# ---------------------------------------------------------------------------- astronomy and CO2
def daylength(lat, doy, sun_angle: float = -6.0) -> np.ndarray:
    """Day length (h) including twilight down to ``sun_angle`` degrees (civil: -6°),
    the photoperiod definition used by CROPGRO."""
    lat = np.radians(np.asarray(lat, float))
    dec = np.radians(-23.45 * np.cos(2 * np.pi * (np.asarray(doy, float) + 10) / 365))
    cos_h = (np.sin(np.radians(sun_angle)) - np.sin(lat) * np.sin(dec)) / (np.cos(lat) * np.cos(dec))
    return 24 / np.pi * np.arccos(np.clip(cos_h, -1, 1))


@lru_cache(maxsize=1)
def _co2_table() -> pd.DataFrame:
    with resources.files("cropemu.data").joinpath("co2_mauna_loa.csv").open() as f:
        t = pd.read_csv(f, comment="#")
    t = t[t["co2"] > 0]
    t["t"] = t["year"] + (t["doy"] - 0.5) / 365.25
    return t


def co2_at(d) -> float:
    """Mauna Loa CO2 (ppm) at a date, interpolated in the monthly series (clamped at the ends)."""
    d = pd.Timestamp(d)
    t = _co2_table()
    return float(np.interp(d.year + (d.dayofyear - 0.5) / 365.25, t["t"], t["co2"]))


# ---------------------------------------------------------------------------- weather
def gdd(tmax, tmin, tbase: float, tupper: float) -> np.ndarray:
    """Daily growing degrees, AquaCrop method 3: Tmax in [Tbase, Tupper], Tmin capped at Tupper,
    mean floored at Tbase."""
    tx = np.clip(tmax, tbase, tupper)
    tn = np.minimum(tmin, tupper)
    return np.maximum((tx + tn) / 2 - tbase, 0.0)


def _vpd(df: pd.DataFrame) -> np.ndarray:
    """Mean daily vapour pressure deficit (kPa) from tmax/tmin and dewp or rhum."""
    es = lambda t: 0.6108 * np.exp(17.27 * t / (t + 237.3))
    es_mean = (es(df["tmax"]) + es(df["tmin"])) / 2
    if "dewp" in df:
        ea = es(df["dewp"])
    elif "rhum" in df:
        ea = es_mean * df["rhum"] / 100
    else:                                  # no humidity: assume dew point = tmin
        ea = es(df["tmin"])
    return np.clip(es_mean - ea, 0, None).to_numpy()


class WeatherSeries:
    """Daily weather prepared once for many seasons of the same point."""

    def __init__(self, df: pd.DataFrame, lat: float, elev: float | None = None):
        from .weather.eto import actual_vapour_pressure, eto_fao56

        idx = pd.DatetimeIndex(df.index)
        self.df = df
        self.elev = float(df.attrs.get("elev", 0.0) if elev is None else elev)
        self.ea = actual_vapour_pressure(df)
        self.eto = eto_fao56(df, lat, self.elev, ea=self.ea).to_numpy()
        self.t0 = idx[0]
        self.n = len(idx)
        self.lat = lat
        self.tmax = df["tmax"].to_numpy(float)
        self.tmin = df["tmin"].to_numpy(float)
        self.srad = df["srad"].to_numpy(float)
        self.rain = df["rain"].to_numpy(float)
        self.vpd = _vpd(df)
        self.dayl = daylength(lat, idx.dayofyear.to_numpy())

    def thermal_days(self, sowing, requirements: dict, tbase: float, tupper: float, dt: float = 0.0,
                     max_days: int = 600) -> dict:
        """Days after sowing to accumulate each thermal time requirement (``{name: GDD}``).

        Requirements not met within ``max_days`` (or the end of the series) get ``max_days``.
        """
        i0 = (pd.Timestamp(sowing) - self.t0).days
        i1 = min(i0 + max_days, self.n)
        cum = np.cumsum(gdd(self.tmax[i0:i1] + dt, self.tmin[i0:i1] + dt, tbase, tupper))
        out = {}
        for name, req in requirements.items():
            k = int(np.searchsorted(cum, req))
            out[name] = float(k + 1) if k < len(cum) else float(max_days)
        return out

    def _eto(self, i0: int, i1: int, dt: float) -> np.ndarray:
        if not dt:
            return self.eto[i0:i1]
        from .weather.eto import eto_fao56

        d = self.df.iloc[i0:i1].copy()
        d["tmax"] += dt
        d["tmin"] += dt
        return eto_fao56(d, self.lat, self.elev, ea=self.ea[i0:i1]).to_numpy()   # vapour pressure kept

    def bucket_stress(self, sowing, paw_mm: float, initial: float = 0.5, start: int = -30, end: int = 130,
                      dt: float = 0.0, rain_factor: float = 1.0, p: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
        """Daily ETo and water stress index of a one-layer bucket from ``start`` to ``end`` days after sowing.

        The bucket holds ``paw_mm`` and starts at ``initial`` of it; it gains rain and loses
        ET = ETo x (1 - stress), where stress = 1 - min(1, S / ((1 - p) x paw_mm)).
        A crude summary of the water supply, not a crop model.
        """
        i0 = (pd.Timestamp(sowing) - self.t0).days + start
        i1 = i0 + (end - start)
        eto = self._eto(i0, i1, dt)
        rain = self.rain[i0:i1] * rain_factor
        cap = max(float(paw_mm), 1.0)
        s, stress = initial * cap, np.empty(len(eto))
        for k in range(len(eto)):
            s = min(s + rain[k], cap)
            stress[k] = 1 - min(1.0, s / ((1 - p) * cap))
            s = max(s - eto[k] * (1 - stress[k]), 0.0)
        return eto, stress

    def window(self, sowing, start: int, end: int, dt: float = 0.0, rain_factor: float = 1.0) -> dict:
        i0 = (pd.Timestamp(sowing) - self.t0).days + start
        i1 = i0 + (end - start)
        if i0 < 0 or i1 > self.n:
            raise ValueError(f"weather does not cover days {start}..{end} after sowing {sowing}")
        tmax = self.tmax[i0:i1] + dt
        es = lambda t: 0.6108 * np.exp(17.27 * t / (t + 237.3))
        # ΔT also raises the VPD: shift the saturation part, keep the actual vapour pressure
        vpd = self.vpd[i0:i1]
        if dt:
            tmin = self.tmin[i0:i1]
            vpd = vpd + ((es(tmax) + es(tmin + dt)) - (es(tmax - dt) + es(tmin))) / 2
        return {"tmax": tmax.mean(), "tmin": self.tmin[i0:i1].mean() + dt, "srad": self.srad[i0:i1].mean(),
                "rain": self.rain[i0:i1].sum() * rain_factor, "vpd": vpd.mean(), "dayl": self.dayl[i0:i1].mean(),
                "hot32": float((tmax >= 32).sum()), "hot35": float((tmax >= 35).sum())}


def season_features(weather: WeatherSeries, sowing, dt: float = 0.0, rain_factor: float = 1.0,
                    windows=WINDOWS, paw_mm: float | None = None, initial_water: float = 0.5) -> dict:
    """Weather features of one season: one value per (window, variable), plus the
    photoperiod on the sowing day and the sowing day of year (as sine and cosine).
    With ``paw_mm`` (soil available water), also the window ETo and bucket stress
    (:data:`WATER_VARIABLES`)."""
    out = {}
    for a, b in windows:
        w = weather.window(sowing, a, b, dt, rain_factor)
        for v in WINDOW_VARIABLES:
            out[f"{v}_{a}_{b}"] = w[v]
    if paw_mm is not None:
        s0, s1 = windows[0][0], windows[-1][1]
        eto, stress = weather.bucket_stress(sowing, paw_mm, initial_water, s0, s1, dt, rain_factor)
        for a, b in windows:
            out[f"eto_{a}_{b}"] = float(eto[a - s0:b - s0].sum())
            out[f"wstr_{a}_{b}"] = float(stress[a - s0:b - s0].mean())
    s = pd.Timestamp(sowing)
    out["dayl_sowing"] = float(daylength(weather.lat, s.dayofyear))
    out["sowing_sin"] = float(np.sin(2 * np.pi * s.dayofyear / 365.25))
    out["sowing_cos"] = float(np.cos(2 * np.pi * s.dayofyear / 365.25))
    return out


# ---------------------------------------------------------------------------- soil and site
def soil_features(profile: pd.DataFrame) -> dict:
    """Soil features from a standard profile with hydraulics (``cropemu.soil.hydraulics``)."""
    thick = (profile["bottom"] - profile["top"]).to_numpy(float)
    paw = (profile["dul"] - profile["ll"]).to_numpy(float) * thick * 10
    top = np.clip(np.minimum(profile["bottom"], 30) - profile["top"], 0, None).to_numpy(float)
    wavg = lambda c: float(np.sum(profile[c].to_numpy(float) * top) / top.sum())
    return {"paw_mm": float(paw.sum()), "paw30_mm": float(np.sum(paw * top / thick)),
            "clay30": wavg("clay"), "sand30": wavg("sand"), "soc30": wavg("soc"), "bdod30": wavg("bdod"),
            "depth_cm": float(profile["bottom"].max())}


def site_features(lat: float, elev: float) -> dict:
    return {"lat": float(lat), "abs_lat": abs(float(lat)), "elev": float(elev)}


# ---------------------------------------------------------------------------- one season
def aquacrop_soybean_thermal(cultivar: dict) -> tuple[dict, float, float]:
    """Thermal requirements of the AquaCrop soybean (FAO SoybeanGDD scaled to ``gdd_maturity``):
    GDD of emergence, flowering, start of senescence and maturity; Tbase and Tupper (°C)."""
    f = float(cultivar["gdd_maturity"]) / 2700.0
    return ({"td_emergence": 200.0, "td_flowering": 1500.0 * f, "td_senescence": 2200.0 * f,
             "td_maturity": float(cultivar["gdd_maturity"])}, 5.0, 30.0)


#: Thermal-time inputs by name (the name is stored in the emulator card).
THERMAL = {"aquacrop_soybean": aquacrop_soybean_thermal}


def season_inputs(weather: WeatherSeries, soil: dict, sowing, cultivar: dict, irrigated: bool, co2: float,
                  dt: float = 0.0, rain_factor: float = 1.0, water_balance: bool = True,
                  initial_water: float = 0.5, thermal: str | None = None) -> dict:
    """Every emulator input of one season, in the order used in training.

    ``soil``: :func:`soil_features`; ``cultivar``: cultivar parameters (names of the emulator
    card); ``irrigated``: potential (no water stress) instead of rainfed; ``co2`` in ppm;
    ``dt``/``rain_factor``: climate perturbation applied to the weather; ``thermal``: name in
    :data:`THERMAL` (days after sowing to accumulate each thermal requirement).
    """
    rec = {**site_features(weather.lat, weather.elev), **soil,
           **season_features(weather, sowing, dt, rain_factor, paw_mm=soil["paw_mm"] if water_balance else None,
                             initial_water=initial_water),
           **{k: float(v) for k, v in cultivar.items()},
           "water": 0.0 if irrigated else 1.0, "co2": float(co2)}
    if thermal is not None:
        req, tb, tu = THERMAL[thermal](cultivar)
        rec.update(weather.thermal_days(sowing, req, tb, tu, dt=dt))
    return rec
