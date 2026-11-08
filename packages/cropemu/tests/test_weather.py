import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cropemu.weather import check, fill_gaps, nasa_power

DATA = Path(__file__).parent / "data"


def sample():
    return json.loads((DATA / "nasa_power_sample.json").read_text())


def test_parse():
    df = nasa_power.parse(sample())
    assert list(df.columns) == ["srad", "tmax", "tmin", "rain", "rhum", "wind", "dewp"]
    assert df.index[0] == pd.Timestamp("1983-12-28") and len(df) == 9
    assert df.loc[:"1983-12-31", "srad"].isna().all()          # fill value -999 -> NaN
    assert df.loc["1984-01-01", "srad"] == 27.9
    assert df.attrs["lat"] == -23.31 and df.attrs["elev"] == pytest.approx(631.22)


def test_cache_roundtrip(tmp_path, monkeypatch):
    calls = []

    def fake_request(*args, **kw):
        calls.append(args)
        return sample()

    monkeypatch.setattr(nasa_power, "_request", fake_request)
    a = nasa_power.fetch(-23.31, -51.16, "1984-01-01", "1984-01-05", cache_dir=tmp_path)
    b = nasa_power.fetch(-23.31, -51.16, "1984-01-01", "1984-01-05", cache_dir=tmp_path)
    assert len(calls) == 1                                       # second call read the cache
    pd.testing.assert_frame_equal(a, b, check_freq=False)
    assert b.attrs["elev"] == a.attrs["elev"] and "downloaded" in b.attrs


def test_fetch_validates_dates(tmp_path):
    with pytest.raises(ValueError, match="1984"):
        nasa_power.fetch(0, 0, "1981-01-01", "1985-01-01", cache_dir=tmp_path)
    with pytest.raises(ValueError, match="before"):
        nasa_power.fetch(0, 0, "1990-01-01", "1989-01-01", cache_dir=tmp_path)


def test_fetch_many_collects_errors(tmp_path, monkeypatch):
    def fake_request(lat, lon, *a):
        if lat > 50:
            raise RuntimeError("boom")
        return sample()

    monkeypatch.setattr(nasa_power, "_request", fake_request)
    pts = pd.DataFrame({"id": ["a", "b"], "lat": [-23.31, 60.0], "lon": [-51.16, 10.0]})
    res = nasa_power.fetch_many(pts, "1984-01-01", "1984-01-05", cache_dir=tmp_path, n_jobs=2)
    assert set(res) == {"a"} and "boom" in res.errors["b"]


def test_check_and_fill_gaps():
    idx = pd.date_range("2000-01-01", periods=20, freq="D")
    df = pd.DataFrame({"srad": 20.0, "tmax": 30.0, "tmin": 20.0, "rain": 1.0}, index=idx)
    df.loc[idx[3:5], "tmax"] = np.nan          # 2-day gap: filled
    df.loc[idx[8:16], "srad"] = np.nan         # 8-day gap: kept
    df.loc[idx[18], "rain"] = np.nan
    df = df.drop(idx[1])                       # missing day
    rep = check(df)
    assert not rep["ok"] and rep["missing_days"] == 1 and rep["nan"]["srad"] == 8
    out = fill_gaps(df, max_gap=3)
    assert len(out) == 20 and out["tmax"].notna().all() and out.loc[idx[18], "rain"] == 0
    assert out["srad"].isna().sum() == 8       # long gap untouched, not partly filled
    assert out.loc[idx[1], "tmin"] == 20.0


@pytest.mark.skipif(os.environ.get("CROPEMU_NETWORK_TESTS") != "1", reason="set CROPEMU_NETWORK_TESTS=1")
def test_live_request(tmp_path):
    df = nasa_power.fetch(42.0, -93.6, "2020-01-01", "2020-01-31", cache_dir=tmp_path)
    assert len(df) == 31 and check(df)["ok"]
