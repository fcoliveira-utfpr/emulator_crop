"""Readers of DSSAT files and the helpers for own data (synthetic files in the DSSAT formats)."""

import numpy as np
import pandas as pd
import pytest

import cropemu
from cropemu.features import WeatherSeries
from cropemu.io import dssat_date, read_cul, read_experiment, read_observed, read_sol, read_wth
from cropemu.soil import fill_from as soil_fill_from
from cropemu.weather import fill_from

WTH_A = """*WEATHER DATA : Test station

@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT
  TEST   -23.500  -51.200   600  21.0   5.0   2.0  10.0
@DATE  SRAD  TMAX  TMIN  RAIN  DEWP  WIND
20001  20.0  30.0  18.0   0.0  15.0 172.8
20002  21.0  31.0  19.0  12.5   -99 172.8
20003  19.0  29.0  18.5   3.0  16.0   -99
"""
WTH_B = """*WEATHER DATA : Test station, blank columns

@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT
  TEST   -23.500  -51.200   600  21.0   5.0 -99.0 -99.0
@DATE  SRAD  TMAX  TMIN  RAIN  DEWP  WIND   PAR
20005  18.0  28.0  17.0   1.0
20006  17.0  27.0  16.0   0.0
"""
SOL = """*TEST000001  TEST        C       150  Test clay
@SITE        COUNTRY          LAT     LONG SCS FAMILY
 Some Town   Brazil        -23.500  -51.200 Test family
@ SCOM  SALB  SLU1  SLDR  SLRO  SLNF  SLPF  SMHB  SMPX  SMKE
     R   .14     6    .6    60     1     1 IB001 IB001 IB001
@  SLB  SLMH  SLLL  SDUL  SSAT  SRGF  SSKS  SBDM  SLOC  SLCL  SLSI  SLCF  SLNI  SLHW  SLHB  SCEC  SADC
    20   -99  .250  .380  .500     1   .50  1.20  1.50    60    20   -99   -99   5.5   -99   -99   -99
    60   -99  .270  .390  .490    .5   .40  1.25   -99    62    18   -99   -99   5.4   -99   -99   -99
   250   -99  .280  .400  .480    .1   .30  1.30   .30    65    15   -99   -99   5.3   -99   -99   -99
@  SLB  SLPX  SLPT  SLPO CACO3  SLAL  SLFE  SLMN  SLBS  SLPA  SLPB  SLKE  SLMG  SLNA  SLSU  SLEC  SLCA
    20   -99   -99   -99   -99   -99   -99   -99   -99   -99   -99   -99   -99   -99   -99   -99   -99

*OTHER00001  TEST        S       100  Another soil
"""
CUL = """*SOYBEAN CULTIVAR COEFFICIENTS: CRGRO048 MODEL
@VAR#  VAR-NAME........ EXPNO   ECO#  CSDL PPSEN EM-FL FL-SH FL-SD SD-PM FL-LF LFMAX SLAVR SIZLF  XFRT WTPSD SFDUR SDPDV PODUR THRSH SDPRO SDLIP
TS0001 TEST CULTIVAR A      . SB0601 12.58 0.311  20.0   9.0  15.0 35.60 18.00 1.030  375. 180.0  1.00  0.18  23.0  2.05  10.0  78.0  .400  .200
"""
SBX = """*EXP.DETAILS: TEST2001SB TEST EXPERIMENT

*TREATMENTS                        -------------FACTOR LEVELS------------
@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM
 1 1 1 0 Rainfed early              1  1  0  1  1  0  0  0  0  0  0  0  1
 2 1 1 0 Irrigated late             1  1  0  1  2  1  0  0  0  0  0  0  1

*CULTIVARS
@C CR INGENO CNAME
 1 SB TS0001 TEST CULTIVAR A

*FIELDS
@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME
 1 TEST0001 TEST       -99   -99 DR000   -99   -99   -99 C      150  TEST000001 Test field (TF)

*PLANTING DETAILS
@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  PLDP  PLWT  PAGE  PENV  PLPH  SPRL                        PLNAME
 1 20290   -99    30    30     S     R    50   -99     4   -99   -99   -99   -99   -99                        early
 2 20320   -99    30    30     S     R    50   -99     4   -99   -99   -99   -99   -99                        late
"""
SBA = """*EXP. DATA (A): TEST2001SB TEST EXPERIMENT

@TRNO   HWAM  ADAT  MDAT
     1  3500   330   410
     2  4100  2020360 2021075
"""


def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_dssat_date():
    assert dssat_date(78166) == pd.Timestamp("1978-06-15")
    assert dssat_date("2019331") == pd.Timestamp("2019-11-27")
    assert dssat_date(18006) == pd.Timestamp("2018-01-06")
    assert dssat_date(-99) is None


