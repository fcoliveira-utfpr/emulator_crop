import numpy as np
import pandas as pd
import pytest

from cropemu.features import (WINDOW_VARIABLES, WINDOWS, WeatherSeries, co2_at, daylength, season_features,
                              soil_features)


def _weather():
    idx = pd.date_range("2019-01-01", "2020-12-31", freq="D")
    n = len(idx)
    return pd.DataFrame({"tmax": np.full(n, 30.0), "tmin": np.full(n, 18.0), "srad": np.full(n, 20.0),
                         "rain": np.full(n, 2.0), "rhum": np.full(n, 70.0)}, index=idx)


def test_daylength():
    assert daylength(0, 80, sun_angle=-0.833) == pytest.approx(12.1, abs=0.1)
    assert daylength(-23.3, 355) > daylength(-23.3, 172)          # southern summer
    assert daylength(42, 172) == pytest.approx(16.4, abs=0.2)     # Iowa, civil twilight
    assert daylength(80, 172) == 24


def test_co2():
    assert 344 < co2_at("1985-06-01") < 348
    assert co2_at("2024-12-01") > co2_at("2000-01-01") > 360
    assert co2_at("1900-01-01") == co2_at("1800-01-01")          # clamped at the ends


def test_season_features_and_perturbation():
    w = WeatherSeries(_weather(), lat=-23.3)
    f = season_features(w, "2019-11-01")
    assert len(f) == len(WINDOWS) * len(WINDOW_VARIABLES) + 3
    assert f["tmax_0_30"] == 30 and f["rain_0_30"] == 60 and f["rain_-30_0"] == 60 and f["hot32_0_30"] == 0
    g = season_features(w, "2019-11-01", dt=3, rain_factor=0.5)
    assert g["tmax_0_30"] == 33 and g["tmin_30_60"] == 21 and g["rain_0_30"] == 30 and g["hot32_0_30"] == 30
    assert g["vpd_0_30"] > f["vpd_0_30"]                           # warmer air, same vapour: drier
    with pytest.raises(ValueError, match="cover"):
        season_features(w, "2020-11-01")                           # 130 days after: beyond the data


def test_soil_features():
    p = pd.DataFrame({"top": [0, 15, 30], "bottom": [15, 30, 100], "ll": [0.2, 0.2, 0.25], "dul": [0.35, 0.33, 0.35],
                      "clay": [40, 50, 60], "sand": [30, 25, 20], "soc": [2, 1, 0.5], "bdod": [1.2, 1.3, 1.3]})
    f = soil_features(p)
    assert f["paw_mm"] == pytest.approx(150 * 0.15 + 150 * 0.13 + 700 * 0.10)
    assert f["paw30_mm"] == pytest.approx(150 * 0.15 + 150 * 0.13)
    assert f["clay30"] == pytest.approx(45) and f["depth_cm"] == 100


def test_thermal_days():
    from cropemu.features import WeatherSeries, gdd

    idx = pd.date_range("2000-01-01", periods=400)
    df = pd.DataFrame({"tmax": 25.0, "tmin": 15.0, "srad": 20.0, "rain": 0.0}, index=idx)   # 15 GDD/day (base 5)
    w = WeatherSeries(df, -23.0)
    assert gdd(np.array([25.0]), np.array([15.0]), 5, 30)[0] == 15
    d = w.thermal_days("2000-02-01", {"a": 150, "b": 151, "c": 1e6}, 5.0, 30.0, max_days=300)
    assert d == {"a": 10.0, "b": 11.0, "c": 300.0}
    assert w.thermal_days("2000-02-01", {"a": 150}, 5.0, 30.0, dt=5.0)["a"] == 8.0      # 20 GDD/day
