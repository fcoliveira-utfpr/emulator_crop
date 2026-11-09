"""SoilGrids 2.0 (ISRIC, CC-BY 4.0) at points, read remotely from the 1 km aggregated maps.

The REST API of SoilGrids is too slow and unreliable for many points, so the
1 km GeoTIFFs (``data_aggregated/1000m``) are sampled over HTTP with rasterio,
which only downloads the blocks around the points. Needs ``pip install cropemu[soil]``.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BASE_URL = "https://files.isric.org/soilgrids/latest/data_aggregated/1000m"
DEPTHS = [(0, 5), (5, 15), (15, 30), (30, 60), (60, 100), (100, 200)]
#: SoilGrids property -> factor to the cropemu standard units (see cropemu.soil).
PROPERTIES = {"clay": 0.1,       # g/kg -> %
              "sand": 0.1,       # g/kg -> %
              "silt": 0.1,       # g/kg -> %
              "soc": 0.01,       # dg/kg -> %
              "bdod": 0.01,      # cg/cm³ -> g/cm³
              "cfvo": 0.1,       # cm³/dm³ -> %
              "nitrogen": 0.001,  # cg/kg -> %
              "phh2o": 0.1,      # pH x 10 -> pH
              "cec": 0.1,        # mmol(c)/kg -> cmol(c)/kg
              "wv0033": 0.001,   # 10⁻³ cm³/cm³ -> cm³/cm³
              "wv1500": 0.001}
NODATA = -32768
GDAL_ENV = {"GDAL_HTTP_TIMEOUT": "60", "GDAL_HTTP_MAX_RETRY": "5", "GDAL_HTTP_RETRY_DELAY": "5",
            "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "VSI_CACHE": "TRUE"}


def default_cache_dir() -> Path:
    return Path(os.environ.get("CROPEMU_CACHE", Path.home() / ".cache" / "cropemu")) / "soilgrids"


def url(prop: str, top: int, bottom: int) -> str:
    return f"{BASE_URL}/{prop}/{prop}_{top}-{bottom}cm_mean_1000.tif"


def _sample_file(path: str, lats, lons, radius: int) -> np.ndarray:
    """Median of the valid pixels in a (2r+1)² window around each point (NaN if none)."""
    import rasterio
    from rasterio.warp import transform
    from rasterio.windows import Window

    out = np.full(len(lats), np.nan)
    with rasterio.Env(**GDAL_ENV), rasterio.open(path) as src:
        xs, ys = transform("EPSG:4326", src.crs, list(lons), list(lats))
        for i, (x, y) in enumerate(zip(xs, ys)):
            row, col = src.index(x, y)
            win = Window(col - radius, row - radius, 2 * radius + 1, 2 * radius + 1)
            a = src.read(1, window=win, boundless=True, fill_value=NODATA).astype(float)
            a = a[a != NODATA]
            if a.size:
                out[i] = np.median(a)
    return out


def _cache_file(cache_dir: Path, lat: float, lon: float, radius: int) -> Path:
    return cache_dir / f"{lat:+08.4f}_{lon:+09.4f}_r{radius}.csv"


def fetch_many(points: pd.DataFrame, cache_dir=None, radius: int = 1, n_jobs: int = 32,
               properties=tuple(PROPERTIES), source=None, points_per_job: int = 25) -> dict:
    """Soil profiles (cropemu standard, 6 layers to 200 cm) at many points.

    ``points`` has columns ``id``, ``lat``, ``lon``. ``radius`` is the half-width of
    the window in 1 km pixels (1: 3 x 3 km median). Points already in the cache are
    not read again. ``source`` overrides the base URL/folder (e.g. a local copy).
    Returns ``{id: DataFrame}``; profiles of points with no soil data (water,
    urban areas, ice) have NaN values.

    Each remote window read takes about a second (HTTP latency), so the work is split
    in jobs of (property, depth, group of ``points_per_job`` points) run by ``n_jobs`` threads.
    """
    cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    pts = points[["id", "lat", "lon"]].reset_index(drop=True)
    files = {r.id: _cache_file(cache_dir, r.lat, r.lon, radius) for r in pts.itertuples()}
    todo = pts[[not files[i].exists() for i in pts["id"]]]

    if len(todo):
        base = source or f"/vsicurl/{BASE_URL}"
        lats, lons = todo["lat"].to_numpy(), todo["lon"].to_numpy()
        groups = [slice(i, i + points_per_job) for i in range(0, len(todo), points_per_job)]
        jobs = [(p, t, b, g) for p in properties for t, b in DEPTHS for g in groups]

        def job(j):
            p, t, b, g = j
            path = f"{base}/{p}/{p}_{t}-{b}cm_mean_1000.tif"
            return (p, t, b), g, _sample_file(path, lats[g], lons[g], radius)

        values = {(p, t, b): np.full(len(todo), np.nan) for p in properties for t, b in DEPTHS}
        with ThreadPoolExecutor(max_workers=n_jobs) as ex:
            for key, g, v in ex.map(job, jobs):
                values[key][g] = v
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for k, r in enumerate(todo.itertuples()):
            rows = [{"top": t, "bottom": b, **{p: values[(p, t, b)][k] * PROPERTIES[p] for p in properties}}
                    for t, b in DEPTHS]
            attrs = {"lat": float(r.lat), "lon": float(r.lon), "source": "SoilGrids 2.0 (1 km)",
                     "radius_km": radius, "downloaded": stamp}
            with open(files[r.id], "w") as f:
                f.write("# " + json.dumps(attrs) + "\n")
                pd.DataFrame(rows).to_csv(f, index=False, float_format="%.4g")

    return {i: _read(files[i]) for i in pts["id"]}


def _read(path: Path) -> pd.DataFrame:
    with open(path) as f:
        attrs = json.loads(f.readline()[2:])
        df = pd.read_csv(f)
    df.attrs = attrs
    return df


def fetch(lat: float, lon: float, **kw) -> pd.DataFrame:
    """Soil profile of one point (see :func:`fetch_many`)."""
    return fetch_many(pd.DataFrame({"id": [0], "lat": [lat], "lon": [lon]}), **kw)[0]
