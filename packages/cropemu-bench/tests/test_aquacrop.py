import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cropemu_bench.design.aquacrop import AQ_PERTURBATIONS, gdd, season_crop
from cropemu_bench.models.aquacrop import AquaSoil, CropFile, crop_period_summary, day_number, read_daily, read_season
from cropemu_bench.models.aquacrop.files import (capillary_rise_parameters, curve_number, readily_evaporable_water,
                                                 soil_class, write_pro)

DATA = Path(__file__).parent / "data" / "aquacrop"


def test_day_number():
    assert day_number("2014-05-21") == 41414 and day_number("2014-10-31") == 41577   # FAO testcase dates
    assert day_number("1901-01-01") == 1


@pytest.mark.parametrize("sat, fc, wp, ksat, cn, rew, cra, crb", [
    # FAO soil database (AquaCrop 7.3 GUI, DATA/*.SOL)
    (50.0, 39.0, 23.0, 125.0, 72, 11, -0.572700, -0.859573),     # clay loam
    (55.0, 54.0, 39.0, 35.0, 77, 14, -0.608600, 0.594642),       # clay
    (46.0, 31.0, 15.0, 500.0, 61, 9, -0.453600, 0.837340),       # loam
    (36.0, 13.0, 6.0, 3000.0, 46, 4, -0.341200, 0.440738),       # sand
    (41.0, 22.0, 10.0, 1200.0, 46, 7, -0.323200, 0.219363),      # sandy loam
    (52.0, 44.0, 23.0, 150.0, 72, 13, -0.516600, 1.622512)])     # silty clay loam
def test_soil_parameters_match_fao_soils(sat, fc, wp, ksat, cn, rew, cra, crb):
    assert curve_number(ksat) == cn
    assert readily_evaporable_water(fc, wp) == rew
    a, b = capillary_rise_parameters(soil_class(sat, fc, wp, ksat), ksat)
    assert a == pytest.approx(cra, abs=1e-5) and b == pytest.approx(crb, abs=1e-5)


def _profile():
    return pd.DataFrame({"top": [0, 5, 15, 30, 60, 100], "bottom": [5, 15, 30, 60, 100, 200],
                         "ll": [0.20, 0.21, 0.22, 0.24, 0.25, 0.25], "dul": [0.31, 0.32, 0.32, 0.32, 0.32, 0.31],
                         "sat": [0.55] * 6, "ksat": [1.0, 0.5, 0.2, 0.15, 0.15, 0.2],
                         "cfvo": [10.0] * 6, "bdod": [1.2] * 6})


def test_soil_from_standard_merges_to_five_horizons():
    s = AquaSoil.from_standard(_profile())
    assert len(s.thickness) == 5 and sum(s.thickness) == pytest.approx(2.0)
    assert s.thickness[0] == pytest.approx(0.15) and s.wp[0] == pytest.approx(100 * (0.20 * 5 + 0.21 * 10) / 15)
    assert s.ksat[0] == pytest.approx(15 / (5 / 1.0 + 10 / 0.5) * 240)          # harmonic mean, mm/d
    assert 10 < s.gravel[0] < 25                                               # 10 vol% stones -> mass %
    sol = s.to_sol().splitlines()
    assert sol[4].split()[0] == "5" and len(sol) == 8 + 5
    w = s.initial_water(0.5)
    assert all(wp < x < fc for x, wp, fc in zip(w, s.wp, s.fc))


def test_crop_file_roundtrip_and_cycle_scaling(tmp_path):
    c = CropFile.read(DATA / "SoybeanGDD.CRO")
    assert c["gdd_maturity"] == 2700 and c["gdd_flowering"] == 1500 and c["hio"] == 40 and c["ccx"] == 0.98
    assert c["cgc_gdd"] == pytest.approx(0.005) and c["tbase"] == 5.0
    c2 = c.copy()
    c2.scale_cycle(0.8)
    assert c2["gdd_maturity"] == 2160 and c2["gdd_cycle"] == 2160 and c2["gdd_flowering"] == 1200
    assert c2["gdd_emergence"] == 200                                           # emergence is not scaled
    assert c2["cgc_gdd"] == pytest.approx(0.005 / 0.8, rel=1e-4)
    assert c["gdd_maturity"] == 2700                                            # copy is independent
    c2.write(tmp_path / "x.CRO")
    c3 = CropFile.read(tmp_path / "x.CRO")
    assert len(c3.lines) == len(c.lines) and c3["gdd_maturity"] == 2160 and c3["hio"] == 40


