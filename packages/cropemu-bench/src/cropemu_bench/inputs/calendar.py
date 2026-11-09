"""Soybean crop calendar of GGCMI Phase 3 (Jägermeyr et al. 2021, Nature Food; CC-BY 4.0).

Zenodo 10.5281/zenodo.5062513, version 1.01: planting and maturity day of year on a
0.5° grid, for rainfed (``rf``) and irrigated (``ir``) soybean.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .download import cache_dir, fetch_file

ZENODO = "https://zenodo.org/api/records/5062513/files/{name}/content"
FILES = {"rf": ("soy_rf_ggcmi_crop_calendar_phase3_v1.01.nc4", "ff26e022c463fccbf96ceb72ce05b7a3"),
         "ir": ("soy_ir_ggcmi_crop_calendar_phase3_v1.01.nc4", "e5a62341a09c684e9af6cf64a2d36bc5")}
SOURCES = {1: "MIRCA", 2: "SAGE", 3: "Iizumi et al. 2019", 4: "RiceAtlas", 5: "Dimou et al. 2018",
           6: "ChinaCropPhen", 7: "IndiaAgStat", 8: "Brazil CONAB", 9: "Australia ABARES"}


@dataclass
class CalendarEntry:
    planting_doy: int
    maturity_doy: int
    season_days: int
    source: str
    cell_lat: float
    cell_lon: float
    distance_cells: int            # 0 if the point's own cell has data


class CropCalendar:
    """GGCMI Phase 3 soybean calendar for one water regime (``"rf"`` or ``"ir"``)."""

    def __init__(self, regime: str = "rf", path=None):
        import xarray as xr

        if regime not in FILES:
            raise ValueError("regime must be 'rf' or 'ir'")
        name, md5sum = FILES[regime]
        path = path or fetch_file(ZENODO.format(name=name), cache_dir("ggcmi") / name, md5sum)
        with xr.open_dataset(path, decode_timedelta=False) as ds:
            self.lat = ds["lat"].to_numpy()
            self.lon = ds["lon"].to_numpy()
            self.planting = ds["planting_day"].to_numpy()
            self.maturity = ds["maturity_day"].to_numpy()
            self.source = ds["data_source_used"].to_numpy()
        self.regime = regime

    def _index(self, lat: float, lon: float) -> tuple[int, int]:
        return int(np.abs(self.lat - lat).argmin()), int(np.abs(self.lon - lon).argmin())

    def at(self, lat: float, lon: float, max_distance: int = 2) -> CalendarEntry | None:
        """Calendar of the cell of (lat, lon), or of the nearest cell with data within
        ``max_distance`` cells (rings of 0.5°). ``None`` if there is none."""
        i0, j0 = self._index(lat, lon)
        ni, nj = self.planting.shape
        for d in range(max_distance + 1):
            best = None
            for i in range(i0 - d, i0 + d + 1):
                for j in range(j0 - d, j0 + d + 1):
                    if max(abs(i - i0), abs(j - j0)) != d or not 0 <= i < ni:
                        continue
                    jj = j % nj                                  # longitude wraps around
                    if np.isfinite(self.planting[i, jj]) and np.isfinite(self.maturity[i, jj]):
                        dist = (self.lat[i] - lat) ** 2 + (self.lon[jj] - lon) ** 2
                        if best is None or dist < best[0]:
                            best = (dist, i, jj)
            if best is not None:
                _, i, j = best
                p, m = int(self.planting[i, j]), int(self.maturity[i, j])
                src = self.source[i, j]
                return CalendarEntry(p, m, (m - p) % 365 or 365,
                                     SOURCES.get(int(src), "unknown") if np.isfinite(src) else "unknown",
                                     float(self.lat[i]), float(self.lon[j]), d)
        return None

    def table(self, points: pd.DataFrame, max_distance: int = 2) -> pd.DataFrame:
        """Calendar of many points (columns ``id``, ``lat``, ``lon``); NaN where none."""
        rows = []
        for r in points[["id", "lat", "lon"]].itertuples(index=False):
            e = self.at(r.lat, r.lon, max_distance)
            rows.append({"id": r.id, **(e.__dict__ if e else {})})
        return pd.DataFrame(rows)


def sowing_window(planting_doy: int, half_width: int = 30) -> tuple[int, int]:
    """Day-of-year window centred on the GGCMI planting day (may wrap past day 365)."""
    return (planting_doy - half_width - 1) % 365 + 1, (planting_doy + half_width - 1) % 365 + 1


def sowing_dates(planting_doy: int, years, offsets) -> list[date]:
    """Sowing dates: the GGCMI planting day of each year shifted by ``offsets`` (days).

    ``years`` and ``offsets`` have the same length (e.g. offsets drawn by Latin
    hypercube in [-half_width, half_width]). Day 366 is mapped to day 365.
    """
    years, offsets = np.asarray(years), np.asarray(offsets)
    if years.shape != offsets.shape:
        raise ValueError("years and offsets must have the same length")
    doy = min(int(planting_doy), 365)
    return [date(int(y), 1, 1) + timedelta(days=doy - 1 + int(round(o))) for y, o in zip(years, offsets)]
