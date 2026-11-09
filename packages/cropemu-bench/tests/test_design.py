from datetime import date

import numpy as np
import pandas as pd
import pytest

from cropemu_bench.design import SeasonDesign, design_seasons, mg_center, to_treatments
from cropemu_bench.design.cultivars import MG_ROWS, PERTURBATIONS, MGTable, cultivar_from_mg, ecotype
from cropemu_bench.models.dssat import COEFFICIENTS, Cultivar


@pytest.fixture
def table(tmp_path):
    """Fake DSSAT home: MG rows whose coefficients grow linearly with MG, plus MINIMA/MAXIMA."""
    genotype = tmp_path / "Genotype"
    genotype.mkdir()
    lines = ["*SOYBEAN CULTIVAR COEFFICIENTS: CRGRO048 MODEL",
             "@VAR#  VAR-NAME........ EXPNO   ECO#  " + " ".join(f"{c:>5s}" for c in COEFFICIENTS)]
    base = np.array([13.0, 0.25, 19.0, 7.0, 14.0, 33.0, 20.0, 1.0, 375, 180, 1.0, 0.18, 23, 2.1, 10, 77, 0.4, 0.2])
    for mg, cid in MG_ROWS.items():
        v = base.copy()
        v[0] -= 0.2 * mg                                           # CSDL decreases with MG
        v[2] += 0.5 * mg                                           # EM-FL increases with MG
        lines.append(Cultivar(cid, ecotype(mg), dict(zip(COEFFICIENTS, v)), f"MG {mg}").to_line())
    lo = Cultivar("999991", "DFAULT", dict(zip(COEFFICIENTS, base * 0.5)), "MINIMA")
    hi = Cultivar("999992", "DFAULT", dict(zip(COEFFICIENTS, base * 1.5)), "MAXIMA")
    lines += [lo.to_line(), hi.to_line()]
    (genotype / "SBGRO048.CUL").write_text("\n".join(lines) + "\n")
    return MGTable(tmp_path)


def test_mg_center():
    assert mg_center([0, -23, 40, 50]).tolist() == [9.0, 6.5, 3.0, -1.5]


def test_baseline_interpolates_mg(table):
    c = cultivar_from_mg(table, "Z00000", 2.5)
    assert c.coefficients["CSDL"] == pytest.approx(13.0 - 0.5)
    assert c.coefficients["EM-FL"] == pytest.approx(19.0 + 1.25)
    assert c.ecotype == "SB0201" or c.ecotype == "SB0301"          # nearest MG (round half to even)
    assert cultivar_from_mg(table, "Z00000", -1.6).ecotype == "SB0001"


def test_perturbations_and_limits(table):
    lo = cultivar_from_mg(table, "Z00000", 5, {c: 0.0 for c in PERTURBATIONS})
    hi = cultivar_from_mg(table, "Z00001", 5, {c: 1.0 for c in PERTURBATIONS})
    mid = cultivar_from_mg(table, "Z00002", 5, {c: 0.5 for c in PERTURBATIONS})
    base = cultivar_from_mg(table, "Z00003", 5)
    assert lo.coefficients["CSDL"] == pytest.approx(base.coefficients["CSDL"] - 0.3)
    assert hi.coefficients["SD-PM"] == pytest.approx(base.coefficients["SD-PM"] * 1.15)
    for k in PERTURBATIONS:
        assert mid.coefficients[k] == pytest.approx(base.coefficients[k])
        assert table.low[COEFFICIENTS.index(k)] <= lo.coefficients[k] <= table.high[COEFFICIENTS.index(k)]
    assert lo.coefficients["XFRT"] == base.coefficients["XFRT"]   # not perturbed


def test_design_seasons(table):
    points = pd.DataFrame({"id": ["a", "b", "c"], "lat": [-23.25, 42.25, 10.0]})
    cal = pd.DataFrame({"id": ["a", "b", "c"], "planting_doy": [304, 123, np.nan]})
    d = SeasonDesign(seasons_per_point=40, perturbed_share=0.25, potential_share=0.2)
    seasons, cultivars = design_seasons(points, cal, table, d)
    assert len(seasons) == 80 and set(seasons["point"]) == {"a", "b"}          # c has no calendar
    assert seasons["sample"].tolist() == list(range(80)) and seasons["cultivar"].is_unique
    assert [c.id for c in cultivars] == seasons["cultivar"].tolist()
    assert seasons["year"].between(d.first_year, d.last_year).all()
    a = seasons[seasons.point == "a"]
    assert a["sowing_offset"].abs().max() <= 30 and a["sowing_offset"].std() > 10   # spread by LHS
    assert (a["mg"] - mg_center(-23.25)).abs().max() <= 2.0
    assert 0.1 < (~seasons["water"]).mean() < 0.3 and 0.15 < seasons["perturbed"].mean() < 0.35
    p = seasons[seasons.perturbed]
    assert p["co2"].between(350, 800).all() and p["dt"].between(-1, 4).all()
    assert seasons.loc[~seasons.perturbed, "co2"].isna().all()
    again, _ = design_seasons(points, cal, table, d)
    pd.testing.assert_frame_equal(seasons, again)                             # reproducible

    t = to_treatments(seasons, {"a": "SOILA00001", "b": "SOILB00001"}, d)
    assert len(t) == 80 and t[0].weather == seasons["point"].iloc[0]
    assert (t[0].planting - t[0].start).days == d.start_days_before_sowing
    k = int(np.flatnonzero(seasons["perturbed"])[0])
    assert t[k].environment.co2 == pytest.approx(seasons["co2"].iloc[k])
    assert t[0].initial_water == d.initial_water
    assert isinstance(seasons["sowing"].iloc[0], date)
