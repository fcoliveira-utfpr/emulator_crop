"""AquaCrop dataset on the seasons of a DSSAT dataset (same points, years, sowing, regime, climate perturbations).

Inputs are the same global datasets (plan, principle 6). AquaCrop needs the
reference ET as input: FAO-56 Penman-Monteith from NASA POWER, recomputed with the
perturbed temperatures (vapour pressure kept, i.e. constant absolute humidity).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from cropemu.soil import hydraulics, soilgrids
from cropemu.weather import eto_fao56, fetch, fill_gaps
from cropemu.weather.eto import actual_vapour_pressure

from .design.aquacrop import AQ_PERTURBATIONS, aquacrop_design, climatological_gdd, season_crop
from .inputs.calendar import CropCalendar
from .models.aquacrop import AquaCrop, AquaSoil, Season
from .pipeline import WEATHER_END, WEATHER_START

#: Simulation window around the sowing date (days); the climate files go further, since
#: AquaCrop converts the GDD cycle to calendar days with the temperature record.
DAYS_BEFORE, DAYS_AFTER, CLIMATE_DAYS_AFTER = 30, 300, 450
INITIAL_WATER = 0.5


def _weather(p) -> pd.DataFrame:
    w = fill_gaps(fetch(p.lat, p.lon, WEATHER_START, WEATHER_END))
    w["ea"] = actual_vapour_pressure(w)
    return w


def season_weather(w: pd.DataFrame, lat: float, elev: float, start, end, dt: float, rain_factor: float):
    s = w.loc[pd.Timestamp(start):pd.Timestamp(end)].copy()
    s["tmax"] += dt
    s["tmin"] += dt
    s["rain"] *= rain_factor
    s["eto"] = eto_fao56(s, lat, elev, ea=s["ea"].to_numpy())
    return s


def generate(dssat_dir, out_dir, model: AquaCrop | None = None, crop_name: str = "SoybeanGDD",
             points_per_batch: int = 50, n_jobs: int = 4, regime: str = "rf", progress: bool = True) -> Path:
    """Simulate with AquaCrop every season of the DSSAT dataset in ``dssat_dir``.

    Writes ``points.parquet``, ``design.parquet`` (shared season inputs + AquaCrop crop
    parameters), ``meta.json`` and ``summary/batchNNNNN.parquet`` (resumable).
    """
    src, out = Path(dssat_dir), Path(out_dir)
    (out / "summary").mkdir(parents=True, exist_ok=True)
    model = model or AquaCrop()
    base = model.crop(crop_name)
    pts = pd.read_parquet(src / "points.parquet")
    dssat_design = pd.read_parquet(src / "design.parquet")
    pts = pts[pts["id"].isin(dssat_design["point"])].reset_index(drop=True)

    dpath = out / "design.parquet"
    if dpath.exists():
        design = pd.read_parquet(dpath)
    else:
        cal = CropCalendar(regime).table(pts).set_index("id")
        t0 = time.time()
        gdd_clim = {}
        for p in pts.itertuples():
            w = fill_gaps(fetch(p.lat, p.lon, WEATHER_START, WEATHER_END))
            gdd_clim[p.id] = climatological_gdd(w, cal.loc[p.id, "planting_doy"], cal.loc[p.id, "maturity_doy"],
                                                base["tbase"], base["tupper"])
        if progress:
            print(f"calendar GDD of {len(pts)} points in {time.time() - t0:.0f}s", flush=True)
        design = aquacrop_design(dssat_design, pts, gdd_clim)
        design.to_parquet(dpath)
    pts.to_parquet(out / "points.parquet")
    (out / "meta.json").write_text(json.dumps({
        "model": "AquaCrop 7.3 (official executable)", "executable": str(model.executable),
        "crop": f"FAO {crop_name}.CRO", "seasons_from": str(src),
        "weather": f"NASA POWER {WEATHER_START}..{WEATHER_END}; ETo FAO-56 PM",
        "soil": "SoilGrids 2.0 1 km, 3x3 km median; top layers merged to 5 horizons",
        "window_days": [DAYS_BEFORE, DAYS_AFTER], "initial_water": INITIAL_WATER,
        "potential": "net irrigation requirement (0 % RAW depletion)",
        "perturbations": {k: list(v) for k, v in AQ_PERTURBATIONS.items()}}, indent=1, default=str))

    ids = list(pts["id"])
    batches = [ids[i:i + points_per_batch] for i in range(0, len(ids), points_per_batch)]
    for b, bids in enumerate(batches):
        target = out / "summary" / f"batch{b:05d}.parquet"
        if target.exists():
            continue
        t0 = time.time()
        rows = pts[pts["id"].isin(bids)]
        weather = {p.id: _weather(p) for p in rows.itertuples()}
        soils = {p.id: AquaSoil.from_standard(hydraulics(soilgrids.fetch(p.lat, p.lon))) for p in rows.itertuples()}
        sub = design[design["point"].isin(bids)]
        seasons = []
        for r in sub.to_dict("records"):
            p = pts.set_index("id").loc[r["point"]]
            sow = pd.Timestamp(r["sowing"])
            start = sow - pd.Timedelta(days=DAYS_BEFORE)
            end = min(sow + pd.Timedelta(days=DAYS_AFTER), pd.Timestamp(WEATHER_END))
            wend = min(sow + pd.Timedelta(days=CLIMATE_DAYS_AFTER), pd.Timestamp(WEATHER_END))
            w = season_weather(weather[r["point"]], p["lat"], p["elev"], start - pd.Timedelta(days=1), wend,
                               r["dt"], r["rain_factor"])
            seasons.append(Season(w, soils[r["point"]], season_crop(base, r), sow, start, end,
                                  co2=r["co2"] if r["perturbed"] else None, irrigated=not r["water"],
                                  initial_water=INITIAL_WATER))
        res = model.simulate(seasons, n_jobs=n_jobs)
        s = res.summary.copy()
        s.insert(0, "sample", sub["sample"].to_numpy()[s.pop("treatment").to_numpy()])
        s.drop(columns=["season"]).to_parquet(target)
        if progress:
            dt = time.time() - t0
            print(f"batch {b + 1}/{len(batches)}: {len(sub)} seasons in {dt:.0f}s ({1000 * dt / len(sub):.0f} ms/season)",
                  flush=True)
    return out
