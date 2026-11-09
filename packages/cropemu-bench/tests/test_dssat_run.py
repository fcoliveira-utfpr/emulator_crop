"""Runs of the real DSSAT executable (skipped unless CROPEMU_DSSAT_EXE and CROPEMU_DSSAT_HOME are set).

Regression reference: tests/data/golden_summary.csv. Regenerate it on purpose (new DSSAT
version, intended change in the writers) with CROPEMU_UPDATE_GOLDEN=1.
"""

import os
from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest
from conftest import DATA, clay_soil, synthetic_weather

from cropemu_bench.models.dssat import DSSAT, Cultivar, EnvironmentModification, Treatment, default_cultivar

pytestmark = pytest.mark.dssat
SOIL = "CEMUSOIL01"
GOLDEN = DATA / "golden_summary.csv"
GOLDEN_COLUMNS = ["treatment", "season", "PDAT", "EDAT", "ADAT", "MDAT", "HWAM", "CWAM", "LAIX", "PRCP",
                  "ETCP", "CO2A"]


@pytest.fixture(scope="module")
def model(dssat_paths, tmp_path_factory):
    exe, home = dssat_paths
    return DSSAT(exe, home, workdir=tmp_path_factory.mktemp("dssat"))


@pytest.fixture(scope="module")
def inputs():
    return {"weather": {"w1": synthetic_weather()}, "soils": {SOIL: clay_soil()}}


def base_treatment(**kw):
    return Treatment("w1", SOIL, "990006", date(2019, 11, 1), **kw)


@pytest.fixture(scope="module")
def scenario(model, inputs):
    late = default_cultivar(model.dssat_home, "990006")
    custom = Cultivar("CE0001", late.ecotype, late.with_(EM_FL=24.0).coefficients)
    T = [base_treatment(seasons=2),
         base_treatment(water=False),
         replace(base_treatment(), cultivar="CE0001"),
         base_treatment(environment=EnvironmentModification(co2=700)),
         base_treatment(environment=EnvironmentModification(tmax_add=3, tmin_add=3)),
         base_treatment(irrigation=True),
         base_treatment(seasons=2, environment=EnvironmentModification(co2=700))]
    res = model.simulate(T, cultivars=[custom], daily=("growth",), **inputs)
    return T, [custom], res


def row(res, t, s=0):
    return res.summary.query("treatment == @t and season == @s").iloc[0]


def test_one_row_per_season(scenario):
    T, _, res = scenario
    assert len(res.summary) == sum(t.seasons for t in T)
    assert row(res, 0, 1)["PDAT"] == 2020305                   # second season, same planting day


def test_expected_responses(scenario):
    _, _, res = scenario
    base = row(res, 0)
    assert base["EDAT"] < base["ADAT"] < base["MDAT"]
    assert row(res, 1)["HWAM"] >= base["HWAM"]                 # potential >= rainfed
    assert row(res, 2)["ADAT"] > base["ADAT"]                  # longer EM-FL: later flowering
    assert row(res, 3)["HWAM"] > base["HWAM"]                  # CO2 700 ppm
    assert abs(row(res, 3)["CO2A"] - 700) < 1
    assert row(res, 4)["MDAT"] < base["MDAT"]                  # +3 °C: shorter cycle
    assert row(res, 5)["IRCM"] > 0                             # automatic irrigation applied


def test_environment_applies_to_every_season(scenario):
    _, _, res = scenario
    assert abs(row(res, 6, 0)["CO2A"] - 700) < 1
    assert abs(row(res, 6, 1)["CO2A"] - 700) < 1


def test_daily_matches_summary(scenario):
    _, _, res = scenario
    g = res.daily["PlantGro"]
    last = g.groupby(["treatment", "season"]).tail(1).set_index(["treatment", "season"])["GWAD"]
    hwam = res.summary.set_index(["treatment", "season"])["HWAM"]
    pd.testing.assert_series_equal(last.sort_index(), hwam.sort_index(), check_names=False, check_dtype=False)
    assert {"envsum", "overview_stress"} <= set(res.extra)


def test_chunks_and_threads_do_not_change_results(model, inputs, scenario):
    T, cultivars, res = scenario
    again = model.simulate(T, cultivars=cultivars, chunk_size=2, n_jobs=3, overview=False, **inputs)
    pd.testing.assert_frame_equal(again.summary.drop(columns=["RUNNO", "TRNO", "TNAM", "FNAM"]),
                                  res.summary.drop(columns=["RUNNO", "TRNO", "TNAM", "FNAM"]))


