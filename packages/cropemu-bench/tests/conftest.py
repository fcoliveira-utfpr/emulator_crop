import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cropemu_bench.models.dssat import SoilProfile, Weather

DATA = Path(__file__).parent / "data"


def synthetic_weather(lat=-23.3, start="2019-01-01", end="2022-12-31", seed=1) -> Weather:
    """Deterministic subtropical weather (southern hemisphere), for tests only."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, end, freq="D")
    s = np.cos(2 * np.pi * (idx.dayofyear.values - 15) / 365)
    tmax = 28 + 4 * s + rng.normal(0, 2, len(idx))
    tmin = 16 + 4 * s + rng.normal(0, 1.5, len(idx))
    srad = 18 + 5 * s + rng.normal(0, 3, len(idx)).clip(-10, 10)
    rain = np.where(rng.random(len(idx)) < 0.3 + 0.1 * s, rng.gamma(1.2, 12, len(idx)), 0.0)
    df = pd.DataFrame({"srad": srad.clip(2, 32), "tmax": tmax, "tmin": np.minimum(tmin, tmax - 2),
                       "rain": rain}, index=idx)
    return Weather(df, lat=lat, lon=-51.2, elev=550)


def clay_soil() -> SoilProfile:
    """Generic clayey profile, for tests only (not a research soil)."""
    layers = pd.DataFrame({
        "slb": [10, 30, 60, 100, 150], "slll": [0.25, 0.26, 0.27, 0.28, 0.28],
        "sdul": [0.38, 0.39, 0.40, 0.40, 0.40], "ssat": [0.50, 0.50, 0.49, 0.48, 0.48],
        "srgf": [1.0, 0.7, 0.4, 0.2, 0.1], "ssks": [1.5] * 5, "sbdm": [1.2, 1.25, 1.3, 1.3, 1.3],
        "sloc": [1.8, 1.2, 0.8, 0.5, 0.3], "slcl": [60] * 5, "slsi": [20] * 5,
        "slni": [0.15, 0.1, 0.07, 0.05, 0.03], "slhw": [5.5] * 5})
    return SoilProfile(layers, texture="C")


@pytest.fixture
def weather():
    return synthetic_weather()


@pytest.fixture
def soil():
    return clay_soil()


@pytest.fixture(scope="session")
def dssat_paths():
    exe, home = os.environ.get("CROPEMU_DSSAT_EXE"), os.environ.get("CROPEMU_DSSAT_HOME")
    if not exe or not home:
        pytest.skip("set CROPEMU_DSSAT_EXE and CROPEMU_DSSAT_HOME to run DSSAT tests")
    return exe, home
