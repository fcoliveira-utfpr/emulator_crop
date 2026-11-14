"""Weather and water-balance inputs summarised by crop phase instead of fixed 30-day windows.

Phases (days after sowing): vegetative [0, flowering), early reproductive [flowering, s5) and seed
filling [s5, maturity), with s5 = flowering + 0.35 (maturity - flowering) (~R5, beginning seed).
Per phase: length, mean Tmax/Tmin/radiation/VPD/day length, rain, ETo, rain - ETo, days with
Tmax >= 32 / 35 °C and Tmin < 10 °C, growing degrees, mean bucket stress, days of bucket stress
> 0.5, longest dry spell (rain < 1 mm). The climate perturbation of each season (ΔT, rain factor)
is applied as in cropemu.features (temperatures + ΔT, rain x factor, VPD shifted, ETo recomputed
with the actual vapour pressure kept).

The bucket is the same one-layer balance as cropemu.features.WeatherSeries.bucket_stress, run
from 30 days before sowing to maturity.

Writes results/phase_<dates>.parquet for two sets of phase dates:
  oof   - flowering and maturity predicted out of fold by the published emulator (test rows)
  train - simulated dates + N(0, 3 d) noise (training rows; censored maturity: the oof prediction)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cropemu.features import WeatherSeries
from cropemu.weather import fetch, fill_gaps
from cropemu_bench.pipeline import WEATHER_END, WEATHER_START

from common import DATA, OUT, baseline_oof, load

L0, L1 = -30, 250                       # days after sowing covered by the daily matrices
DAYS = np.arange(L0, L1 + 1)


def es(t):
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def eto_fao56(tmax, tmin, srad, wind, ea, lat, elev, doy):
    """FAO-56 Penman-Monteith (cropemu.weather.eto.eto_fao56), vectorised over arrays."""
    u2 = np.where(np.isfinite(wind), wind, 2.0)
    tmean = (tmax + tmin) / 2
    p = 101.3 * ((293 - 0.0065 * elev) / 293) ** 5.26
    gamma = 0.000665 * p
    delta = 4098 * es(tmean) / (tmean + 237.3) ** 2
    esat = (es(tmax) + es(tmin)) / 2
    ea = np.minimum(ea, esat)
    phi = np.radians(lat)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    dec = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(dec), -1, 1))
    ra = 24 * 60 / np.pi * 0.0820 * dr * (ws * np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.sin(ws))
    rso = (0.75 + 2e-5 * elev) * ra
    ratio = np.clip(np.divide(srad, rso, out=np.ones_like(srad), where=rso > 0), 0.3, 1.0)
    rnl = 4.903e-9 * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2 * (0.34 - 0.14 * np.sqrt(ea)) * (1.35 * ratio - 0.35)
    eto = (0.408 * delta * (0.77 * srad - rnl) + gamma * 900 / (tmean + 273) * u2 * (esat - ea)) / (delta + gamma * (1 + 0.34 * u2))
    return np.maximum(eto, 0.0)


def daily_matrices(design: pd.DataFrame, points: pd.DataFrame):
    """Per sample (rows of ``design``), the daily weather from L0 to L1 days after sowing with the
    season's perturbation applied: dict of (n, L) float32 arrays."""
    n, L = len(design), len(DAYS)
    names = ["tmax", "tmin", "srad", "rain", "eto", "vpd", "dayl"]
    M = {k: np.full((n, L), np.nan, np.float32) for k in names}
    pts = points.set_index("id")
    pos = {s: i for i, s in enumerate(design["sample"])}
    for k, (pid, g) in enumerate(design.groupby("point", sort=False)):
        p = pts.loc[pid]
        ws = WeatherSeries(fill_gaps(fetch(p["lat"], p["lon"], WEATHER_START, WEATHER_END)), p["lat"], p["elev"])
        rows = np.array([pos[s] for s in g["sample"]])
        i0 = (pd.to_datetime(g["sowing"]).to_numpy() - np.datetime64(ws.t0, "ns")) // np.timedelta64(1, "D")
        idx = i0[:, None] + DAYS[None, :]
        ok = (idx >= 0) & (idx < ws.n)
        idx = np.clip(idx, 0, ws.n - 1)
        dt = g["dt"].to_numpy()[:, None]
        rf = g["rain_factor"].to_numpy()[:, None]
        tmax, tmin = ws.tmax[idx] + dt, ws.tmin[idx] + dt
        vpd = ws.vpd[idx] + ((es(tmax) + es(tmin)) - (es(tmax - dt) + es(tmin - dt))) / 2
        doy = pd.DatetimeIndex(ws.df.index).dayofyear.to_numpy()[idx]
        wind = ws.df["wind"].to_numpy(float)[idx] if "wind" in ws.df else np.full(idx.shape, np.nan)
        eto = np.where(dt != 0, eto_fao56(tmax, tmin, ws.srad[idx], wind, ws.ea[idx], p["lat"], ws.elev, doy), ws.eto[idx])
        vals = {"tmax": tmax, "tmin": tmin, "srad": ws.srad[idx], "rain": ws.rain[idx] * rf, "eto": eto, "vpd": vpd,
                "dayl": ws.dayl[idx]}
        for name, v in vals.items():
            M[name][rows] = np.where(ok, v, np.nan)
        if k % 200 == 0:
            print(f"  weather {k}/{design['point'].nunique()} points", flush=True)
    return M


