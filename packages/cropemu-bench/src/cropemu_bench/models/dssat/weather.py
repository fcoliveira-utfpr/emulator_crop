"""DSSAT weather files (``.WTH``)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ._fmt import is_missing, num, yyyyddd

#: Daily columns written to the .WTH file, in order, with their units.
#: ``srad`` MJ/m²/d, ``tmax``/``tmin``/``dewp`` °C, ``rain`` mm, ``rhum`` %, ``wind`` km/d.
DAILY_COLUMNS = {"srad": "SRAD", "tmax": "TMAX", "tmin": "TMIN", "rain": "RAIN",
                 "rhum": "RHUM", "wind": "WIND", "dewp": "DEWP"}
REQUIRED = ("srad", "tmax", "tmin", "rain")


@dataclass
class Weather:
    """Daily weather of one station/point.

    ``data`` is indexed by date (daily, no gaps) and has at least the columns
    ``srad``, ``tmax``, ``tmin`` and ``rain``; ``rhum``, ``wind`` and ``dewp`` are
    optional (see :data:`DAILY_COLUMNS` for units).
    """

    data: pd.DataFrame
    lat: float
    lon: float
    elev: float
    refht: float = 2.0
    wndht: float = 2.0
    co2: float | None = None   # written as CCO2; used by DSSAT only with CO2 option "W"

    def __post_init__(self):
        missing = [c for c in REQUIRED if c not in self.data]
        if missing:
            raise ValueError(f"weather data lacks columns {missing}")
        idx = pd.DatetimeIndex(self.data.index)
        if len(idx) > 1 and not (np.diff(idx.values) == np.timedelta64(1, "D")).all():
            raise ValueError("weather data must be daily without gaps")

    def tav_amp(self) -> tuple[float, float]:
        """Annual mean temperature and amplitude (half the range of monthly means)."""
        tmed = (self.data["tmax"] + self.data["tmin"]) / 2
        monthly = tmed.groupby(pd.DatetimeIndex(tmed.index).month).mean()
        return float(tmed.mean()), float((monthly.max() - monthly.min()) / 2)

    def to_wth(self, insi: str) -> str:
        """Text of the .WTH file (4-digit-year dates)."""
        if len(insi) != 4:
            raise ValueError("INSI must have 4 characters")
        tav, amp = self.tav_amp()
        cols = [c for c in DAILY_COLUMNS if c in self.data]
        head = "@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT  CCO2"
        site = (f"  {insi}{num(self.lat, 9, 3)}{num(self.lon, 9, 3)}{num(round(self.elev), 6, 0)}"
                f"{num(tav, 6, 1)}{num(amp, 6, 1)}{num(self.refht, 6, 1)}{num(self.wndht, 6, 1)}"
                f"{num(self.co2, 6, 0)}")
        # "$WEATHER" (not "*WEATHER") tells DSSAT the dates have 4-digit years (YYYYDDD)
        lines = ["$WEATHER DATA : cropemu", "", head, site,
                 "@  DATE" + "".join(f"{DAILY_COLUMNS[c]:>6s}" for c in cols)]
        values = self.data[cols].to_numpy(dtype=float)
        for d, row in zip(pd.DatetimeIndex(self.data.index), values):
            # DSSAT reads the date from columns 1-7 (Fortran I7), whatever the header says
            lines.append(yyyyddd(d.date()) + "".join(
                num(np.nan if is_missing(v) else v, 6, 1) for v in row))
        return "\n".join(lines) + "\n"

    def write(self, folder: Path, insi: str) -> str:
        """Write ``<WSTA>.WTH`` in ``folder`` and return the 8-character WSTA code."""
        idx = pd.DatetimeIndex(self.data.index)
        y0, n = idx[0].year, idx[-1].year - idx[0].year + 1
        wsta = f"{insi}{y0 % 100:02d}{min(n, 99):02d}"
        (Path(folder) / f"{wsta}.WTH").write_text(self.to_wth(insi))
        return wsta
