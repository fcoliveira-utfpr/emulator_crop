"""Daily weather sequences of every season of a dataset (input of the convolutional emulator).

Computed with :func:`cropemu.features.season_sequence`, the code the library uses to predict,
and cached as ``<out_dir>/sequence.npy`` (float16, seasons x channels x days, rows in the order of
``sequence_index.parquet``).
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from cropemu.features import SEQUENCE_CHANNELS, SEQUENCE_DAYS, WeatherSeries, season_sequence
from cropemu.weather import fetch, fill_gaps

from .pipeline import WEATHER_END, WEATHER_START, load


def build_sequences(out_dir, X: pd.DataFrame, cache: bool = True, verbose: bool = True) -> np.ndarray:
    """Sequences of the seasons of ``X`` (index ``sample``; ``paw_mm`` column), in its row order.

    Returns a read-only memory map (float16)."""
    out = Path(out_dir)
    path, ipath = out / "sequence.npy", out / "sequence_index.parquet"
    if cache and path.exists() and ipath.exists():
        idx = pd.read_parquet(ipath)["sample"]
        seq = np.load(path, mmap_mode="r")
        pos = pd.Series(np.arange(len(idx)), index=idx.to_numpy())
        if X.index.isin(pos.index).all():
            rows = pos.loc[X.index].to_numpy()
            return seq if np.array_equal(rows, np.arange(len(seq))) else seq[rows]
    t = load(out)
    design = t["design"].set_index("sample").loc[X.index]
    pts = t["points"].set_index("id")
    n = SEQUENCE_DAYS[1] - SEQUENCE_DAYS[0] + 1
    seq = np.lib.format.open_memmap(path, mode="w+", dtype=np.float16, shape=(len(X), len(SEQUENCE_CHANNELS), n))
    pos = {s: i for i, s in enumerate(X.index)}
    paw = X["paw_mm"].to_numpy(float)
    t0 = time.time()
    for k, (pid, g) in enumerate(design.groupby("point", sort=False)):
        p = pts.loc[pid]
        w = WeatherSeries(fill_gaps(fetch(p["lat"], p["lon"], WEATHER_START, WEATHER_END)), p["lat"], p["elev"])
        for s, r in zip(g.index, g[["sowing", "dt", "rain_factor"]].itertuples(index=False)):
            i = pos[s]
            seq[i] = season_sequence(w, r.sowing, paw[i], float(r.dt), float(r.rain_factor))
        if verbose and k % 200 == 0:
            print(f"  sequences: point {k}/{design['point'].nunique()} ({(time.time() - t0) / 60:.1f} min)", flush=True)
    seq.flush()
    pd.DataFrame({"sample": X.index}).to_parquet(ipath)
    return np.load(path, mmap_mode="r")
