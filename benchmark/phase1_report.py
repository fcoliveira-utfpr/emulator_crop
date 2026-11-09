"""Phase 1 report: acceptance labels per output (plan, 4.5.1) and classifiers of the categorical outputs.

Usage (after benchmark/phase1_emulators.py):

    python benchmark/phase1_report.py --name dssat_v0

Reads the out-of-fold predictions in data/<name>/benchmark/ and writes, there,
``acceptance_<emulator>_<validation>.csv``, ``acceptance_summary.csv`` and ``classifiers.csv``.
"""

import argparse
from pathlib import Path

import pandas as pd

from cropemu_bench.dataset import build
from cropemu_bench.evaluate import acceptance, classify_cv

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("matured", "crop_status", "delayed_germination")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="dssat_v0")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--no-classifiers", action="store_true")
    args = ap.parse_args()

    out = ROOT / "data" / args.name / "benchmark"
    X, Y, info = build(ROOT / "data" / args.name, derived=True)
    rows = []
    for f in sorted(out.glob("*_oof.parquet")):
        emu, val = f.stem[:-len("_oof")].rsplit("_", 1)
        P = pd.read_parquet(f)
        P.index = Y.index if len(P) == len(Y) else P.index
        cols = [c for c in P.columns if c in Y]
        a = acceptance(Y[cols], P[cols], info["point"])
        a.to_csv(out / f"acceptance_{emu}_{val}.csv")
        rows.append({"emulator": emu, "validation": val, "outputs": len(a), "recommended": int(a["recommended"].sum()),
                     "dates_recommended": f"{int(a.loc[a.index.str.endswith('_dap'), 'recommended'].sum())}/"
                                          f"{int(a.index.str.endswith('_dap').sum())}",
                     "median_rmse_over_within_sd": a.loc[~a.index.str.endswith("_dap"), "rmse_over_within_sd"].median()})
    s = pd.DataFrame(rows)
    s.to_csv(out / "acceptance_summary.csv", index=False)
    print(s.round(3).to_string(index=False), flush=True)

    if not args.no_classifiers:
        crows = []
        for lab in LABELS:
            if lab not in info or info[lab].nunique() < 2:
                continue
            m, _, _ = classify_cv(X, info[lab].astype(str), groups=info["block"], n_splits=args.folds)
            crows.append({"output": lab, **m})
            print(lab, {k: round(v, 3) if isinstance(v, float) else v for k, v in m.items()}, flush=True)
        pd.DataFrame(crows).to_csv(out / "classifiers.csv", index=False)


if __name__ == "__main__":
    main()
