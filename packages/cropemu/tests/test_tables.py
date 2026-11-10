"""Own data from spreadsheets: column names, units and templates."""

import warnings

import pandas as pd
import pytest

from cropemu.io import read_seasons, read_sites, read_soil, read_soils, read_weather, write_templates


@pytest.mark.parametrize("lang", ["en", "pt"])
def test_templates_roundtrip(tmp_path, lang):
    sites, weather, soil, seasons = write_templates(tmp_path, lang=lang)
    s = read_sites(sites)
    assert list(s.index) == ["A"] and s.loc["A", "lat"] == -24.5
    w = read_weather(weather, lat=-24.5, lon=-51.6, elev=600)
    assert list(w.columns) == ["srad", "tmax", "tmin", "rain", "rhum", "wind"] and w.attrs["conversions"] == []
    p = read_soil(soil)
    assert list(p["bottom"]) == [20, 60, 200] and p.loc[0, "clay"] == 55
    x = read_seasons(seasons)
    assert x.loc[0, "sowing"] == pd.Timestamp("2023-10-15") and not x.loc[0, "irrigated"]
    assert x.loc[0, "obs_flowering"] == 56 and x.loc[0, "obs_maturity"] == 128 and x.loc[0, "obs_yield"] == 3650


def test_weather_units_and_names(tmp_path):
    p = tmp_path / "estacao.csv"
    p.write_text("Data;Radiação (W/m²);Temp. máx;Temp. mín;Chuva (mm);UR\n"
                 "01/10/2023;250,0;30,5;18,0;0,0;0,60\n02/10/2023;200,0;31,0;19,5;5,2;0,80\n")
    p.write_text(p.read_text().replace("Temp. máx", "Tmax").replace("Temp. mín", "Tmin"))
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        w = read_weather(p, lat=-24, lon=-51, elev=600)
    assert w.index[0] == pd.Timestamp("2023-10-01")                     # day first
    assert w.loc["2023-10-01", "srad"] == pytest.approx(21.6) and w.loc["2023-10-02", "rain"] == 5.2
    assert w.loc["2023-10-02", "rhum"] == pytest.approx(80)
    assert len(w.attrs["conversions"]) == 2
    y = pd.DataFrame({"ano": [2023, 2023], "dia juliano": [274, 275], "tmax": [303.15, 304.0], "tmin": [291, 292],
                      "rs": [20, 21], "prec": [0, 1]})
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        w = read_weather(y, lat=-24, lon=-51, elev=600)
    assert w.index[0] == pd.Timestamp("2023-10-01") and w.loc["2023-10-01", "tmax"] == pytest.approx(30.0)
    with pytest.raises(KeyError, match="rain"):
        read_weather(y.drop(columns="prec"))


def test_soil_units_and_profiles():
    t = pd.DataFrame({"Fazenda": ["A", "A", "B"], "Profundidade (cm)": [20, 60, 30], "Argila (g/kg)": [550, 600, 200],
                      "Areia (g/kg)": [250, 200, 700], "MO (%)": [3.0, 1.5, 2.0], "Ds": [1.2, 1.3, 1.5],
                      "CC (%)": [40, 42, 20], "PMP (%)": [25, 27, 8]})
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        s = read_soils(t)
    assert set(s) == {"A", "B"}
    a = s["A"]
    assert list(a["top"]) == [0, 20] and a.loc[0, "clay"] == 55 and a.loc[0, "silt"] == pytest.approx(20)
    assert a.loc[0, "soc"] == pytest.approx(3.0 / 1.724) and a.loc[0, "dul"] == pytest.approx(0.40)
    with pytest.raises(ValueError, match="several"):
        read_soil(t)


def test_sites_reject_bad_coordinates():
    with pytest.raises(ValueError, match="impossible"):
        read_sites(pd.DataFrame({"fazenda": ["A"], "latitude": [-124.0], "longitude": [-51.0]}))
