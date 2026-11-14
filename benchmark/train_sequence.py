"""Block validation and final fit of the daily-sequence emulator (``SequenceEmulator``, "cnn").

    python benchmark/train_sequence.py --name dssat_v1 cv        # out-of-fold predictions
    python benchmark/phase1_report.py --name dssat_v1 --no-classifiers   # acceptance levels
    python benchmark/train_sequence.py --name dssat_v1 fit       # all seasons -> benchmark/cnn_final.pkl
    python benchmark/export_emulators.py --name dssat_v1 --emulator cnn --zoo-name dssat-soybean-v2

The validation is resumable: every part (date networks of one seed, convolutional network of
one fold) is saved in ``data/<name>/benchmark/cnn_parts/`` as it finishes and skipped when present.
Same 5 folds by 5° blocks as the other emulators (``evaluate.splits``, seed 0).
"""

import argparse
import pickle
import time
from pathlib import Path

import sys

import numpy as np
import pandas as pd

from cropemu_bench.dataset import DERIVED, build, derive, model_of
from cropemu_bench.emulators import SequenceEmulator
from cropemu_bench.emulators.grouped import AQUACROP_OFFSETS
from cropemu_bench.evaluate import cross_validate, metrics, splits
from cropemu_bench.sequence import build_sequences

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))


def emulator(name: str) -> SequenceEmulator:
    return SequenceEmulator(offsets=AQUACROP_OFFSETS if model_of(ROOT / "data" / name) == "aquacrop" else None)


def cv(name: str, folds: int = 5):
    data = ROOT / "data" / name
    X, Y, info = build(data, derived=False)
    seq = build_sequences(data, X)
    out = data / "benchmark"
    parts = out / "cnn_parts"
    parts.mkdir(parents=True, exist_ok=True)
    em = emulator(name)
    dates, other = em.split(Y)
    groups = info["block"].to_numpy()
    t0 = time.time()
    cost_file = parts / "cost.csv"                    # fit seconds of every part and fold

    def log_cost(c):
        c.to_csv(cost_file, mode="a", header=not cost_file.exists(), index=False)

    for s in em.seeds:
        f = parts / f"dates_seed{s}.parquet"
        if not f.exists():
            _, oof, c = cross_validate(lambda: em.fit_dates_factory(s), X, Y[dates], groups=groups, n_splits=folds)
            oof.to_parquet(f)
            log_cost(c.assign(part=f"dates_seed{s}"))
            print(f"dates seed {s} done ({(time.time() - t0) / 60:.0f} min)", flush=True)
    for k, (tr, te) in enumerate(splits(len(X), groups, folds, 0)):
        f = parts / f"conv_fold{k}.parquet"
        if f.exists():
            continue
        print(f"conv fold {k}", flush=True)
        m = em.conv_factory().fit(X.iloc[tr], Y[other].iloc[tr], groups=groups[tr], seq=seq[tr])
        m.predict(X.iloc[te], seq[te]).to_parquet(f)
        log_cost(pd.DataFrame([{"fold": k, "fit_s": m.fit_seconds_, "predict_us_per_row": m.predict_us_per_row_,
                                "n_train": len(tr), "n_test": len(te), "part": "conv"}]))
        print(f"conv fold {k} done ({(time.time() - t0) / 60:.0f} min)", flush=True)
    d = sum(pd.read_parquet(parts / f"dates_seed{s}.parquet").loc[Y.index, dates] for s in em.seeds) / len(em.seeds)
    c = pd.concat([pd.read_parquet(parts / f"conv_fold{k}.parquet") for k in range(folds)]).loc[Y.index, other]
    oof = pd.concat([d, c], axis=1)[Y.columns]
    oof.to_parquet(out / "cnn_block_oof.parquet")
    # metrics and summary row as benchmark/phase1_emulators.py
    _, Y_all, _ = build(data, derived=True)
    m = metrics(Y, oof)
    m["derived"] = False
    der = [c for c in DERIVED if c in Y_all and set(DERIVED[c][:2]) <= set(oof.columns)]
    if der:
        md = metrics(Y_all.loc[Y.index, der], derive(oof)[der])
        md["derived"] = True
        m = pd.concat([m, md])
    m.to_csv(out / "cnn_block_metrics.csv")
    cost = pd.read_csv(cost_file) if cost_file.exists() else pd.DataFrame(columns=["fold", "fit_s", "part"])
    cost.to_csv(out / "cnn_block_cost.csv", index=False)
    from phase1_emulators import KEY

    summ = out / "summary.csv"
    prev = pd.read_csv(summ)
    prev = prev[~((prev["emulator"] == "cnn") & (prev["validation"] == "block"))]
    old = prev[prev["emulator"] == "cnn"]
    row = {"emulator": "cnn", "validation": "block", "outputs": Y.shape[1],
           "median_r2": m.loc[~m["derived"], "r2"].median(),
           "minutes": cost["fit_s"].sum() / 60 if len(cost) else np.nan,
           "fit_s_per_fold": cost.groupby("part")["fit_s"].mean().sum() if len(cost) else np.nan,
           "predict_us_per_row": np.nan, **{f"rmse_{k}": m.loc[k, "rmse"] for k in KEY if k in m.index}}
    pd.concat([prev, pd.DataFrame([row])], ignore_index=True).to_csv(summ, index=False)
    print(m.loc[[k for k in KEY if k in m.index], ["rmse", "r2"]].round(3).to_string(), flush=True)


def fit(name: str):
    data = ROOT / "data" / name
    X, Y, info = build(data, derived=False)
    seq = build_sequences(data, X)
    t0 = time.time()
    em = emulator(name).fit(X, Y, groups=info["block"].to_numpy(), seq=np.asarray(seq))
    print(f"fit on {len(X)} seasons in {(time.time() - t0) / 60:.0f} min", flush=True)
    with open(data / "benchmark" / "cnn_final.pkl", "wb") as f:
        pickle.dump(em, f)
    timing(name, em, X, seq)


def timing(name: str, em=None, X=None, seq=None, rows: int = 5000):
    """Prediction cost of the final emulator (µs per season, torch on CPU) into summary.csv."""
    data = ROOT / "data" / name
    if em is None:
        with open(data / "benchmark" / "cnn_final.pkl", "rb") as f:
            em = pickle.load(f)
        X, _, _ = build(data, derived=False)
        seq = build_sequences(data, X)
    i = np.sort(np.random.default_rng(0).choice(len(X), rows, replace=False))
    s = np.asarray(seq[i], np.float32)
    em.predict(X.iloc[i[:100]], s[:100])
    t0 = time.time()
    em.predict(X.iloc[i], s)
    us = 1e6 * (time.time() - t0) / rows
    summ = data / "benchmark" / "summary.csv"
    t = pd.read_csv(summ)
    t.loc[t["emulator"] == "cnn", "predict_us_per_row"] = us
    t.to_csv(summ, index=False)
    print(f"prediction: {us:.0f} µs per season", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("step", choices=["sequences", "cv", "fit", "timing"])
    args = ap.parse_args()
    if args.step == "sequences":
        X, _, _ = build(ROOT / "data" / args.name, derived=False)
        print(build_sequences(ROOT / "data" / args.name, X).shape)
    elif args.step == "cv":
        cv(args.name)
    elif args.step == "timing":
        timing(args.name)
    else:
        fit(args.name)


if __name__ == "__main__":
    main()
