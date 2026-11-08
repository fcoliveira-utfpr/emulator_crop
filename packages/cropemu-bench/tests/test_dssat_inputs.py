"""Writers of DSSAT input files (no executable needed)."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from cropemu_bench.models.dssat import COEFFICIENTS, Cultivar, EnvironmentModification, Treatment
from cropemu_bench.models.dssat._fmt import code, num, yyddd, yyyyddd
from cropemu_bench.models.dssat.cultivar import read_cultivars, write_cul
from cropemu_bench.models.dssat.filex import write_filex


# ------------------------------------------------------------------ formatting
@pytest.mark.parametrize("x, width, dec, expected", [
    (0.129, 5, 3, "0.129"), (37.4, 5, 3, "37.40"), (300, 5, 3, "300.0"), (12345, 5, 3, "12345"),
    (np.nan, 6, 1, "   -99"), (None, 5, 1, "  -99"), (-2.5, 4, 1, "-2.5"), (550, 4, 1, " 550")])
def test_num(x, width, dec, expected):
    assert num(x, width, dec) == expected


def test_num_too_wide():
    with pytest.raises(ValueError):
        num(123456, 5)


def test_dates_and_codes():
    assert yyddd(date(2019, 11, 1)) == "19305"
    assert yyyyddd(date(2020, 12, 31)) == "2020366"
    assert code(0, 4) == "0000" and code(35, 4) == "000Z" and code(36, 4) == "0010"
    with pytest.raises(ValueError):
        code(36**4, 4)


# ------------------------------------------------------------------ weather
def test_wth_format(weather, tmp_path):
    wsta = weather.write(tmp_path, "AB12")
    assert wsta == "AB121904"
    lines = (tmp_path / f"{wsta}.WTH").read_text().splitlines()
    assert lines[0].startswith("$WEATHER")             # 4-digit years
    assert lines[4].startswith("@  DATE")
    first = lines[5]
    assert first[:7] == "2019001"                     # DSSAT reads the date as I7
    assert len(lines) == 5 + len(weather.data)
    tav, amp = weather.tav_amp()
    assert 15 < tav < 30 and 0 < amp < 10


def test_weather_rejects_gaps(weather):
    from cropemu_bench.models.dssat import Weather
    with pytest.raises(ValueError, match="gaps"):
        Weather(weather.data.drop(weather.data.index[10]), lat=0, lon=0, elev=0)
    with pytest.raises(ValueError, match="lacks"):
        Weather(weather.data.drop(columns="rain"), lat=0, lon=0, elev=0)


# ------------------------------------------------------------------ soil
def test_sol_format(soil):
    text = soil.to_sol("CEMUSOIL01").splitlines()
    assert text[0].startswith("*CEMUSOIL01  cropemu")
    # Fortran (1X, A10, 2X, A11, 1X, A5, 1X, F5.0): texture in columns 26-30, depth in 32-36
    assert text[0][25:30].strip() == "C" and text[0][31:36] == "  150"
    surface = text[4]
    assert surface[6:12] == "  0.13"                  # SALB as 1X, F5.0 in columns 8-12
    layer_lines = text[6:]
    assert len(layer_lines) == len(soil.layers)
    for ln in layer_lines:                            # every field: a space plus 5 characters
        assert len(ln) == 6 * 17
        assert all(ln[i] == " " for i in range(0, len(ln), 6))
    assert layer_lines[0][:12] == "    10   -99"


def test_soil_validation(soil):
    from cropemu_bench.models.dssat import SoilProfile
    bad = soil.layers.copy()
    bad.loc[0, "sdul"] = 0.6
    with pytest.raises(ValueError, match="slll < sdul < ssat"):
        SoilProfile(bad)


# ------------------------------------------------------------------ cultivar
def _base_cul(tmp_path):
    header = ("*SOYBEAN CULTIVAR COEFFICIENTS: CRGRO048 MODEL\n@VAR#  VAR-NAME........ EXPNO   ECO#  "
              + " ".join(f"{c:>5s}" for c in COEFFICIENTS) + "\n")
    base = Cultivar("990006", "SB0601", dict(zip(COEFFICIENTS, [12.58, 0.311, 20.2, 9.0, 16.0, 35.6, 18.0,
                    1.03, 375, 180, 1.0, 0.18, 23.0, 2.05, 10.0, 78.0, 0.400, 0.200])), "M GROUP   6")
    path = tmp_path / "BASE.CUL"
    path.write_text(header + base.to_line() + "\n")
    return path, base


def test_cultivar_roundtrip(tmp_path):
    path, base = _base_cul(tmp_path)
    custom = Cultivar("CE0001", "SB0601", base.with_(EM_FL=24.5, CSDL=12.0).coefficients)
    write_cul(tmp_path / "OUT.CUL", path, [custom])
    table = read_cultivars(tmp_path / "OUT.CUL").set_index("id")
    assert list(table.index) == ["990006", "CE0001"]
    assert table.loc["CE0001", "EM-FL"] == 24.5 and table.loc["CE0001", "CSDL"] == 12.0
    assert table.loc["990006", "SLAVR"] == 375


def test_cultivar_id_clash(tmp_path):
    path, base = _base_cul(tmp_path)
    with pytest.raises(ValueError, match="already"):
        write_cul(tmp_path / "OUT.CUL", path, [base])


# ------------------------------------------------------------------ filex
def test_filex(soil, tmp_path):
    T = [Treatment("w", "CEMUSOIL01", "990006", date(2019, 11, 1), seasons=3),
         Treatment("w", "CEMUSOIL01", "990006", date(2019, 12, 1), water=False,
                   environment=EnvironmentModification(tmax_add=2, rain_factor=0.8, co2=550))]
    write_filex(tmp_path / "X.SBX", T, {"w": "AB121904"}, {"CEMUSOIL01": soil}, daily=("growth",))
    text = (tmp_path / "X.SBX").read_text()
    for section in ("*TREATMENTS", "*CULTIVARS", "*FIELDS", "*INITIAL CONDITIONS", "*PLANTING DETAILS",
                    "*ENVIRONMENT MODIFICATIONS", "*SIMULATION CONTROLS"):
        assert section in text
    lines = text.splitlines()
    env = lines[lines.index("*ENVIRONMENT MODIFICATIONS") + 2]
    # Fortran (I3, I5, 8(1X, A1, F4.0))
    assert env == " 2 19305 A 0.0 M 1.0 A 2.0 A 0.0 M 0.8 R 550 A 0.0 A 0.0"
    treat = [ln for ln in lines if ln.startswith(" 2 1 0 0")][0]
    assert treat[-3:] == "  2" and treat[-9:-6] == "  2"   # SM and ME levels
    assert "    3     1     S 19275" in text            # NYERS=3, start 30 days before planting


def test_filex_limits(soil, tmp_path):
    T = [Treatment("w", "CEMUSOIL01", "990006", date(2019, 11, 1))] * 100
    with pytest.raises(ValueError, match="1 to 99"):
        write_filex(tmp_path / "X.SBX", T, {"w": "AB121904"}, {"CEMUSOIL01": soil})
    with pytest.raises(ValueError, match="unknown daily"):
        write_filex(tmp_path / "X.SBX", T[:1], {"w": "AB121904"}, {"CEMUSOIL01": soil}, daily=("roots",))


def test_treatment_validation():
    with pytest.raises(ValueError, match="start"):
        Treatment("w", "s", "c", date(2019, 11, 1), start=date(2019, 12, 1))
    with pytest.raises(ValueError, match="irrigation"):
        Treatment("w", "s", "c", date(2019, 11, 1), water=False, irrigation=True)
    assert Treatment("w", "s", "c", date(2019, 11, 1)).start == date(2019, 10, 2)
