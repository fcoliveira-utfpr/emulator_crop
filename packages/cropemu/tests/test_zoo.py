"""Emulators shipped with the package: loading by name, cultivars, output table."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("onnxruntime")

import cropemu


def _weather():
    idx = pd.date_range("2015-01-01", "2020-12-31", freq="D")
    doy = idx.dayofyear.to_numpy()
    t = 22 + 5 * np.cos(2 * np.pi * (doy - 15) / 365)
    return pd.DataFrame({"tmax": t + 6, "tmin": t - 6, "srad": 18.0, "rain": 4.0, "rhum": 70.0}, index=idx)


SOIL = pd.DataFrame({"top": [0, 5, 15, 30, 60, 100], "bottom": [5, 15, 30, 60, 100, 200],
                     "clay": [50.0] * 6, "sand": [25.0] * 6, "silt": [25.0] * 6, "soc": [2, 1.5, 1, 0.6, 0.4, 0.3],
                     "bdod": [1.2, 1.25, 1.3, 1.3, 1.35, 1.35]})


def test_available_and_describe():
    names = cropemu.available()
    assert {"dssat-soybean-v1", "aquacrop-soybean-v1"} <= set(names)
    for n in names:
        emu = cropemu.load(n)
        d = emu.describe()
        assert set(emu.outputs_) <= set(d.index)
        assert (d["unit"] != "").all() and d["level"].isin(["recommended", "caution", "not recommended"]).all()
    with pytest.raises(FileNotFoundError):
        cropemu.load("no-such-emulator")


def test_dssat_cultivar_and_prediction():
    emu = cropemu.load("dssat-soybean-v1")
    assert emu.typical_mg(-23) == pytest.approx(6.5)
    c6, c8 = emu.cultivar(mg=6), emu.cultivar(mg=8)
    assert list(c6) == emu.cultivar_ and c8["CSDL"] < c6["CSDL"]          # later MG: shorter critical day length
    assert emu.cultivar(lat=-23)["mg"] == pytest.approx(6.5)
    assert emu.cultivar(mg=6, LFMAX=1.2)["LFMAX"] == 1.2
    r = emu.predict(_weather(), lat=-23.0, elev=500, soil=SOIL, sowing=["2016-10-15", "2017-10-15"],
                    cultivar=c6, co2=410)
    assert r.outputs["MDAT_dap"].between(80, 180).all() and (r.outputs["HWAM"] > 0).all()
    warm = emu.predict(_weather(), lat=-23.0, elev=500, soil=SOIL, sowing="2016-10-15", cultivar=c6, co2=410, dt=3)
    assert warm.inputs["tmax_0_30"].iloc[0] == pytest.approx(r.inputs["tmax_0_30"].iloc[0] + 3)


def test_aquacrop_cultivar():
    emu = cropemu.load("aquacrop-soybean-v1")
    w = _weather()
    c = emu.cultivar(weather=w, sowing="2016-10-15", cycle_days=120)
    g = cropemu.season_gdd(w, "2016-10-15", 120)
    assert c["gdd_maturity"] == pytest.approx(g) and c["cycle_factor"] == 1.0
    longer = emu.cultivar(mg=8.5, lat=-23, weather=w, sowing="2016-10-15", cycle_days=120)
    assert longer["gdd_maturity"] == pytest.approx(g * 1.25)
    with pytest.raises(ValueError):
        emu.cultivar()
    r = emu.predict(w, lat=-23.0, elev=500, soil=SOIL, sowing="2016-10-15", cultivar=c, co2=410)
    assert r.outputs["MAT_dap"].iloc[0] > 60
