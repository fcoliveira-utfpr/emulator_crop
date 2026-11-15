"""Test 4: the current emulator trained with the new Americas seasons (exp4_generate.py) added.

The original seasons keep the folds of the baseline; a new point takes the fold of its 5° block
(so it never helps to predict its own block); new points in blocks absent from dssat_v1 get a
random fold. Evaluation on the original seasons only, comparable with the baseline.
"""
import time

import numpy as np
import pandas as pd

from cropemu_bench.dataset import build
from cropemu_bench.emulators import GroupedEmulator
from cropemu_bench.evaluate import splits

from common import OUT, ROOT, evaluate, load

X, Y, info = load()
Xn, Yn, infon = build(ROOT / "data" / "dssat_americas", derived=False)
Yn = Yn.reindex(columns=Y.columns)
print(f"original {len(X)} seasons; new {len(Xn)} seasons at {infon['point'].nunique()} points", flush=True)

fold = np.empty(len(X), int)
for k, (_, te) in enumerate(splits(len(X), info["block"], 5, 0)):
    fold[te] = k
block_fold = pd.Series(fold, index=info["block"].to_numpy()).groupby(level=0).first()
rng = np.random.default_rng(0)
new_fold = np.array([block_fold.get(b, -1) for b in infon["block"]])
missing = new_fold < 0
blocks_new = pd.unique(infon["block"][missing])
extra = dict(zip(blocks_new, rng.integers(0, 5, len(blocks_new))))
new_fold[missing] = [extra[b] for b in infon["block"][missing]]
print(f"new points in existing blocks: {(~missing).mean():.0%}", flush=True)

XA, YA = pd.concat([X, Xn[X.columns]]), pd.concat([Y, Yn])
groups = np.concatenate([info["block"].to_numpy(), infon["block"].to_numpy()])
foldA = np.concatenate([fold, new_fold])
n0 = len(X)
oof = pd.DataFrame(np.nan, index=Y.index, columns=Y.columns)
t0 = time.time()
for k in range(5):
    tr = np.flatnonzero(foldA != k)
    te = np.flatnonzero(fold == k)
    em = GroupedEmulator(seed=0).fit(XA.iloc[tr], YA.iloc[tr], groups=groups[tr])
    oof.iloc[te] = em.predict(X.iloc[te]).to_numpy()
    print(f"  fold {k + 1}/5 ({(time.time() - t0) / 60:.1f} min)", flush=True)
oof.to_parquet(OUT / "4_more_americas_oof.parquet")
evaluate("4_more_americas", oof, Y, info, (time.time() - t0) / 60,
         note=f"+{infon['point'].nunique()} pontos novos nas Américas ({len(Xn)} safras)")
