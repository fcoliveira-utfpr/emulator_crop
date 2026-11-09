"""Phase 1 benchmark: emulators of every Summary.OUT output, spatial-block vs random validation.

Usage (after benchmark/generate_dssat.py):

    python benchmark/phase1_emulators.py --name dssat_v0

Writes data/<name>/benchmark/: metrics per (emulator, validation, output), cost per fold,
out-of-fold predictions, and a short report table printed at the end.
"""

import argparse
import time
from pathlib import Path

import pandas as pd

from cropemu_bench.dataset import build
from cropemu_bench.emulators import GBEmulator, MLPEmulator, RidgeEmulator
from cropemu_bench.evaluate import cross_validate

ROOT = Path(__file__).resolve().parents[1]
KEY = ["EDAT_dap", "ADAT_dap", "MDAT_dap", "HWAM", "CWAM", "LAIX", "HIAM", "ETCM", "PRCM", "DRCM", "SWXM"]
EMULATORS = {"ridge": RidgeEmulator, "gb": GBEmulator, "mlp": MLPEmulator}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="dssat_v0")
    ap.add_argument("--emulators", nargs="+", default=list(EMULATORS))
    ap.add_argument("--validation", nargs="+", default=["block", "random"], choices=["block", "random"])
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--gb-key-only", action="store_true", help="GB only on the key outputs (faster)")
    args = ap.parse_args()

    data = ROOT / "data" / args.name
    out = data / "benchmark"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    X, Y, info = build(data)
    print(f"X {X.shape}, Y {Y.shape}, {info['point'].nunique()} points, {info['block'].nunique()} blocks "
          f"({time.time() - t0:.0f}s)", flush=True)

    summary = []
    for v in args.validation:
        groups = info["block"] if v == "block" else None
        for name in args.emulators:
            y = Y[[c for c in KEY if c in Y]] if (name == "gb" and args.gb_key_only) else Y
            t1 = time.time()
            print(f"{name} / {v}: {y.shape[1]} outputs", flush=True)
            m, oof, cost = cross_validate(EMULATORS[name], X, y, groups=groups, n_splits=args.folds)
            m.to_csv(out / f"{name}_{v}_metrics.csv")
            cost.to_csv(out / f"{name}_{v}_cost.csv", index=False)
            oof.to_parquet(out / f"{name}_{v}_oof.parquet")
            summary.append({"emulator": name, "validation": v, "outputs": y.shape[1],
                            "median_r2": m["r2"].median(), "minutes": (time.time() - t1) / 60,
                            "fit_s_per_fold": cost["fit_s"].mean(),
                            "predict_us_per_row": cost["predict_us_per_row"].mean(),
                            **{f"rmse_{k}": m.loc[k, "rmse"] for k in KEY if k in m.index}})
            pd.DataFrame(summary).to_csv(out / "summary.csv", index=False)
    print(pd.DataFrame(summary).round(3).to_string(), flush=True)


if __name__ == "__main__":
    main()
