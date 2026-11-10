"""Export to ONNX + card and prediction with the library (cropemu.load)."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("onnxruntime")
pytest.importorskip("onnx")

import cropemu
from cropemu.features import WeatherSeries, season_inputs, soil_features
from cropemu_bench.emulators import GroupedEmulator
from cropemu_bench.export import export

SOIL = pd.DataFrame({"top": [0, 15, 30], "bottom": [15, 30, 100], "ll": [0.2, 0.2, 0.25], "dul": [0.35, 0.33, 0.35],
                     "clay": [40, 50, 60], "sand": [30, 25, 20], "soc": [2, 1, 0.5], "bdod": [1.2, 1.3, 1.3]})


def _weather(seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", "2021-12-31", freq="D")
    doy = idx.dayofyear.to_numpy()
    t = 22 + 6 * np.sin(2 * np.pi * doy / 365) + rng.normal(0, 2, len(idx))
    return pd.DataFrame({"tmax": t + 6, "tmin": t - 6, "srad": 18 + rng.normal(0, 3, len(idx)),
                         "rain": rng.exponential(3, len(idx)), "rhum": np.full(len(idx), 70.0)}, index=idx)


def test_export_and_library_prediction(tmp_path):
    w = WeatherSeries(_weather(), lat=-24.0, elev=500)
    soil = soil_features(SOIL)
    rng = np.random.default_rng(1)
    sow = pd.Timestamp("2018-03-01") + pd.to_timedelta(rng.integers(0, 900, 400), unit="D")
    cult = [{"mg": m, "gdd_maturity": g} for m, g in zip(rng.uniform(4, 8, 400), rng.uniform(1500, 2500, 400))]
    X = pd.DataFrame([season_inputs(w, soil, s, c, irrigated=bool(k % 2), co2=400, thermal="aquacrop_soybean")
                      for k, (s, c) in enumerate(zip(sow, cult))])
    Y = pd.DataFrame({"MAT_dap": X["td_maturity"] + 3 * X["mg"], "yield": 1000 * X["mg"] - 10 * X["tmax_0_30"]})
    em = GroupedEmulator(groups={"dates": ["MAT_dap"]}, offsets={"MAT_dap": "td_maturity"}, hidden=(32, 32),
                         max_epochs=60, patience=10).fit(X, Y)
    card = {"name": "test", "model": "synthetic", "crop": "soybean", "cultivar": ["mg", "gdd_maturity"],
            "thermal": "aquacrop_soybean", "water_balance": True, "initial_water": 0.5,
            "hydraulics": "hybrid", "acceptance": {"MAT_dap": {"level": "recommended"}, "yield": {"level": "caution"}}}
    export(em, X, tmp_path / "emu", card)

    emu = cropemu.load(tmp_path / "emu")
    assert emu.inputs_ == list(X.columns) and emu.outputs_ == ["MAT_dap", "yield"]
    res = emu.predict_inputs(X)
    np.testing.assert_allclose(res.outputs.to_numpy(), em.predict(X).to_numpy(), rtol=1e-4, atol=1e-2)

    # from weather, soil and cultivar: the same inputs as in training
    r = emu.predict(_weather(), lat=-24.0, elev=500, soil=SOIL, sowing=[sow[0], sow[1]], cultivar=cult[0] | {"x": 1},
                    irrigated=False, co2=400)
    assert r.inputs.iloc[0].to_dict() == pytest.approx(
        season_inputs(w, soil, sow[0], cult[0], irrigated=False, co2=400, thermal="aquacrop_soybean"))
    assert list(r.recommended("recommended").columns) == ["MAT_dap"]
    # a raw profile (no LL/DUL): the water retention of the card is applied at the given latitude
    from cropemu.soil import hydraulics
    raw = SOIL.drop(columns=["ll", "dul"])
    r2 = emu.predict(_weather(), lat=-24.0, elev=500, soil=raw, sowing=sow[0], cultivar=cult[0], co2=400)
    expected = season_inputs(w, soil_features(hydraulics(raw, method="hybrid", lat=-24.0)), sow[0], cult[0],
                             irrigated=False, co2=400, thermal="aquacrop_soybean")
    assert r2.inputs.iloc[0].to_dict() == pytest.approx(expected)
    assert r.out_of_domain.iloc[0] == []
    far = emu.predict_inputs(X.iloc[:1].assign(mg=20.0))
    assert far.out_of_domain.iloc[0] == ["mg"] and far.rare_inputs.iloc[0] == ["mg"]
    lo = emu.card["domain"]["mg"]
    edge = emu.predict_inputs(X.iloc[:1].assign(mg=(lo["min"] + lo["q005"]) / 2))
    assert edge.out_of_domain.iloc[0] == [] and edge.rare_inputs.iloc[0] == ["mg"]
    with pytest.raises(KeyError, match="cultivar"):
        emu.predict(_weather(), lat=-24.0, soil=SOIL, sowing=sow[0], cultivar={"mg": 5})
