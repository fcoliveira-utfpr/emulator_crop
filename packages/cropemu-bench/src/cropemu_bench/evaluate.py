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


def classify_cv(X: pd.DataFrame, y: pd.Series, groups=None, n_splits: int = 5, seed: int = 0, **kw):
    """Out-of-fold classification of a categorical output (gradient boosting classifier).

    Returns (metrics dict: accuracy, balanced accuracy, ROC AUC when binary, recall per class;
    out-of-fold predicted classes; out-of-fold class probabilities).
    """
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, recall_score, roc_auc_score

    y = pd.Series(np.asarray(y), index=X.index)
    classes = sorted(y.unique().tolist(), key=str)
    proba = pd.DataFrame(0.0, index=X.index, columns=classes)
    for tr, te in splits(len(X), groups, n_splits, seed):
        m = HistGradientBoostingClassifier(max_iter=kw.get("max_iter", 300), learning_rate=0.1,
                                           class_weight=kw.get("class_weight", "balanced"), random_state=seed)
        m.fit(X.iloc[tr], y.iloc[tr])
        proba.iloc[te, [classes.index(c) for c in m.classes_]] = m.predict_proba(X.iloc[te])
    pred = proba.idxmax(axis=1)
    out = {"n": len(y), "accuracy": accuracy_score(y, pred), "balanced_accuracy": balanced_accuracy_score(y, pred),
           "majority_share": float(y.value_counts(normalize=True).iloc[0])}
    if len(classes) == 2:
        out["roc_auc"] = roc_auc_score(y == classes[1], proba[classes[1]])
    for c, r in zip(classes, recall_score(y, pred, labels=classes, average=None)):
        out[f"recall_{c}"] = float(r)
        out[f"share_{c}"] = float((y == c).mean())
    return out, pred, proba


#: Acceptance criteria of the plan (4.5.1), fixed before the benchmark.
DATE_RMSE_DAYS = 5.0          # phase dates: RMSE below the typical field observation error (3-5 d)
RELATIVE_RMSE = 0.25          # other outputs: RMSE below 25 % of the within-site standard deviation


def within_site_sd(y: pd.Series, site) -> float:
    """Pooled standard deviation of an output across the seasons of each site."""
    g = pd.DataFrame({"y": y.to_numpy(float), "site": np.asarray(site)}).dropna()
    var = g.groupby("site")["y"].var(ddof=1).dropna()
    n = g.groupby("site")["y"].count().loc[var.index] - 1
    return float(np.sqrt((var * n).sum() / n.sum())) if n.sum() > 0 else np.nan


def acceptance(Y: pd.DataFrame, P: pd.DataFrame, site, date_rmse: float = DATE_RMSE_DAYS,
               relative: float = RELATIVE_RMSE) -> pd.DataFrame:
    """Per output: RMSE, within-site SD, their ratio and the "recommended" label (plan, 4.5.1).

    Dates (``*_dap``): recommended when RMSE <= ``date_rmse`` days. Other outputs:
    recommended when RMSE < ``relative`` x the within-site SD.
    """
    m = metrics(Y, P)
    rows = []
    for c in m.index:
        sd = within_site_sd(Y[c], site)
        is_date = c.endswith("_dap")
        ratio = m.loc[c, "rmse"] / sd if sd > 0 else np.nan
        ok = m.loc[c, "rmse"] <= date_rmse if is_date else bool(ratio < relative)
        rows.append({"target": c, "rmse": m.loc[c, "rmse"], "r2": m.loc[c, "r2"], "within_site_sd": sd,
                     "rmse_over_within_sd": ratio, "criterion": f"RMSE <= {date_rmse:g} d" if is_date
                     else f"RMSE < {relative:g} within-site SD", "recommended": bool(ok)})
    return pd.DataFrame(rows).set_index("target")