def test_co2_from_weather_file(model):
    w = synthetic_weather()
    w.co2 = 600
    res = model.simulate([base_treatment(co2_method="W")], weather={"w1": w}, soils={SOIL: clay_soil()})
    assert abs(res.summary["CO2A"].iloc[0] - 600) < 1


def test_golden_regression(scenario):
    _, _, res = scenario
    got = res.summary[GOLDEN_COLUMNS].reset_index(drop=True)
    if os.environ.get("CROPEMU_UPDATE_GOLDEN") == "1" or not GOLDEN.exists():
        got.to_csv(GOLDEN, index=False)
        pytest.skip("golden summary written")
    expected = pd.read_csv(GOLDEN)
    assert got[["treatment", "season"]].equals(expected[["treatment", "season"]].astype(got["treatment"].dtype))
    # Other compilers/platforms may differ by floating point: allow 1 day in dates, 1% in quantities.
    for c in ("PDAT", "EDAT", "ADAT", "MDAT"):
        days = (pd.to_datetime(got[c].astype(int).astype(str), format="%Y%j")
                - pd.to_datetime(expected[c].astype(int).astype(str), format="%Y%j")).dt.days
        assert days.abs().max() <= 1, c
    for c in ("HWAM", "CWAM", "LAIX", "PRCP", "ETCP", "CO2A"):
        np.testing.assert_allclose(got[c], expected[c], rtol=0.01, equal_nan=True, err_msg=c)


@pytest.mark.skipif(os.environ.get("CROPEMU_NETWORK_TESTS") != "1", reason="set CROPEMU_NETWORK_TESTS=1")
def test_nasa_power_to_dssat(model, tmp_path):
    """Real weather end to end: NASA POWER -> cropemu standard -> DSSAT."""
    from cropemu.weather import check, fetch, fill_gaps

    from cropemu_bench.models.dssat import Weather

    df = fill_gaps(fetch(-23.2, -51.2, "2015-01-01", "2020-12-31", cache_dir=tmp_path))
    assert check(df)["ok"]
    w = Weather.from_standard(df)
    assert w.data["wind"].median() > 20                          # m/s converted to km/d
    T = [Treatment("lond", SOIL, "990006", date(2016, 10, 20), seasons=4, evapotranspiration="F")]
    res = model.simulate(T, weather={"lond": w}, soils={SOIL: clay_soil()})
    assert len(res.summary) == 4 and (res.summary["HWAM"] > 500).all()


@pytest.mark.skipif(os.environ.get("CROPEMU_NETWORK_TESTS") != "1", reason="set CROPEMU_NETWORK_TESTS=1")
def test_real_weather_and_soil_to_dssat(model, tmp_path):
    """NASA POWER + SoilGrids -> DSSAT at one point."""
    pytest.importorskip("rasterio")
    from cropemu.soil import hydraulics, soilgrids
    from cropemu.weather import fetch, fill_gaps

    from cropemu_bench.models.dssat import SoilProfile, Weather

    lat, lon = -23.2, -51.2
    soil = SoilProfile.from_standard(hydraulics(soilgrids.fetch(lat, lon, cache_dir=tmp_path)))
    assert soil.texture in ("C", "SIC", "CL", "SC") and soil.depth == 200
    w = Weather.from_standard(fill_gaps(fetch(lat, lon, "2015-01-01", "2020-12-31", cache_dir=tmp_path)))
    T = [Treatment("p", "SGLOND0001", "990006", date(2016, 10, 20), seasons=4, evapotranspiration="F")]
    res = model.simulate(T, weather={"p": w}, soils={"SGLOND0001": soil})
    assert len(res.summary) == 4 and (res.summary["HWAM"] > 500).all()


def test_sliced_weather_gives_identical_results(model, inputs):
    """Short weather files (from the day before the start) give the same results as the full series."""
    w = inputs["weather"]["w1"]
    T = [base_treatment(), base_treatment(water=False), replace(base_treatment(), planting=date(2020, 11, 20),
                                                                start=date(2020, 10, 21))]
    full = model.simulate(T, **inputs)
    sliced_w, T2 = {}, []
    for t in T:
        key = f"w1|{t.start}"
        sliced_w[key] = w.slice(pd.Timestamp(t.start) - pd.Timedelta(days=1),
                                pd.Timestamp(t.start) + pd.Timedelta(days=420))
        T2.append(replace(t, weather=key))
    sliced = model.simulate(T2, weather=sliced_w, soils=inputs["soils"])
    skip = ["RUNNO", "TRNO", "TNAM", "FNAM", "WSTA", "WYEAR"]
    pd.testing.assert_frame_equal(full.summary.drop(columns=skip), sliced.summary.drop(columns=skip))
