import numpy as np
import pandas as pd
import pytest

from cropemu_bench.dataset import derive, targets
from cropemu_bench.emulators import GBEmulator, GroupedEmulator, MLPEmulator, RidgeEmulator
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
    (lambda: GroupedEmulator(groups={"g1": ["lin"]}, hidden=(64, 64), max_epochs=150, patience=15), 0.7),
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


def test_ratio_outputs_are_derived_not_emulated():
    s = pd.DataFrame({"sample": [0, 1, 2], "PDAT": [2019305] * 3, "HWAM": [3000.0, 2000.0, 1000.0],
                      "CWAM": [6000.0, 5000.0, 2000.0], "PRCP": [500.0, 0.0, 100.0], "YPPM": [6.0, 20000.0, 10.0],
                      "DMPPM": [12.0, 50000.0, 20.0]})
    assert "YPPM" not in targets(s) and "DMPPM" not in targets(s)
    y = targets(s, derived=True, min_valid=0.5)
    assert np.isnan(y.loc[1, "YPPM"]) and y.loc[2, "YPPM"] == 10.0     # ratio censored with almost no rain
    p = derive(targets(s))
    assert p.loc[0, "YPPM"] == 6.0 and p.loc[0, "DMPPM"] == 12.0
    assert p.loc[1, "YPPM"] == 80.0                                    # rain floored at 25 mm


def test_acceptance_and_within_site_sd():
    from cropemu_bench.evaluate import acceptance, within_site_sd

    site = np.repeat(["a", "b"], 50)
    rng = np.random.default_rng(0)
    y = pd.Series(np.r_[rng.normal(0, 1, 50), rng.normal(100, 1, 50)])
    assert within_site_sd(y, site) == pytest.approx(1.0, abs=0.15)           # between-site offset ignored
    Y = pd.DataFrame({"HWAM": y, "ADAT_dap": 40 + rng.normal(0, 10, 100)})
    P = Y + pd.DataFrame({"HWAM": rng.normal(0, 0.1, 100), "ADAT_dap": rng.normal(0, 6, 100)})
    a = acceptance(Y, P, site)
    assert a.loc["HWAM", "recommended"] and not a.loc["ADAT_dap", "recommended"]   # 6 d > 5 d
    assert a.loc["ADAT_dap", "level"] == "caution"                                  # 6 d < 10 d
    # a site property (within-site SD ~1 % of the total): judged against the total SD
    Y["OCAM"] = np.repeat([1000.0, 5000.0], 50) + rng.normal(0, 20, 100)
    P["OCAM"] = Y["OCAM"] + rng.normal(0, 300, 100)
    a = acceptance(Y, P, site)
    assert a.loc["OCAM", "reference"] == "total SD" and a.loc["OCAM", "recommended"]
    assert a.loc["HWAM", "reference"] == "total SD"                     # also between-site dominated here


def test_classify_cv_and_labels():
    from cropemu_bench.dataset import labels
    from cropemu_bench.evaluate import classify_cv

    X, Y, groups = _data(n=800)
    y = np.where(X.a + 0.3 * X.b > 0.8, "fail", "ok")
    out, pred, proba = classify_cv(X, y, groups=groups, n_splits=3, max_iter=100)
    assert out["balanced_accuracy"] > 0.85 and out["roc_auc"] > 0.95 and len(pred) == 800
    s = pd.DataFrame({"sample": [0, 1, 2], "CRST": [1, 39, 32]})
    lab = labels(s)
    assert lab["matured"].tolist() == [True, False, False]
    assert lab["crop_status"].tolist() == ["matured", "ended_before_maturity", "cold_kill"]


def test_mdat_is_censored_when_crop_did_not_mature():
    s = pd.DataFrame({"sample": [0, 1, 2], "PDAT": [2019305] * 3, "MDAT": [2020040, 2020010, 2020050],
                      "CRST": [1, 39, 1], "HWAM": [1.0, 2.0, 3.0]})
    y = targets(s)
    assert np.isnan(y.loc[1, "MDAT_dap"]) and y.loc[0, "MDAT_dap"] == 100


def test_grouped_offsets():
    """An output equal to a feature plus a small deviation: the members fit only the deviation."""
    X, Y, _ = _data()
    X["td"] = 50 + 30 * np.abs(X.b)
    Y["date"] = X["td"] + (X.a > 1.5) * 10.0
    em = GroupedEmulator(groups={"dates": ["date"]}, offsets={"date": "td", "absent": "td"}, hidden=(64, 64),
                         max_epochs=150, patience=15).fit(X, Y)
    assert em.offsets_ == {"date": "td"}
    p = em.predict(X)
    assert list(p.columns) == list(Y.columns)
    assert np.sqrt(((p["date"] - Y["date"]) ** 2).mean()) < 1.5
