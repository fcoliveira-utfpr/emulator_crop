"""End-to-end generation of a simulation dataset (points -> inputs -> design -> DSSAT -> Parquet).

Everything comes from the same global datasets at every point (plan, principle 6):
NASA POWER weather, SoilGrids soil, GGCMI calendar, cultivars from the design.
Outputs are written in batches of points, so an interrupted run resumes where it stopped.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

from cropemu.soil import hydraulics, soilgrids
from cropemu.weather import check, fetch, fetch_many, fill_gaps

from .design.cultivars import MGTable, cultivar_table
from .design.seasons import SeasonDesign, design_seasons, to_treatments
from .inputs.calendar import CropCalendar
from .models.dssat import DSSAT, SoilProfile, Weather
from .models.dssat._fmt import code

WEATHER_START, WEATHER_END = "1984-01-01", "2025-12-31"


def prepare_inputs(points: pd.DataFrame, n_jobs_weather: int = 4, n_jobs_soil: int = 32,
                   progress: bool = True) -> pd.DataFrame:
    """Download (or read from the cache) weather and soil of every point and check them.

    Returns ``points`` with ``elev``, ``soil_id``, ``texture``, ``paw_mm`` and ``ok``
    (False when weather or soil is unusable, with the reason in ``problem``).
    """
    pts = points.reset_index(drop=True).copy()
    t0 = time.time()
    w = fetch_many(pts, WEATHER_START, WEATHER_END, n_jobs=n_jobs_weather, progress=progress)
    if progress:
        print(f"weather: {len(w)} ok, {len(w.errors)} errors in {time.time() - t0:.0f}s")
    t0 = time.time()
    s = soilgrids.fetch_many(pts, n_jobs=n_jobs_soil)
    if progress:
        print(f"soil: {len(s)} points in {time.time() - t0:.0f}s")

    out = []
    for k, r in enumerate(pts.itertuples()):
        rec = {"elev": float("nan"), "soil_id": "SG" + code(k, 8), "texture": None, "paw_mm": float("nan"),
               "ok": False, "problem": ""}
        if r.id not in w:
            rec["problem"] = f"weather: {w.errors.get(r.id, 'missing')}"
        else:
            rep = check(fill_gaps(w[r.id]))
            rec["elev"] = w[r.id].attrs.get("elev", float("nan"))
            prof = s[r.id]
            if not rep["ok"]:
                rec["problem"] = f"weather check: {rep}"
            elif prof[["clay", "sand", "soc", "bdod"]].isna().any().any():
                rec["problem"] = "no soil data"
            else:
                h = hydraulics(prof)
                sp = SoilProfile.from_standard(h)
                rec.update(texture=sp.texture, ok=True,
                           paw_mm=float(((h["dul"] - h["ll"]) * (h["bottom"] - h["top"]) * 10).sum()))
        out.append(rec)
    return pd.concat([pts, pd.DataFrame(out)], axis=1)


def _soil(point_row) -> SoilProfile:
    prof = soilgrids.fetch(point_row.lat, point_row.lon)          # from the cache
    return SoilProfile.from_standard(hydraulics(prof))


def _weather(point_row) -> Weather:
    df = fill_gaps(fetch(point_row.lat, point_row.lon, WEATHER_START, WEATHER_END))   # from the cache
    return Weather.from_standard(df)


def generate(points: pd.DataFrame, out_dir, design: SeasonDesign = SeasonDesign(), model: DSSAT | None = None,
             points_per_batch: int = 50, n_jobs: int = 4, regime: str = "rf", progress: bool = True) -> Path:
    """Simulate every season of every usable point and write a dataset to ``out_dir``.

    Files: ``points.parquet``, ``design.parquet`` (one row per season: every varying input),
    ``cultivars.parquet``, ``meta.json`` and, per batch of points, ``summary/``,
    ``envsum/`` and ``stress/`` Parquet files keyed by ``sample``. Existing batch
    files are kept (resume).
    """
    out = Path(out_dir)
    for sub in ("summary", "envsum", "stress"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    model = model or DSSAT()

    pts = points[points["ok"]].reset_index(drop=True) if "ok" in points else prepare_inputs(points)
    pts = pts[pts["ok"]].reset_index(drop=True)
    calendar = CropCalendar(regime).table(pts)
    seasons, cultivars = design_seasons(pts, calendar, MGTable(model.dssat_home), design)
    seasons = seasons.merge(calendar[["id", "planting_doy"]].rename(columns={"id": "point"}), on="point")
    pts.to_parquet(out / "points.parquet")
    seasons.to_parquet(out / "design.parquet")
    cultivar_table(cultivars).to_parquet(out / "cultivars.parquet")
    (out / "meta.json").write_text(json.dumps({
        "design": asdict(design), "weather": f"NASA POWER {WEATHER_START}..{WEATHER_END}",
        "soil": "SoilGrids 2.0 1 km, 3x3 km median; LL/DUL from wv1500/wv0033",
        "calendar": f"GGCMI Phase 3 v1.01 soy_{regime}", "dssat": str(model.executable)}, indent=1, default=str))

    cul_by_id = {c.id: c for c in cultivars}
    soil_ids = dict(zip(pts["id"], pts["soil_id"]))
    point_ids = list(pts["id"])
    batches = [point_ids[i:i + points_per_batch] for i in range(0, len(point_ids), points_per_batch)]
    for b, ids in enumerate(batches):
        target = out / "summary" / f"batch{b:05d}.parquet"
        if target.exists():
            continue
        t0 = time.time()
        rows = pts[pts["id"].isin(ids)]
        full = {r.id: _weather(r) for r in rows.itertuples()}
        soils = {r.soil_id: _soil(r) for r in rows.itertuples()}
        sub = seasons[seasons["point"].isin(ids)]
        treatments, weather = [], {}
        for t in to_treatments(sub, soil_ids, design):
            # one short weather file per season: DSSAT reads it ~3x faster than the 42-year
            # series, with identical results (it needs the day before the start; TAV/AMP of the full series)
            key = f"{t.weather}|{t.start}"
            if key not in weather:
                s0 = pd.Timestamp(t.start)
                weather[key] = full[t.weather].slice(s0 - pd.Timedelta(days=30), s0 + pd.Timedelta(days=450))
            treatments.append(replace(t, weather=key))
        res = model.simulate(treatments, weather=weather, soils=soils,
                             cultivars=[cul_by_id[c] for c in sub["cultivar"]], n_jobs=n_jobs)
        samples = sub["sample"].to_numpy()
        for name, df in (("summary", res.summary), ("envsum", res.extra.get("envsum")),
                         ("stress", res.extra.get("overview_stress"))):
            if df is None:
                continue
            df = df.copy()
            df.insert(0, "sample", samples[df.pop("treatment").to_numpy()])
            df = df.drop(columns=["season"])
            df.to_parquet(out / name / f"batch{b:05d}.parquet")
        if progress:
            dt = time.time() - t0
            print(f"batch {b + 1}/{len(batches)}: {len(sub)} seasons in {dt:.0f}s ({1000 * dt / len(sub):.0f} ms/season)")
    return out


def load(out_dir) -> dict[str, pd.DataFrame]:
    """Read a generated dataset: design joined with the summary outputs, plus the other tables."""
    out = Path(out_dir)
    tables = {n: pd.concat([pd.read_parquet(f) for f in sorted((out / n).glob("*.parquet"))], ignore_index=True)
              for n in ("summary", "envsum", "stress") if any((out / n).glob("*.parquet"))}
    tables["design"] = pd.read_parquet(out / "design.parquet")
    tables["points"] = pd.read_parquet(out / "points.parquet")
    return tables
