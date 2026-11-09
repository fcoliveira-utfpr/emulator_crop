"""Phase 1 benchmark: emulators of every Summary.OUT output, spatial-block vs random validation.

Usage (after benchmark/generate_dssat.py):

    python benchmark/phase1_emulators.py --name dssat_v0

Writes data/<name>/benchmark/: metrics per (emulator, validation, output), cost per fold,
out-of-fold predictions, and a short report table printed at the end.
"""

import argparse
import functools
import time
from pathlib import Path

import pandas as pd

from cropemu_bench.dataset import DERIVED, build, derive
from cropemu_bench.emulators import GBEmulator, GroupedEmulator, MLPEmulator, RidgeEmulator
from cropemu_bench.emulators.grouped import AQUACROP_OFFSETS
from cropemu_bench.evaluate import cross_validate, metrics

ROOT = Path(__file__).resolve().parents[1]
KEY = ["EDAT_dap", "ADAT_dap", "MDAT_dap", "HWAM", "CWAM", "LAIX", "HIAM", "ETCM", "PRCM", "DRCM", "SWXM",
       # AquaCrop
       "EMR_dap", "FLO_dap", "MAT_dap", "Y(dry)", "BioMass", "HI", "CC_max", "ET_crop", "Tr_crop", "Drain_crop"]
EMULATORS = {"ridge": RidgeEmulator, "gb": GBEmulator, "mlp": MLPEmulator, "mlp_grouped": GroupedEmulator,
             "mlp_offset": functools.partial(GroupedEmulator, offsets=AQUACROP_OFFSETS)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="dssat_v0")
    ap.add_argument("--emulators", nargs="+", default=list(EMULATORS))
    ap.add_argument("--validation", nargs="+", default=["block", "random"], choices=["block", "random"])
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0, help="network seed (the folds do not change)")
    ap.add_argument("--features", default="features.parquet", help="feature file in data/<name>")
    ap.add_argument("--out", default="benchmark", help="output folder in data/<name>")
    ap.add_argument("--gb-key-only", action="store_true", help="GB only on the key outputs (faster)")
    args = ap.parse_args()

    data = ROOT / "data" / args.name
    out = data / args.out
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    X, Y_all, info = build(data, derived=True, features_file=args.features)
    Y = Y_all.drop(columns=[c for c in DERIVED if c in Y_all])       # ratios computed from predictions
    print(f"X {X.shape}, Y {Y.shape}, {info['point'].nunique()} points, {info['block'].nunique()} blocks "
          f"({time.time() - t0:.0f}s)", flush=True)

    old = out / "summary.csv"
    summary = []
    if old.exists():                       # keep the rows of emulators/validations not rerun now
        prev = pd.read_csv(old)
        keep = ~(prev["emulator"].isin(args.emulators) & prev["validation"].isin(args.validation))
        summary = prev[keep].to_dict("records")
    for v in args.validation:
        groups = info["block"] if v == "block" else None
        for name in args.emulators:
            y = Y[[c for c in KEY if c in Y]] if (name == "gb" and args.gb_key_only) else Y
            t1 = time.time()
            print(f"{name} / {v}: {y.shape[1]} outputs", flush=True)
            factory = EMULATORS[name]
            if name.startswith("mlp"):
                factory = functools.partial(factory, seed=args.seed)
            m, oof, cost = cross_validate(factory, X, y, groups=groups, n_splits=args.folds)
            m["derived"] = False
            der = [c for c in DERIVED if c in Y_all and set(DERIVED[c][:2]) <= set(oof.columns)]
            if der:
                oof = derive(oof)
                md = metrics(Y_all[der], oof[der])
                md["derived"] = True
                m = pd.concat([m, md])
            m.to_csv(out / f"{name}_{v}_metrics.csv")
            cost.to_csv(out / f"{name}_{v}_cost.csv", index=False)
            oof.to_parquet(out / f"{name}_{v}_oof.parquet")
            summary.append({"emulator": name, "validation": v, "outputs": y.shape[1],
                            "median_r2": m.loc[~m["derived"], "r2"].median(), "minutes": (time.time() - t1) / 60,
                            "fit_s_per_fold": cost["fit_s"].mean(),
                            "predict_us_per_row": cost["predict_us_per_row"].mean(),
                            **{f"rmse_{k}": m.loc[k, "rmse"] for k in KEY if k in m.index}})
            pd.DataFrame(summary).to_csv(out / "summary.csv", index=False)
    print(pd.DataFrame(summary).round(3).to_string(), flush=True)


if __name__ == "__main__":
    main()
