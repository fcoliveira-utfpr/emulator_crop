"""Baseline: the published emulator (stored out-of-fold predictions) and a retrain with the same
settings (to measure the run-to-run noise). Usage: python baseline.py [--retrain SEED ...]"""
import argparse
import functools

from cropemu_bench.emulators import GroupedEmulator

from common import baseline_oof, evaluate, load, run_cv

ap = argparse.ArgumentParser()
ap.add_argument("--retrain", nargs="*", type=int, default=[])
args = ap.parse_args()
X, Y, info = load()
evaluate("0_baseline_published", baseline_oof(), Y, info, note="MLP por grupos publicado (OOF armazenado)")
for s in args.retrain:
    run_cv(f"0_baseline_seed{s}", functools.partial(GroupedEmulator, seed=s), X, Y, info, note=f"retreino, semente {s}")