def bucket(rain, eto, paw, initial=0.5, p=0.5):
    """Daily stress of the one-layer bucket (WeatherSeries.bucket_stress), vectorised over seasons."""
    cap = np.maximum(paw, 1.0)
    s = initial * cap
    stress = np.empty_like(rain)
    for k in range(rain.shape[1]):
        r = np.nan_to_num(rain[:, k])
        s = np.minimum(s + r, cap)
        stress[:, k] = 1 - np.minimum(1.0, s / ((1 - p) * cap))
        s = np.maximum(s - np.nan_to_num(eto[:, k]) * (1 - stress[:, k]), 0.0)
    return stress


def phase_features(M, stress, flo, mat):
    """Phase summaries for the given flowering and maturity days (arrays, days after sowing)."""
    flo = np.clip(np.round(flo), 5, 200)
    mat = np.clip(np.round(mat), flo + 10, L1)
    s5 = np.round(flo + 0.35 * (mat - flo))
    gdd = np.maximum((np.clip(M["tmax"], 5, 30) + np.minimum(M["tmin"], 30)) / 2 - 5, 0)
    out = {}
    d = DAYS[None, :]
    for name, a, b in (("veg", np.zeros_like(flo), flo), ("rep", flo, s5), ("fill", s5, mat)):
        m = (d >= a[:, None]) & (d < b[:, None])
        n = m.sum(1).astype(float)
        mean = lambda v: np.nansum(np.where(m, v, 0), 1) / np.maximum(n, 1)
        tot = lambda v: np.nansum(np.where(m, v, 0), 1)
        cnt = lambda c: np.where(m, c, False).sum(1).astype(float)
        out[f"{name}_days"] = n
        for v in ("tmax", "tmin", "srad", "vpd", "dayl"):
            out[f"{name}_{v}"] = mean(M[v])
        out[f"{name}_rain"] = tot(M["rain"])
        out[f"{name}_eto"] = tot(M["eto"])
        out[f"{name}_deficit"] = out[f"{name}_rain"] - out[f"{name}_eto"]
        out[f"{name}_hot32"] = cnt(M["tmax"] >= 32)
        out[f"{name}_hot35"] = cnt(M["tmax"] >= 35)
        out[f"{name}_cold10"] = cnt(M["tmin"] < 10)
        out[f"{name}_gdd"] = tot(gdd)
        out[f"{name}_wstr"] = mean(stress)
        out[f"{name}_wstr_days"] = cnt(stress > 0.5)
        run = np.zeros(len(flo))
        longest = np.zeros(len(flo))
        dry = (np.nan_to_num(M["rain"], nan=0) < 1) & m
        for k in range(dry.shape[1]):
            run = (run + 1) * dry[:, k]
            longest = np.maximum(longest, run)
        out[f"{name}_dry_spell"] = longest
    return pd.DataFrame(out)


def main():
    X, Y, info = load()
    design = pd.read_parquet(DATA / "design.parquet").set_index("sample").loc[X.index].reset_index()
    points = pd.read_parquet(DATA / "points.parquet")
    M = daily_matrices(design, points)
    stress = bucket(M["rain"], M["eto"], X["paw_mm"].to_numpy())
    P = baseline_oof().loc[X.index]
    rng = np.random.default_rng(1)
    flo_oof, mat_oof = P["ADAT_dap"].to_numpy(), P["MDAT_dap"].to_numpy()
    flo_true = Y["ADAT_dap"].to_numpy()
    mat_true = Y["MDAT_dap"].to_numpy()
    flo_tr = np.where(np.isfinite(flo_true), flo_true + rng.normal(0, 3, len(X)), flo_oof)
    mat_tr = np.where(np.isfinite(mat_true), mat_true + rng.normal(0, 3, len(X)), mat_oof)
    for tag, flo, mat in (("oof", flo_oof, mat_oof), ("train", flo_tr, mat_tr)):
        F = phase_features(M, stress, flo, mat).set_index(X.index)
        bad = F.columns[~np.isfinite(F.to_numpy()).all(0)].tolist()
        if bad:
            print("non-finite columns:", bad)
        F.to_parquet(OUT / f"phase_{tag}.parquet")
        print(tag, F.shape, flush=True)


if __name__ == "__main__":
    main()
