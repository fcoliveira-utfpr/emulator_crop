"""Quality checks and gap filling of daily weather (cropemu standard format)."""

from __future__ import annotations

import pandas as pd

#: Plausible ranges of each column (outside them a value is flagged).
RANGES = {"srad": (0, 45), "tmax": (-50, 60), "tmin": (-60, 45), "rain": (0, 1000), "rhum": (0, 100),
          "wind": (0, 40), "dewp": (-70, 40)}


def check(df: pd.DataFrame) -> dict:
    """Report problems: missing days, NaN per column, values out of range, tmin > tmax."""
    idx = pd.DatetimeIndex(df.index)
    full = pd.date_range(idx.min(), idx.max(), freq="D")
    report = {"missing_days": int(len(full) - len(idx.unique())),
              "nan": {c: int(df[c].isna().sum()) for c in df if df[c].isna().any()},
              "out_of_range": {}, "tmin_gt_tmax": 0}
    for c, (lo, hi) in RANGES.items():
        if c in df:
            n = int(((df[c] < lo) | (df[c] > hi)).sum())
            if n:
                report["out_of_range"][c] = n
    if {"tmin", "tmax"} <= set(df):
        report["tmin_gt_tmax"] = int((df["tmin"] > df["tmax"]).sum())
    report["ok"] = not (report["missing_days"] or report["nan"] or report["out_of_range"]
                        or report["tmin_gt_tmax"])
    return report


def fill_gaps(df: pd.DataFrame, max_gap: int = 5) -> pd.DataFrame:
    """Reindex to every day and fill NaN runs of up to ``max_gap`` days.

    Temperatures, radiation, humidity, wind and dew point are interpolated
    linearly; missing rain is set to 0. Longer gaps stay NaN (check with :func:`check`).
    """
    idx = pd.DatetimeIndex(df.index)
    out = df.reindex(pd.date_range(idx.min(), idx.max(), freq="D"))
    out.index.name = df.index.name
    for c in out:
        gap = out[c].isna()
        run_length = gap.groupby((~gap).cumsum()).transform("sum")   # length of the NaN run of each day
        short = gap & (run_length <= max_gap)
        if c == "rain":
            out.loc[short, c] = 0.0
        else:
            filled = out[c].interpolate(limit_area="inside")
            out.loc[short, c] = filled[short]
    out.attrs = dict(df.attrs)
    return out


def fill_from(df: pd.DataFrame, other: pd.DataFrame, columns=None) -> pd.DataFrame:
    """Complete ``df`` (e.g. a weather station) with ``other`` (e.g. NASA POWER at the same point).

    The result covers the days of both; every missing value of ``df`` in ``columns`` (default:
    the columns of ``other``) is taken from ``other`` on the same day. ``df`` keeps its values
    and attrs; ``attrs["filled_from"]`` counts the values taken per column. No bias correction:
    check the agreement of the two sources on the common days first.
    """
    cols = list(other.columns if columns is None else columns)
    idx = pd.DatetimeIndex(df.index).union(pd.DatetimeIndex(other.index))
    out = df.reindex(idx)
    out.index.name = df.index.name or "date"
    o = other.reindex(idx)
    filled = {}
    for c in cols:
        if c not in o:
            continue
        if c not in out:
            out[c] = float("nan")
        miss = out[c].isna() & o[c].notna()
        out.loc[miss, c] = o.loc[miss, c]
        if miss.any():
            filled[c] = int(miss.sum())
    out.attrs = {**dict(df.attrs), "filled_from": {"source": other.attrs.get("source", "other"), **filled}}
    return out
