import numpy as np
import pandas as pd
import pytest

from cropemu_bench.dataset import targets
from cropemu_bench.emulators import GBEmulator, MLPEmulator, RidgeEmulator
from cropemu_bench.evaluate import cross_validate, metrics, splits


def _data(n=1500, seed=0):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(rng.normal(size=(n, 4)), columns=list("abcd"))
    Y = pd.DataFrame({"lin": 2 * X.a - X.b, "nonlin": np.sin(2 * X.a) * X.c + X.d ** 2})
    Y.loc[rng.random(n) < 0.2, "nonlin"] = np.nan                  # censored output
    groups = (np.arange(n) // 50).astype(str)
    return X, Y, groups


@pytest.mark.parametrize("factory, r2_min", [
    (lambda: MLPEmulator(hidden=(64, 64), max_epochs=150, patience=15), 0.7),
    (lambda: GBEmulator(max_iter=200), 0.7),
    (lambda: RidgeEmulator(), None)])
def test_emulators_fit_masked_targets(factory, r2_min):
    X, Y, groups = _data()
    m, oof, cost = cross_validate(factory, X, Y, groups=groups, n_splits=3, verbose=False)
    assert set(m.index) == {"lin", "nonlin"} and m.loc["nonlin", "n"] == Y["nonlin"].notna().sum()
    assert m.loc["lin", "r2"] > 0.99                               # every emulator gets the linear output
    if r2_min:
        assert m.loc["nonlin", "r2"] > r2_min
    else:
        assert m.loc["nonlin", "r2"] < 0.5                         # ridge cannot fit the nonlinear one
    assert len(cost) == 3 and (cost["predict_us_per_row"] > 0).all()


def test_splits_keep_groups_together():
    g = np.repeat(["a", "b", "c", "d", "e", "f"], 10)
    for tr, te in splits(len(g), g, n_splits=3):
        assert not set(g[tr]) & set(g[te])
    folds = splits(100, None, n_splits=4)
    assert sorted(np.concatenate([te for _, te in folds]).tolist()) == list(range(100))


def test_metrics():
    Y = pd.DataFrame({"y": [1.0, 2.0, 3.0, np.nan]})
    P = pd.DataFrame({"y": [2.0, 3.0, 4.0, 0.0]})
    m = metrics(Y, P).loc["y"]
    assert m["n"] == 3 and m["bias"] == 1 and m["rmse"] == 1


def test_targets_from_summary():
    s = pd.DataFrame({"sample": [0, 1, 2], "PDAT": [2019305, 2019305, 2020010], "ADAT": [2019340, -99, 2020050],
                      "MDAT": [2020040, np.nan, 2020120], "HWAM": [3000.0, 0.0, 4000.0], "CR": ["SB"] * 3,
                      "CRST": [1, 2, 1], "CONST": [5.0, 5.0, 5.0], "TRNO": [1, 2, 3]})
    s["ADAT"] = s["ADAT"].replace(-99, np.nan)
    y = targets(s)
    assert list(y.columns) == ["ADAT_dap", "MDAT_dap", "HWAM"]        # no identifiers, codes or constants
    assert y.loc[0, "ADAT_dap"] == 35 and y.loc[2, "ADAT_dap"] == 40 and np.isnan(y.loc[1, "ADAT_dap"])
    assert y.loc[0, "MDAT_dap"] == 100                                # across the new year (2019 not leap)
