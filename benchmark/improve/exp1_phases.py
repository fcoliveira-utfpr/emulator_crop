"""Test 1: inputs summarised by crop phase (phase_features.py) added to the current inputs.

Phenology (emergence, flowering, maturity, harvest) keeps the published network: its out-of-fold
predictions also define the phases of the test rows. The other outputs get a new network with the
current inputs + the phase inputs: training rows use the simulated dates with noise, test rows the
predicted dates (as in use, where the phases come from the predicted dates)."""
import sys

import numpy as np
import pandas as pd

from cropemu_bench.emulators import MLPEmulator

from common import OUT, PHENOLOGY, baseline_oof, cv_custom, load

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 0
X, Y, info = load()
base = baseline_oof().loc[X.index]
F_tr = pd.read_parquet(OUT / "phase_train.parquet").loc[X.index]
F_te = pd.read_parquet(OUT / "phase_oof.parquet").loc[X.index]
other = [c for c in Y.columns if c not in PHENOLOGY]
groups = info["block"].to_numpy()


def fit_predict(tr, te):
    Xtr = pd.concat([X.iloc[tr], F_tr.iloc[tr]], axis=1)
    Xte = pd.concat([X.iloc[te], F_te.iloc[te]], axis=1)
    m = MLPEmulator(seed=SEED).fit(Xtr, Y.iloc[tr][other], groups=groups[tr])
    p = m.predict(Xte)
    for c in PHENOLOGY:
        if c in Y:
            p[c] = base.iloc[te][c].to_numpy()
    return p


cv_custom("1_phases" if SEED == 0 else f"1_phases_seed{SEED}", fit_predict, X, Y, info, note="janelas fixas + 45 entradas por fase fenológica (datas previstas no teste)")
