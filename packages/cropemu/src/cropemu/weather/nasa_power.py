"""NASA POWER daily point data (https://power.larc.nasa.gov), with a local cache.

Meteorology comes from MERRA-2 (~0.5° x 0.625°), solar radiation from CERES/SRB (1°).
Solar radiation starts on 1984-01-01, so that is the default start date.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .. import __version__

URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
#: NASA POWER parameter -> cropemu column (units already match the cropemu standard).
PARAMETERS = {"ALLSKY_SFC_SW_DWN": "srad", "T2M_MAX": "tmax", "T2M_MIN": "tmin", "PRECTOTCORR": "rain",
              "RH2M": "rhum", "WS2M": "wind", "T2MDEW": "dewp"}
FIRST_DATE = date(1984, 1, 1)
USER_AGENT = f"cropemu/{__version__} (+https://pypi.org/project/cropemu/)"


def default_cache_dir() -> Path:
    return Path(os.environ.get("CROPEMU_CACHE", Path.home() / ".cache" / "cropemu")) / "nasa_power"


def _as_date(d) -> date:
    return d if isinstance(d, date) else pd.Timestamp(d).date()


def parse(payload: dict) -> pd.DataFrame:
    """Daily table (cropemu standard) from a NASA POWER JSON response; fill values become NaN."""
    params = payload["properties"]["parameter"]
    fill = payload["header"].get("fill_value", -999.0)
    df = pd.DataFrame({PARAMETERS.get(k, k): pd.Series(v, dtype=float) for k, v in params.items()})
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "date"
    df = df.replace(fill, np.nan)[[c for c in PARAMETERS.values() if c in df]]
    lon, lat, elev = payload["geometry"]["coordinates"]
    df.attrs = {"lat": float(lat), "lon": float(lon), "elev": float(elev), "source": "NASA POWER",
                "api_version": payload["header"].get("api", {}).get("version", "")}
    return df


def _request(lat, lon, start: date, end: date, timeout: float, retries: int) -> dict:
    query = urllib.parse.urlencode({
        "parameters": ",".join(PARAMETERS), "community": "AG", "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}", "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
        "format": "JSON"})
    req = urllib.request.Request(f"{URL}?{query}", headers={"User-Agent": USER_AGENT})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(min(60, 2 ** attempt * 5))      # back off: POWER limits request rates
    raise RuntimeError("unreachable")


def _cache_path(cache_dir: Path, lat, lon, start: date, end: date) -> Path:
    return cache_dir / f"{lat:+08.4f}_{lon:+09.4f}_{start:%Y%m%d}_{end:%Y%m%d}.csv.gz"


def fetch(lat: float, lon: float, start=FIRST_DATE, end=None, cache_dir=None, use_cache: bool = True,
          timeout: float = 120, retries: int = 4) -> pd.DataFrame:
    """Daily weather of one point from NASA POWER (cropemu standard columns).

    Parameters
    ----------
    start, end
        Period (inclusive). ``end`` defaults to 31 December of the previous year,
        so cached series do not change with near-real-time updates.
    cache_dir
        Folder of the cache (default ``$CROPEMU_CACHE/nasa_power`` or
        ``~/.cache/cropemu/nasa_power``). Each series is saved as ``.csv.gz`` with
        its metadata (coordinates of the grid cell, elevation, API version, download time).
    """
    start = _as_date(start)
    end = _as_date(end) if end is not None else date(date.today().year - 1, 12, 31)
    if start < FIRST_DATE:
        raise ValueError(f"NASA POWER solar radiation starts on {FIRST_DATE}")
    if end < start:
        raise ValueError("end must not be before start")
    cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
    path = _cache_path(cache_dir, lat, lon, start, end)
    if use_cache and path.exists():
        return _read_cache(path)

    df = parse(_request(lat, lon, start, end, timeout, retries))
    df.attrs.update({"requested_lat": float(lat), "requested_lon": float(lon),
                     "downloaded": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    if use_cache:
        _write_cache(path, df)
    return df


def _write_cache(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt") as f:
        f.write("# " + json.dumps(df.attrs) + "\n")
        df.to_csv(f, float_format="%.2f")
    tmp.replace(path)                                  # atomic: no half-written cache files


def _read_cache(path: Path) -> pd.DataFrame:
    with gzip.open(path, "rt") as f:
        attrs = json.loads(f.readline()[2:])
        df = pd.read_csv(io.StringIO(f.read()), index_col="date", parse_dates=["date"])
    df.attrs = attrs
    return df


def fetch_many(points: pd.DataFrame, start=FIRST_DATE, end=None, cache_dir=None, n_jobs: int = 4,
               progress: bool = False, **kw) -> dict:
    """Fetch several points in parallel. ``points`` has columns ``id``, ``lat``, ``lon``.

    Returns ``{id: DataFrame}``. Points that fail are reported in the
    ``errors`` attribute of the returned dict subclass instead of stopping the batch.
    """
    class Results(dict):
        errors: dict

    out, errors = Results(), {}
    rows = list(points[["id", "lat", "lon"]].itertuples(index=False))

    def job(r):
        try:
            return r.id, fetch(r.lat, r.lon, start, end, cache_dir, **kw), None
        except Exception as e:                       # noqa: BLE001 - collect and report
            return r.id, None, repr(e)

    with ThreadPoolExecutor(max_workers=n_jobs) as ex:
        for k, (pid, df, err) in enumerate(ex.map(job, rows), 1):
            if err:
                errors[pid] = err
            else:
                out[pid] = df
            if progress and k % 50 == 0:
                print(f"{k}/{len(rows)} points")
    out.errors = errors
    return out
