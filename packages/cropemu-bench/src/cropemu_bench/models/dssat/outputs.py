"""Readers of DSSAT output files. Every column the file has is kept (native names)."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

MISSING_CODES = (-99, -99.0, -999, -999.0)
#: Identifier columns kept as text even when they look numeric (e.g. WSTA "00001904").
TEXT_COLUMNS = {"CR", "MODEL", "EXNAME", "TNAM", "FNAM", "WSTA", "SOIL_ID"}


def _numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Convert every column that is fully numeric (except identifiers); -99 becomes NaN."""
    out = df.copy()
    for c in out.columns:
        if c in TEXT_COLUMNS:
            continue
        conv = pd.to_numeric(out[c], errors="coerce")
        if conv.notna().sum() == out[c].replace("", np.nan).notna().sum():
            out[c] = conv.replace(list(MISSING_CODES), np.nan)
    return out


def _by_header_positions(header: str, lines: list[str]) -> pd.DataFrame:
    """Split fixed-width lines using the end position of each header name.

    DSSAT right-aligns numbers under their header; text columns (e.g. TNAM) may
    contain spaces, so splitting on whitespace would be wrong.
    """
    h = header.replace("@", " ", 1)
    names = [n.rstrip(".") or n for n in h.split()]     # "TNAM....." -> "TNAM"
    ends = [m.end() for m in re.finditer(r"\S+", h)]
    starts = [0] + ends[:-1]
    rows = [[ln[a:b].strip() for a, b in zip(starts, ends)] for ln in lines]
    return pd.DataFrame(rows, columns=names)


def read_summary(path: Path) -> pd.DataFrame:
    """All columns of ``Summary.OUT`` (or ``EnvSum.OUT``, same layout), one row per run,
    plus ``run`` (1-based, file order)."""
    text = Path(path).read_text(encoding="latin-1").splitlines()
    i = next(k for k, ln in enumerate(text) if ln.startswith("@"))
    df = _numeric(_by_header_positions(text[i], [ln for ln in text[i + 1:] if ln.strip()]))
    df.insert(0, "run", np.arange(1, len(df) + 1))
    return df


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def read_overview_stress(path: Path) -> pd.DataFrame:
    """The ENVIRONMENTAL AND STRESS FACTORS table of ``OVERVIEW.OUT``.

    Long format: one row per run and development phase, with ``run``, ``phase`` and
    the numeric columns of the table (duration, weather means, water/N/P stress).
    """
    cols = ["days", "tmax", "tmin", "tmean", "srad", "photoperiod", "co2", "rain", "et", "etp",
            "n_tmin_lt0", "n_tmin_lt2", "n_tmax_gt30", "n_tmax_gt32", "n_tmax_gt34", "n_rain_gt0",
            "water_photo", "water_growth", "n_photo", "n_growth", "p_photo", "p_growth"]
    rows, run, inside = [], 0, False
    with open(path, encoding="latin-1") as f:
        for ln in f:
            if ln.startswith("*RUN"):
                run, inside = run + 1, False      # *RUN numbers restart after 999: count instead
            elif ln.startswith("*ENVIRONMENTAL AND STRESS"):
                inside = True
            elif inside and ln.startswith("*"):
                inside = False
            elif inside and ln[:1] == " " and ln[1:24].strip() and not ln[1:2] in "-|":
                values = ln[24:].split()
                try:
                    nums = [float(v) for v in values]
                except ValueError:
                    continue
                if len(nums) == len(cols):
                    rows.append([run, _slug(ln[1:24])] + nums)
    return pd.DataFrame(rows, columns=["run", "phase"] + cols)


def read_daily(path: Path) -> pd.DataFrame:
    """A daily output file (``PlantGro.OUT``, ``SoilWat.OUT``, ...) as one table.

    Adds ``run`` (1-based, counting ``*RUN`` blocks in file order). When a run has
    several tables, they are joined on ``YEAR`` and ``DOY``.
    """
    runs: dict[int, list[pd.DataFrame]] = {}
    run, header, block = 0, None, []

    def flush():
        if header is not None and block:
            runs.setdefault(run, []).append(pd.DataFrame([b.split() for b in block],
                                                         columns=header.replace("@", " ", 1).split()))

    with open(path, encoding="latin-1") as f:
        for ln in f:
            if ln.startswith("*RUN"):
                flush()
                run, header, block = run + 1, None, []
            elif ln.startswith("@"):
                flush()
                header, block = ln, []
            elif header is not None and ln.strip() and not ln.startswith(("*", "!", "$")):
                if len(ln.split()) == len(header.split()):
                    block.append(ln)
                else:
                    flush()
                    header, block = None, []
            elif header is not None and not ln.strip():
                flush()
                header, block = None, []
    flush()

    frames = []
    for r, tables in runs.items():
        t = tables[0]
        for other in tables[1:]:
            keys = [k for k in ("YEAR", "DOY") if k in t and k in other]
            t = t.merge(other, on=keys, how="outer", suffixes=("", "_2")) if keys else pd.concat([t, other], axis=1)
        t.insert(0, "run", r)
        frames.append(t)
    if not frames:
        return pd.DataFrame(columns=["run"])
    return _numeric(pd.concat(frames, ignore_index=True))
