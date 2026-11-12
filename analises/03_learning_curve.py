"""Learning curve: emulation error on held-out 5° blocks as a function of the number of simulated
points used for training (the chosen emulator of each model, same folds as the benchmark).

    python analises/03_learning_curve.py
"""
import functools
import sys

import numpy as np
import pandas as pd

from common import MODELS, ROOT, TAB, rmse, r2
from cropemu_bench.dataset import DERIVED, build
from cropemu_bench.emulators import GroupedEmulator
from cropemu_bench.emulators.grouped import AQUACROP_OFFSETS
from cropemu_bench.evaluate import splits

FRACTIONS = [0.05, 0.10, 0.25, 0.50, 1.00]
FACTORY = {"dssat": GroupedEmulator, "aquacrop": functools.partial(GroupedEmulator, offsets=AQUACROP_OFFSETS)}
rows = []
for m in sys.argv[1:] or list(MODELS):
    cfg = MODELS[m]
    X, Y_all, info = build(ROOT / "data" / cfg["data"], derived=True)
    Y = Y_all.drop(columns=[c for c in DERIVED if c in Y_all])
    rng = np.random.default_rng(0)
    for k, (tr, te) in enumerate(splits(len(X), info["block"], 5, 0)):
        pts = info["point"].to_numpy()
        train_points = rng.permutation(np.unique(pts[tr]))
        for f in FRACTIONS:
            keep = set(train_points[: max(int(round(f * len(train_points))), 10)])
            idx = tr[np.fromiter((p in keep for p in pts[tr]), bool, len(tr))]
            em = FACTORY[m](seed=0)
            em.fit(X.iloc[idx], Y.iloc[idx], groups=info["block"].to_numpy()[idx])
            P = em.predict(X.iloc[te])
            rec = {"model": m, "fold": k, "fraction": f, "points": len(keep), "seasons": len(idx), "fit_s": em.fit_seconds_}
            for name, col in (("yield", cfg["yld"]), ("maturity", cfg["mat"]), ("et", cfg["et"]), ("biomass", cfg["bio"])):
                y, p = Y.iloc[te][col].to_numpy(float), P[col].to_numpy(float)
                rec[f"rmse_{name}"], rec[f"r2_{name}"] = rmse(p - y), r2(y, p)
            rec["median_r2"] = float(np.nanmedian([r2(Y.iloc[te][c], P[c]) for c in Y.columns]))
            rows.append(rec)
            print(rec, flush=True)
            pd.DataFrame(rows).to_csv(TAB / f"learning_curve_{'_'.join(sys.argv[1:]) or 'all'}.csv", index=False)
