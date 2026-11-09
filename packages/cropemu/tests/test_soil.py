import os

import numpy as np
import pandas as pd
import pytest

from cropemu.soil import hydraulics, saxton_rawls, texture_class


@pytest.mark.parametrize("sand, clay, expected", [
    (92, 3, "S"), (82, 6, "LS"), (65, 10, "SL"), (40, 20, "L"), (20, 15, "SIL"), (10, 5, "SI"),
    (60, 25, "SCL"), (32, 33, "CL"), (10, 35, "SICL"), (50, 40, "SC"), (5, 45, "SIC"), (20, 60, "C")])
def test_texture_class(sand, clay, expected):
    assert texture_class(sand, clay) == expected


def test_saxton_rawls_reference_values():
    # Saxton & Rawls (2006), Table 3 (OM 2.5%, no density adjustment): loam ~ θ1500 0.14,
    # θ33 0.27, θS 0.47 (rounded); clay has much more water at both potentials.
    loam = saxton_rawls(40, 20, 2.5)
    assert loam["ll"] == pytest.approx(0.14, abs=0.015)
    assert loam["dul"] == pytest.approx(0.27, abs=0.02)
    assert loam["sat"] == pytest.approx(0.47, abs=0.03)
    clay = saxton_rawls(25, 50, 2.5)
    assert clay["ll"] > loam["ll"] + 0.1 and clay["dul"] > loam["dul"] + 0.1
    sand = saxton_rawls(88, 5, 2.5)
    assert sand["ksat"] > loam["ksat"] > clay["ksat"]


def _profile():
    return pd.DataFrame({"top": [0, 30], "bottom": [30, 100], "clay": [40, 50], "sand": [30, 25],
                         "silt": [30, 25], "soc": [1.5, 0.5], "bdod": [1.2, 1.35],
                         "wv1500": [0.22, np.nan], "wv0033": [0.36, np.nan]})


def test_hydraulics_soilgrids_with_fallback():
    p = hydraulics(_profile())
    assert p.loc[0, "ll"] == 0.22 and p.loc[0, "dul"] == 0.36
    assert p.loc[0, "sat"] == pytest.approx(1 - 1.2 / 2.65)
    sr = saxton_rawls(25, 50, 0.5 * 1.724, 1.35)
    assert p.loc[1, "ll"] == pytest.approx(sr["ll"])               # no wv data: Saxton & Rawls
    assert ((p["ll"] < p["dul"]) & (p["dul"] < p["sat"])).all()


def test_hydraulics_enforces_order():
    p = _profile()
    p.loc[0, "wv0033"] = 0.21                                       # dul below ll in the data
    out = hydraulics(p, min_gap=0.02)
    assert out.loc[0, "dul"] == pytest.approx(0.24)


@pytest.mark.skipif(os.environ.get("CROPEMU_NETWORK_TESTS") != "1", reason="set CROPEMU_NETWORK_TESTS=1")
def test_soilgrids_live(tmp_path):
    pytest.importorskip("rasterio")
    from cropemu.soil import soilgrids

    pts = pd.DataFrame({"id": ["londrina", "ocean"], "lat": [-23.2, -30.0], "lon": [-51.2, -30.0]})
    res = soilgrids.fetch_many(pts, cache_dir=tmp_path, n_jobs=8)
    lond = res["londrina"]
    assert len(lond) == 6 and lond["clay"].iloc[0] > 30           # clayey oxisol region
    assert res["ocean"]["clay"].isna().all()
    again = soilgrids.fetch_many(pts.iloc[:1], cache_dir=tmp_path)   # from the cache
    pd.testing.assert_frame_equal(again["londrina"], lond)


def test_soilgrids_failed_reads_are_not_cached(tmp_path, monkeypatch):
    from cropemu.soil import soilgrids

    calls = {"n": 0}

    def fake_sample(path, lats, lons, radius, retries=4):
        calls["n"] += 1
        values = np.full(len(lats), 300.0)                          # e.g. 30% clay everywhere
        failed = np.asarray(lats) > 50                             # points north of 50° "lose the network"
        return values, failed

    monkeypatch.setattr(soilgrids, "_sample_file", fake_sample)
    pts = pd.DataFrame({"id": ["ok", "bad"], "lat": [-23.2, 60.0], "lon": [-51.2, 10.0]})
    res = soilgrids.fetch_many(pts, cache_dir=tmp_path, n_jobs=2)
    assert res["ok"]["clay"].iloc[0] == pytest.approx(30.0) and "error" not in res["ok"].attrs
    assert res["bad"]["clay"].isna().all() and "error" in res["bad"].attrs
    assert len(list(tmp_path.glob("*.csv"))) == 1                  # only the good point is cached
    n = calls["n"]
    soilgrids.fetch_many(pts, cache_dir=tmp_path, n_jobs=2)        # retries only the failed point
    assert calls["n"] == n + len(soilgrids.PROPERTIES) * len(soilgrids.DEPTHS)
