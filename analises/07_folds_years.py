"""Uncertainty of the validation metrics (R5) and temporal leakage (R6), on the v3 campaign.

R5. RMSE of the released CNN emulators (out-of-fold, 5° blocks) per fold, with a 95 % interval from a
    bootstrap of the blocks; the v1 architecture (grouped MLP; with the thermal-time offset for AquaCrop)
    retrained on the same data and folds, so v1 and the CNN are compared fold by fold.
R6. The same test seasons held out by block AND by year: for fold k, the test set is the seasons of the
    blocks of fold k in the years of year-group k; training excludes those blocks and, in every site,
    those years. A second run excludes only the blocks, with the training set subsampled at random to the
    same size, so the difference measures what the shared years add to the optimism (not the smaller
    training set). Run with the v1 architecture (the CNN is 25 times slower to train).

    python analises/07_folds_years.py [--models dssat aquacrop] [--boot 1000]
"""
import argparse
import functools

import numpy as np
import pandas as pd

from common import ROOT, TAB
from cropemu_bench.dataset import DERIVED, build
from cropemu_bench.emulators import GroupedEmulator
from cropemu_bench.emulators.grouped import AQUACROP_OFFSETS
from cropemu_bench.evaluate import splits

KEYS = {"dssat": {"yield": ("HWAM", 1e-3), "maturity": ("MDAT_dap", 1), "ET": ("ETCM", 1)},
        "aquacrop": {"yield": ("Y(dry)", 1.0), "maturity": ("MAT_dap", 1), "ET": ("ET_crop", 1)}}


def rmse(e):
    e = e[np.isfinite(e)]
    return float(np.sqrt(np.mean(e ** 2)))


def factory(model, seed=0):
    if model == "aquacrop":
        return functools.partial(GroupedEmulator, offsets=AQUACROP_OFFSETS, seed=seed)
    return functools.partial(GroupedEmulator, seed=seed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["dssat", "aquacrop"])
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()
    rng = np.random.default_rng(1)
    r5, r6 = [], []
    for model in args.models:
        folder = ROOT / "data" / f"{model}_v3"
        X, Y_all, info = build(folder, derived=True)
        Y = Y_all.drop(columns=[c for c in DERIVED if c in Y_all])
        design = pd.read_parquet(folder / "design.parquet").set_index("sample").loc[Y.index]
        blocks = info["block"].to_numpy()
        years = design["year"].to_numpy()
        folds = splits(len(X), blocks, 5, 0)
        fold_of = np.empty(len(X), int)
        for k, (_, te) in enumerate(folds):
            fold_of[te] = k
        cnn = pd.read_parquet(folder / "benchmark" / "cnn_block_oof.parquet").loc[Y.index]

        # ---- R5: v1 retrained on the same folds
        print(model, "v1 block CV", flush=True)
        v1 = pd.DataFrame(np.nan, index=Y.index, columns=Y.columns)
        for k, (tr, te) in enumerate(folds):
            em = factory(model)()
            em.fit(X.iloc[tr], Y.iloc[tr], groups=blocks[tr])
            v1.iloc[te] = em.predict(X.iloc[te])[Y.columns].to_numpy()
            print(f"  fold {k}: {em.fit_seconds_:.0f}s", flush=True)
        ub = np.unique(blocks)
        for name, (col, sc) in KEYS[model].items():
            y = Y[col].to_numpy() * sc
            for em_name, P in (("cnn", cnn), ("v1", v1)):
                e = P[col].to_numpy() * sc - y
                per_fold = [rmse(e[fold_of == k]) for k in range(5)]
                # bootstrap of blocks
                eb = pd.Series(e ** 2).groupby(blocks).agg(["sum", "count"])
                eb = eb[eb["count"] > 0]
                s, c = eb["sum"].to_numpy(), eb["count"].to_numpy()
                bs = []
                for _ in range(args.boot):
                    i = rng.integers(0, len(eb), len(eb))
                    bs.append(np.sqrt(np.nansum(s[i]) / c[i].sum()))
                r5.append(dict(model=model, output=name, emulator=em_name, rmse=rmse(e),
                               ci_lo=np.quantile(bs, 0.025), ci_hi=np.quantile(bs, 0.975),
                               fold_mean=np.mean(per_fold), fold_sd=np.std(per_fold, ddof=1),
                               **{f"fold{k}": v for k, v in enumerate(per_fold)}))
        t5 = pd.DataFrame(r5)
        # paired reduction per fold (CNN vs v1)
        for name in KEYS[model]:
            a = t5[(t5.model == model) & (t5.output == name)].set_index("emulator")
            red = [100 * (1 - a.loc["cnn", f"fold{k}"] / a.loc["v1", f"fold{k}"]) for k in range(5)]
            print(f"  {name}: CNN {a.loc['cnn','rmse']:.3f} [{a.loc['cnn','ci_lo']:.3f}-{a.loc['cnn','ci_hi']:.3f}] "
                  f"v1 {a.loc['v1','rmse']:.3f}; reduction per fold {np.round(red, 1)} "
                  f"(mean {np.mean(red):.1f}, min {np.min(red):.1f})", flush=True)

        # ---- R6: blocks x years
        uy = np.unique(years)
        ygroup = dict(zip(rng.permutation(uy), np.arange(len(uy)) % 5))
        yg = np.array([ygroup[y] for y in years])
        for k in range(5):
            test = (fold_of == k) & (yg == k)
            tr_by = np.flatnonzero((fold_of != k) & (yg != k))
            tr_b_all = np.flatnonzero(fold_of != k)
            tr_b = np.sort(rng.choice(tr_b_all, size=len(tr_by), replace=False))
            te = np.flatnonzero(test)
            for variant, tr in (("blocks", tr_b), ("blocks+years", tr_by)):
                em = factory(model)()
                em.fit(X.iloc[tr], Y.iloc[tr], groups=blocks[tr])
                P = em.predict(X.iloc[te])
                row = dict(model=model, fold=k, variant=variant, n_train=len(tr), n_test=len(te))
                for name, (col, sc) in KEYS[model].items():
                    row[name] = rmse((P[col].to_numpy() - Y[col].to_numpy()[te]) * sc)
                r6.append(row)
                print(f"  R6 fold {k} {variant}: n_train {len(tr)} n_test {len(te)} yield {row['yield']:.3f}", flush=True)
        pd.DataFrame(r5).round(4).to_csv(TAB / "fold_uncertainty.csv", index=False)
        pd.DataFrame(r6).round(4).to_csv(TAB / "temporal_leakage.csv", index=False)

    t6 = pd.DataFrame(r6)
    summ = t6.groupby(["model", "variant"])[["yield", "maturity", "ET"]].mean()
    print(summ.round(3).to_string())
    for model in t6.model.unique():
        a = t6[t6.model == model].pivot(index="fold", columns="variant", values="yield")
        inc = 100 * (a["blocks+years"] / a["blocks"] - 1)
        print(f"{model}: yield RMSE increase with years held out, per fold {inc.round(1).tolist()}, mean {inc.mean():.1f}%")


if __name__ == "__main__":
    main()
