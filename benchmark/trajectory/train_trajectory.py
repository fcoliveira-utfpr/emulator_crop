"""Trajectory emulator: curve shapes in phenological time (``cropemu_bench.trajectory``) by the
convolutional network of v2 (same inputs: season inputs + daily weather sequence).

    python benchmark/trajectory/train_trajectory.py --name dssat_v3 cv     # out-of-fold, 5° blocks
    python benchmark/trajectory/train_trajectory.py --name dssat_v3 fit    # all seasons

Resumable: every fold is saved in ``data/<name>/benchmark/traj_parts/``. Same 5 folds by 5° blocks as
the other emulators (``evaluate.splits``, seed 0). Writes ``traj_block_oof.parquet`` and
``traj_block_metrics.csv`` (RMSE and R² per curve and phase, on the normalised shapes) and, with
``fit``, ``traj_final.pkl``.
"""

import argparse
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd

from cropemu_bench.dataset import build, model_of
from cropemu_bench.emulators.sequence import ConvEmulator
from cropemu_bench.evaluate import splits
from cropemu_bench.sequence import build_sequences
from cropemu_bench.trajectory import GRID, PHASE_POINTS, trajectory_targets

ROOT = Path(__file__).resolve().parents[2]


def data_of(name: str):
    data = ROOT / "data" / name
    X, _, info = build(data, derived=False)
    T = trajectory_targets(data).reindex(X.index)
    keep = T.notna().any(axis=1).to_numpy()             # seasons that reached maturity
    X, T, info = X[keep], T[keep], info[keep]
    seq = build_sequences(data, X)
    return data, X, T, info, seq


def metrics(T: pd.DataFrame, P: pd.DataFrame) -> pd.DataFrame:
    """RMSE and R² of the shapes by curve and phase (vegetative tau 0-1, reproductive 1-2)."""
    rows = []
    for curve in sorted({c.rsplit("_", 1)[0] for c in T.columns}):
        cols = [c for c in T.columns if c.startswith(curve + "_")]
        parts = {"all": cols}
        if curve != "stress":
            parts |= {"vegetative": cols[:PHASE_POINTS], "reproductive": cols[PHASE_POINTS - 1:]}
        else:
            parts |= {"vegetative": cols[:PHASE_POINTS - 1], "reproductive": cols[PHASE_POINTS - 1:]}
        for part, cs in parts.items():
            t, p = T[cs].to_numpy(), P[cs].to_numpy()
            ok = np.isfinite(t)
            err = (p - t)[ok]
            ss = ((t[ok] - t[ok].mean()) ** 2).sum()
            rows.append({"curve": curve, "part": part, "points": len(cs), "n": int(ok.sum()),
                         "rmse": float(np.sqrt(np.mean(err ** 2))),
                         "r2": float(1 - (err ** 2).sum() / ss) if ss > 1e-9 else np.nan,   # e.g. grain before flowering
                         "bias": float(err.mean())})
    return pd.DataFrame(rows)


def cv(name: str, folds: int = 5):
    data, X, T, info, seq = data_of(name)
    parts = data / "benchmark" / "traj_parts"
    parts.mkdir(parents=True, exist_ok=True)
    groups = info["block"].to_numpy()
    t0 = time.time()
    for k, (tr, te) in enumerate(splits(len(X), groups, folds, 0)):
        f = parts / f"traj_fold{k}.parquet"
        if f.exists():
            continue
        print(f"trajectory fold {k}", flush=True)
        m = ConvEmulator().fit(X.iloc[tr], T.iloc[tr], groups=groups[tr], seq=seq[tr])
        m.predict(X.iloc[te], seq[te]).to_parquet(f)
        print(f"trajectory fold {k} done ({(time.time() - t0) / 60:.0f} min, {m.fit_seconds_ / 60:.0f} min fit)",
              flush=True)
    oof = pd.concat([pd.read_parquet(parts / f"traj_fold{k}.parquet") for k in range(folds)]).loc[T.index, T.columns]
    oof.to_parquet(data / "benchmark" / "traj_block_oof.parquet")
    m = metrics(T, oof)
    m.to_csv(data / "benchmark" / "traj_block_metrics.csv", index=False)
    print(m[m["part"] == "all"].round(3).to_string(index=False), flush=True)


def fit(name: str):
    data, X, T, info, seq = data_of(name)
    t0 = time.time()
    m = ConvEmulator().fit(X, T, groups=info["block"].to_numpy(), seq=seq)
    print(f"trajectory fit on {len(X)} seasons in {(time.time() - t0) / 60:.0f} min", flush=True)
    with open(data / "benchmark" / "traj_final.pkl", "wb") as f:
        pickle.dump(m, f)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("step", choices=["targets", "cv", "fit"])
    args = ap.parse_args()
    if args.step == "targets":
        T = trajectory_targets(ROOT / "data" / args.name)
        print(f"{model_of(ROOT / 'data' / args.name)}: {T.shape}, complete {T.notna().all(axis=1).mean():.3f}")
    elif args.step == "cv":
        cv(args.name)
    else:
        fit(args.name)


if __name__ == "__main__":
    main()
