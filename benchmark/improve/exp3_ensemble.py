"""Test 3: ensembles of the current emulator.

3a  mean of 4 MLP-by-groups networks with different seeds (published + seeds 1-3, same folds);
3b  50/50 mean of the published MLP and gradient boosting on the outputs GB was benchmarked on
    (11 key outputs; stored out-of-fold predictions of the published benchmark);
3c  3a + GB on those outputs.

Usage: python exp3_ensemble.py [--train 1 2 3]   (seeds to train first; their OOF are reused later)
"""
import argparse
import functools

import pandas as pd

from cropemu_bench.emulators import GroupedEmulator

from common import DATA, OUT, baseline_oof, evaluate, load, run_cv

ap = argparse.ArgumentParser()
ap.add_argument("--train", nargs="*", type=int, default=[])
args = ap.parse_args()
X, Y, info = load()
for s in args.train:
    if not (OUT / f"0_baseline_seed{s}_oof.parquet").exists():
        run_cv(f"0_baseline_seed{s}", functools.partial(GroupedEmulator, seed=s), X, Y, info, note=f"retreino, semente {s}")

members = [baseline_oof().loc[Y.index]] + [pd.read_parquet(p).loc[Y.index] for p in sorted(OUT.glob("0_baseline_seed[1-9]_oof.parquet"))]
mean = sum(m[Y.columns] for m in members) / len(members)
evaluate("3a_seed_ensemble", mean, Y, info, note=f"média de {len(members)} redes (sementes diferentes)")

gb = pd.read_parquet(DATA / "benchmark" / "gb_block_oof.parquet").loc[Y.index]
cols = [c for c in gb.columns if c in Y and gb[c].notna().all()]
blend = members[0][Y.columns].copy()
blend[cols] = (members[0][cols] + gb[cols]) / 2
evaluate("3b_mlp_gb", blend, Y, info, note=f"MLP publicado + GB (50/50) em {len(cols)} saídas: {' '.join(cols)}")
both = mean.copy()
both[cols] = (mean[cols] + gb[cols]) / 2
evaluate("3c_seeds_gb", both, Y, info, note="3a + GB (50/50) nas mesmas saídas")

# 3d: mean of the phase-input networks (exp1_phases.py with seeds 0..3), if available
ph = [pd.read_parquet(p).loc[Y.index] for p in [OUT / "1_phases_oof.parquet", *sorted(OUT.glob("1_phases_seed[1-9]_oof.parquet"))] if p.exists()]
if len(ph) > 1:
    evaluate("3d_phases_seed_ensemble", sum(m[Y.columns] for m in ph) / len(ph), Y, info, note=f"média de {len(ph)} redes com entradas por fase")
