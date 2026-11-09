"""Cross-validation of emulators with spatial blocks (or random folds) and metrics per output."""

from __future__ import annotations

import numpy as np
import pandas as pd


def metrics(Y: pd.DataFrame, P: pd.DataFrame) -> pd.DataFrame:
    """Per output: n, RMSE, MAE, median absolute error, bias (pred - true), R², NRMSE (RMSE / std of the truth)."""
    rows = []
    for c in Y.columns:
        y, p = Y[c].to_numpy(float), P[c].to_numpy(float)
        ok = np.isfinite(y) & np.isfinite(p)
        y, p = y[ok], p[ok]
        if len(y) == 0:
            continue
        e = p - y
        sd = y.std()
        rmse = float(np.sqrt(np.mean(e**2)))
        rows.append({"target": c, "n": int(ok.sum()), "rmse": rmse, "mae": float(np.mean(np.abs(e))),
                     "medae": float(np.median(np.abs(e))),
                     "bias": float(e.mean()), "r2": float(1 - np.mean(e**2) / sd**2) if sd > 0 else np.nan,
                     "nrmse": rmse / sd if sd > 0 else np.nan})
    return pd.DataFrame(rows).set_index("target")


def splits(n: int, groups=None, n_splits: int = 5, seed: int = 0):
    """Fold indices: whole groups (e.g. 5° blocks) per fold when ``groups`` is given, else random."""
    rng = np.random.default_rng(seed)
    if groups is None:
        fold = rng.permutation(np.arange(n) % n_splits)
    else:
        g = np.asarray(groups)
        ug = rng.permutation(np.unique(g))
        gfold = {u: k % n_splits for k, u in enumerate(ug)}
        fold = np.array([gfold[x] for x in g])
    return [(np.flatnonzero(fold != k), np.flatnonzero(fold == k)) for k in range(n_splits)]


def cross_validate(factory, X: pd.DataFrame, Y: pd.DataFrame, groups=None, n_splits: int = 5, seed: int = 0,
                   verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Out-of-fold predictions of ``factory()`` emulators.

    Returns (metrics per output on all out-of-fold predictions, out-of-fold
    predictions, cost per fold: fit seconds, prediction µs per row).
    """
    oof = pd.DataFrame(np.nan, index=Y.index, columns=Y.columns)
    cost = []
    for k, (tr, te) in enumerate(splits(len(X), groups, n_splits, seed)):
        em = factory()
        g = None if groups is None else np.asarray(groups)[tr]
        em.fit(X.iloc[tr], Y.iloc[tr], groups=g)
        oof.iloc[te] = em.predict(X.iloc[te]).to_numpy()
        cost.append({"fold": k, "fit_s": em.fit_seconds_, "predict_us_per_row": em.predict_us_per_row_,
                     "n_train": len(tr), "n_test": len(te)})
        if verbose:
            print(f"  {em.name} fold {k + 1}/{n_splits}: fit {em.fit_seconds_:.0f}s", flush=True)
    return metrics(Y, oof), oof, pd.DataFrame(cost)
