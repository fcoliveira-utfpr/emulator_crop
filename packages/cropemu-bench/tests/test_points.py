import numpy as np
import pandas as pd
import pytest

from cropemu_bench.inputs.points import (PointDesign, add_strata, allocate, allocate_fill, cell_of,
                                         sample_points)


def test_cell_of():
    lat, lon = cell_of([-23.2, 42.0, -0.1], [-51.2, -93.6, 0.3])
    assert lat.tolist() == [-23.25, 42.25, -0.25] and lon.tolist() == [-51.25, -93.75, 0.25]


def test_allocate_minimum_capacity_and_total():
    w = pd.Series({"a": 100.0, "b": 1.0, "c": 0.0})
    cap = pd.Series({"a": 50, "b": 3, "c": 5})
    out = allocate(w, 20, minimum=2, capacity=cap)
    assert out.sum() == 20 and (out >= 2).all() and (out <= cap).all() and out["a"] > out["b"]
    out = allocate(w, 100, minimum=2, capacity=cap)               # more than capacity: fill all
    assert out.to_dict() == {"a": 50, "b": 3, "c": 5}
    with pytest.raises(ValueError):
        allocate(w, 3, minimum=2, capacity=cap)


def test_allocate_fill_exact_total_with_existing_points():
    w = pd.Series({"a": 1.0, "b": 1.0, "c": 1.0})
    cap = pd.Series({"a": 100, "b": 100, "c": 100})
    out = allocate_fill(w, 30, minimum=1, capacity=cap, existing=pd.Series({"a": 50}))
    assert out.sum() == 30 and out["a"] == 0 and out["b"] == out["c"] == 15
    out = allocate_fill(w, 30, minimum=1, capacity=cap, existing=pd.Series({"a": 4}))
    assert out.sum() == 30 and (out + pd.Series({"a": 4, "b": 0, "c": 0})).max() - \
        (out + pd.Series({"a": 4, "b": 0, "c": 0})).min() <= 1    # balanced final totals


@pytest.mark.parametrize("n_sites", [10, 30, 50])
def test_total_is_exact_with_many_sites(n_sites):
    sites = pd.DataFrame({"site_id": [f"s{i}" for i in range(n_sites)], "lat": np.linspace(0.3, 9.7, n_sites),
                          "lon": [1.1] * n_sites})
    out = sample_points(_grid(), PointDesign(n_total=80, expansion_share=0.0, min_per_stratum=1), sites)
    assert len(out) == 80


def _grid():
    """Two climate classes x two latitude bands; soybean only in band 0-10."""
    lats = np.arange(0.25, 20, 0.5)
    lons = np.arange(0.25, 10, 0.5)
    la, lo = np.meshgrid(lats, lons, indexing="ij")
    df = pd.DataFrame({"lat": la.ravel(), "lon": lo.ravel()})
    df["koppen"] = np.where(df["lon"] < 5, "Aw", "Cfa")
    df["koppen"] = np.where(df["lat"] > 19, "ET", df["koppen"])
    df["soy_ha"] = np.where(df["lat"] < 10, 2000.0, 0.0)
    df["other_ha"] = 10000.0
    return df


def test_sample_points_structure_and_reproducibility():
    d = PointDesign(n_total=60, expansion_share=0.25, min_per_stratum=2, block=5.0)
    a = sample_points(_grid(), d)
    b = sample_points(_grid(), d)
    pd.testing.assert_frame_equal(a, b)                           # fixed seed
    assert len(a) == 60 and a["id"].is_unique
    assert a["kind"].value_counts().to_dict() == {"soy": 45, "expansion": 15}
    assert (a.loc[a.kind == "soy", "soy_ha"] >= d.min_soy_ha).all()
    assert (a.loc[a.kind == "expansion", "lat"] > 10).all()
    assert set(a["stratum"].str.split("|").str[0]) <= {"Aw", "Cfa"}   # ET excluded
    assert not a.duplicated(["lat", "lon"]).any()


def test_sites_reduce_fill_in_their_stratum():
    d = PointDesign(n_total=40, expansion_share=0.0, min_per_stratum=1)
    sites = pd.DataFrame({"site_id": [f"s{i}" for i in range(10)], "lat": np.linspace(0.3, 9.7, 10),
                          "lon": [1.1] * 10})
    out = sample_points(_grid(), d, sites)
    assert (out["kind"] == "site").sum() == 10 and out.loc[out.kind == "site", "id"].iloc[0] == "site:s0"
    fill = out[out.kind == "soy"]
    aw = (fill["koppen"] == "Aw").sum()
    cfa = (fill["koppen"] == "Cfa").sum()
    assert cfa > aw                                               # the stratum with sites got fewer
    site_cells = set(zip(*cell_of(sites["lat"], sites["lon"])))
    assert not site_cells & set(zip(fill["lat"], fill["lon"]))   # no fill point on a site's cell


def test_strata_and_blocks():
    s = add_strata(pd.DataFrame({"lat": [-23.25, 42.25], "lon": [-51.25, -93.75], "koppen": ["Cfa", "Dfa"]}))
    assert s["stratum"].tolist() == ["Cfa|-30", "Dfa|40"]
    assert s["block"].tolist() == ["-5_-11", "8_-19"]


@pytest.mark.skipif(__import__("os").environ.get("CROPEMU_NETWORK_TESTS") != "1",
                    reason="set CROPEMU_NETWORK_TESTS=1 (downloads ~160 MB once into the cache)")
def test_real_global_grid():
    from cropemu_bench.inputs.calendar import CropCalendar
    from cropemu_bench.inputs.points import grid_table

    g = grid_table()
    assert 115e6 < g["soy_ha"].sum() < 125e6                     # ~120 Mha of soybean in 2015
    pts = sample_points(g, PointDesign(n_total=500))
    assert len(pts) == 500 and not pts["koppen"].isin(["ET", "EF"]).any()
    cal = CropCalendar("rf").table(pts, max_distance=2)
    assert cal["planting_doy"].notna().mean() > 0.95             # almost every point has a calendar