def test_season_crop_applies_design_row():
    base = CropFile.read(DATA / "SoybeanGDD.CRO")
    row = {"gdd_maturity": 2970.0, **{n: (1.1 if k == "mul" else lo) for n, (k, lo, _) in AQ_PERTURBATIONS.items()}}
    c = season_crop(base, row)
    assert c["gdd_maturity"] == 2970 and c["wp"] == 13.0 and c["plants"] == 300000
    assert c["cgc_gdd"] == pytest.approx(0.005 / 1.1 * 1.1, rel=1e-3)


def test_gdd_method_3():
    g = gdd(np.array([4.0, 20.0, 35.0, 20.0]), np.array([0.0, 10.0, 25.0, 2.0]), 5.0, 30.0)
    assert g.tolist() == [0.0, 10.0, 22.5, 6.0]


def test_read_outputs():
    s = read_season(DATA / "S0PROseason.OUT")
    assert len(s) == 1 and s.loc[0, "Y(dry)"] == pytest.approx(4.495) and "BioMass" in s
    d = read_daily(DATA / "S0PROday.OUT")
    assert {"DAP", "Stage", "CC", "Biomass", "Rain", "ETo", "Tr"} <= set(d.columns)
    p = crop_period_summary(d)
    assert p["EMR_dap"] < p["FLO_dap"] < p["YLD_dap"] < p["MAT_dap"] and p["matured"]
    golden = pd.read_csv(DATA / "golden_summary.csv").iloc[0]
    for k in ("EMR_dap", "FLO_dap", "MAT_dap", "Rain_crop", "Tr_crop", "CC_max"):
        assert p[k] == pytest.approx(golden[k])


def test_pro_file_has_the_layout_read_by_aquacrop(tmp_path):
    write_pro(tmp_path / "a.PRO", "2019-10-02", "2020-08-27", "2019-11-01", "S0.CLI", "S0.CRO", "S0.SOL",
              initial="S0.SW0")
    lines = (tmp_path / "a.PRO").read_text().splitlines()
    assert len(lines) == 2 + 5 + 42                                            # ReadNumberSimulationRuns layout
    assert lines[3].split()[0] == str(day_number("2019-10-02")) and lines[5].split()[0] == str(day_number("2019-11-01"))
    assert lines[7].startswith("-- 1. Climate") and lines[8].strip() == "S0.CLI"


aquacrop = pytest.mark.skipif(not os.environ.get("CROPEMU_AQUACROP_EXE"), reason="set CROPEMU_AQUACROP_EXE")


def _weather(start="2015-01-01", days=900, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days)
    doy = idx.dayofyear.to_numpy()
    t = 22 + 5 * np.cos(2 * np.pi * (doy - 15) / 365)                          # southern-hemisphere summer
    rain = np.where(rng.random(days) < 0.25, rng.gamma(2, 8, days), 0.0)
    return pd.DataFrame({"tmax": t + 6, "tmin": t - 6, "rain": rain, "eto": 4 + np.cos(2 * np.pi * (doy - 15) / 365)},
                        index=idx)


@aquacrop
@pytest.mark.aquacrop
def test_aquacrop_runs_rainfed_and_irrigated():
    from cropemu_bench.models.aquacrop import AquaCrop, Season

    ac = AquaCrop(crop_dir=DATA)
    soil = AquaSoil.from_standard(_profile())
    w = _weather()
    sow = pd.Timestamp("2015-11-01")
    start, end = sow - pd.Timedelta(days=30), sow + pd.Timedelta(days=300)
    seasons = [Season(w, soil, ac.crop(), sow, start, end, irrigated=irr) for irr in (False, True)]
    short = ac.crop()
    short.scale_cycle(0.8)
    seasons.append(Season(w, soil, short, sow, start, end, co2=700.0))
    seasons.append(Season(w.loc[:"2016-01-15"], soil, ac.crop(), sow, start, end))   # record too short
    r = ac.simulate(seasons, n_jobs=2, chunk_size=2).summary
    assert r.loc[:2, "matured"].all() and (r.loc[:2, "Y(dry)"] > 0.5).all()
    assert r.loc[1, "Y(dry)"] >= r.loc[0, "Y(dry)"] and r.loc[1, "Irri_crop"] > 0 and r.loc[0, "Irri_crop"] == 0
    assert r.loc[2, "MAT_dap"] < r.loc[0, "MAT_dap"] and r.loc[2, "CO2"] == pytest.approx(700, abs=1)
    assert r.loc[3, "error"].startswith("crop cycle") and not r.loc[3, "matured"]
