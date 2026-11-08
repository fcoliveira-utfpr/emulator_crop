"""Readers of DSSAT output files, on real outputs saved in tests/data (DSSAT 4.8.6.4)."""

from conftest import DATA

from cropemu_bench.models.dssat import read_daily, read_overview_stress, read_summary


def test_summary_all_columns():
    s = read_summary(DATA / "Summary.OUT")
    assert s.shape == (6, 100)
    assert list(s["run"]) == [1, 2, 3, 4, 5, 6]
    assert s["WSTA"].iloc[0] == "00001904"            # identifiers stay text
    assert s["TNAM"].tolist()[:3] == ["T1", "T1", "T2"]
    assert s["HWAM"].tolist() == [5961, 4376, 6269, 6353, 7769, 4288]
    assert s["PRCP"].isna().sum() == 0 and s["ETCP"].isna().sum() == 1   # -99 -> NaN (potential run)
    for col in ("PDAT", "ADAT", "MDAT", "CWAM", "LAIX", "NFXM", "CO2A", "TMAXA"):
        assert col in s


def test_envsum():
    e = read_summary(DATA / "EnvSum.OUT")
    assert len(e) == 6 and {"TMINA", "SRADA", "PRCP", "WSGA"} <= set(e.columns)


def test_daily_plantgro():
    g = read_daily(DATA / "PlantGro.OUT")
    assert g.groupby("run").size().to_dict() == {1: 131, 2: 129}
    assert {"YEAR", "DOY", "DAP", "LAID", "GWAD", "CWAD"} <= set(g.columns)
    last = g[g.run == 1].iloc[-1]
    assert last["GWAD"] == 5961                       # matches HWAM of run 1 in Summary.OUT


def test_overview_stress():
    o = read_overview_stress(DATA / "OVERVIEW.OUT")
    assert set(o["run"]) == {1, 2}
    assert set(o["phase"]) == {"emergence_first_flower", "first_flower_first_seed", "first_seed_phys_mat",
                               "emergence_phys_mat", "planting_to_harvest"}
    assert ((o["water_growth"] >= 0) & (o["water_growth"] <= 1)).all()