def test_read_wth(tmp_path):
    w = read_wth(write(tmp_path, "A.WTH", WTH_A), write(tmp_path, "B.WTH", WTH_B))
    assert list(w.index[:3]) == list(pd.date_range("2020-01-01", periods=3))
    assert w.attrs["lat"] == -23.5 and w.attrs["elev"] == 600
    assert np.isnan(w.loc["2020-01-02", "dewp"]) and np.isnan(w.loc["2020-01-03", "wind"])
    u10 = 172.8 / 86.4                                       # 2 m/s at 10 m
    assert w.loc["2020-01-01", "wind"] == pytest.approx(u10 * 4.87 / np.log(67.8 * 10 - 5.42))
    assert w.loc["2020-01-06", "tmax"] == 27.0                # second file, blank columns
    ws = WeatherSeries(w, lat=-23.5, elev=600)                 # 2020-01-04 is missing: reindexed
    assert ws.n == 6 and np.isnan(ws.tmax[3])
    assert np.isfinite(ws.vpd[[0, 1, 2]]).all()               # humidity day by day


def test_weather_fill_from(tmp_path):
    w = read_wth(write(tmp_path, "A.WTH", WTH_A))
    other = pd.DataFrame({"srad": 15.0, "tmax": 25.0, "tmin": 15.0, "rain": 2.0, "dewp": 12.0},
                         index=pd.date_range("2019-12-30", "2020-01-05"))
    out = fill_from(w, other)
    assert out.index.min() == pd.Timestamp("2019-12-30") and out.index.max() == pd.Timestamp("2020-01-05")
    assert out.loc["2020-01-01", "tmax"] == 30.0               # the station wins
    assert out.loc["2020-01-02", "dewp"] == 12.0               # missing value taken
    assert out.attrs["filled_from"]["tmax"] == 4


def test_read_sol_and_training_soil(tmp_path):
    s = read_sol(write(tmp_path, "T.SOL", SOL), "TEST000001")
    assert list(s["top"]) == [0, 20, 60] and list(s["bottom"]) == [20, 60, 250]
    assert s.loc[0, "sand"] == pytest.approx(20) and s.loc[0, "dul"] == 0.38
    assert s.attrs["lat"] == -23.5 and s.attrs["lon"] == -51.2 and s.attrs["name"] == "Test clay"
    assert np.isnan(s.loc[1, "soc"])
    with pytest.raises(KeyError):
        read_sol(tmp_path / "T.SOL", "NOPE")
    grid = pd.DataFrame({"top": [0, 30, 100], "bottom": [30, 100, 200], "soc": [2.0, 1.0, 0.5]})
    f = soil_fill_from(s, grid, ["soc"])
    assert f.loc[1, "soc"] == 1.0 and f.loc[0, "soc"] == 1.5 and f.attrs["filled_from"]["soc"] == 1
    emu = cropemu.load("dssat-soybean-v1")
    t = emu.training_soil(f, lat=-23.5)
    assert t["bottom"].max() == 200 and t.loc[0, "ll"] == 0.25    # cut at 2 m, measured limits kept


def test_read_cul_experiment_observed(tmp_path):
    c = read_cul(write(tmp_path, "T.CUL", CUL), "TS0001")
    assert c["VAR-NAME"] == "TEST CULTIVAR A" and c["CSDL"] == 12.58 and c["SDLIP"] == 0.2
    x = read_experiment(write(tmp_path, "TEST2001.SBX", SBX))
    assert list(x["name"]) == ["Rainfed early", "Irrigated late"]
    assert list(x["irrigated"]) == [False, True]
    assert x.loc[1, "sowing"] == pd.Timestamp("2020-10-16") and x.loc[1, "ID_SOIL"] == "TEST000001"
    assert x.loc[1, "WSTA"] == "TEST" and x.loc[2, "plants_m2"] == 30
    o = read_observed(write(tmp_path, "TEST2001.SBA", SBA))
    assert o.loc[1, "ADAT"] == pd.Timestamp("2020-11-25")       # day of year, year of the experiment
    assert o.loc[2, "MDAT"] == pd.Timestamp("2021-03-16")


def test_cultivar_from_dssat_and_domain(tmp_path):
    emu = cropemu.load("dssat-soybean-v1")
    c = read_cul(write(tmp_path, "T.CUL", CUL), "TS0001")
    assert emu.mg_from_csdl(emu.cultivar(mg=6.0)["CSDL"]) == pytest.approx(6.0, abs=0.01)
    cv = emu.cultivar_from_dssat(c)
    assert cv["mg"] == pytest.approx(6.0, abs=0.01) and cv["CSDL"] == 12.58
    d = emu.cultivar_domain({**cv, "LFMAX": 1.5})
    assert d.loc["LFMAX", "status"] == "out of domain" and d.loc["CSDL", "status"] == "ok"
    assert emu.fixed_inputs() == {"depth_cm": 200.0}


def test_gdd_between():
    w = pd.DataFrame({"tmax": 30.0, "tmin": 20.0}, index=pd.date_range("2020-01-01", periods=10))
    assert cropemu.gdd_between(w, "2020-01-01", "2020-01-10") == pytest.approx(10 * 20.0)
    with pytest.raises(ValueError):
        cropemu.gdd_between(w, "2020-01-05", "2020-01-20")
