"""Test 2: a network that reads the daily weather (1-D CNN) besides the current inputs.

Sequence: days -30..+170 after sowing, 9 channels (Tmax, Tmin, radiation, rain, ETo, VPD, day
length, bucket stress, day after sowing), with the season's perturbation applied (same matrices as
phase_features.py, checked against the current window inputs). The CNN embedding is concatenated
with the current inputs and a head predicts the non-phenology outputs; phenology keeps the
published network (as in test 1). Same folds, NaN targets masked, early stopping on held-out blocks.

Usage: python exp2_sequence.py [--prepare] [--folds 0 1 2 3 4] [--epochs N]
"""
from __future__ import annotations

import argparse
import copy
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from cropemu_bench.emulators.base import Scaler
from cropemu_bench.evaluate import splits

from common import DATA, OUT, PHENOLOGY, baseline_oof, evaluate, load

T1 = 170
SEQ = OUT / "sequence_f16.npy"
CHANNELS = ["tmax", "tmin", "srad", "rain", "eto", "vpd", "dayl", "stress", "das"]


def prepare(X):
    from phase_features import DAYS, bucket, daily_matrices

    design = pd.read_parquet(DATA / "design.parquet").set_index("sample").loc[X.index].reset_index()
    M = daily_matrices(design, pd.read_parquet(DATA / "points.parquet"))
    M["stress"] = bucket(M["rain"], M["eto"], X["paw_mm"].to_numpy())
    keep = DAYS <= T1
    seq = np.empty((len(X), len(CHANNELS), keep.sum()), np.float16)
    for c, name in enumerate(CHANNELS[:-1]):
        v = np.nan_to_num(M[name][:, keep], nan=0.0)
        seq[:, c] = v
        del M[name]
    seq[:, -1] = (DAYS[keep] / 100.0)[None, :]
    np.save(SEQ, seq)
    print("sequence", seq.shape, flush=True)


class Net(nn.Module):
    def __init__(self, n_static, n_out, ch=len(CHANNELS)):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(ch, 32, 7, padding=3), nn.SiLU(), nn.MaxPool1d(2),
            nn.Conv1d(32, 48, 5, padding=2), nn.SiLU(), nn.MaxPool1d(2),
            nn.Conv1d(48, 64, 5, padding=2), nn.SiLU(), nn.MaxPool1d(2),
            nn.Conv1d(64, 64, 3, padding=1), nn.SiLU())
        self.static = nn.Sequential(nn.Linear(n_static, 256), nn.SiLU())
        self.head = nn.Sequential(nn.Linear(256 + 128, 256), nn.SiLU(), nn.Linear(256, 256), nn.SiLU(), nn.Linear(256, n_out))

    def forward(self, s, x):
        h = self.conv(s)
        h = torch.cat([h.mean(2), h.amax(2)], 1)
        return self.head(torch.cat([self.static(x), h], 1))


def fit_predict(seq, X, Y, groups, tr, te, epochs, seed=0, batch=512, patience=12):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    xs, ys = Scaler().fit(X[tr]), Scaler().fit(Y[tr])
    # channel scaling from a sample of training sequences
    sample = seq[rng.choice(tr, size=min(5000, len(tr)), replace=False)].astype(np.float32)
    cm, cs = sample.mean((0, 2)), sample.std((0, 2)) + 1e-6
    S = lambda idx: torch.from_numpy((seq[idx].astype(np.float32) - cm[None, :, None]) / cs[None, :, None])
    x = torch.from_numpy(xs.transform(X).astype(np.float32))
    y = ys.transform(Y).astype(np.float32)
    mask = torch.from_numpy(np.isfinite(y).astype(np.float32))
    y = torch.from_numpy(np.nan_to_num(y))
    ug = np.unique(groups[tr])
    val_g = rng.choice(ug, size=max(1, round(0.1 * len(ug))), replace=False)
    val = tr[np.isin(groups[tr], val_g)]
    fit = tr[~np.isin(groups[tr], val_g)]
    net = Net(X.shape[1], Y.shape[1])
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-5)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=patience // 3)
    loss = lambda p, t, m: ((p - t) ** 2 * m).sum() / m.sum().clamp(min=1)

    def evaluate_loss(idx):
        net.eval()
        tot, w = 0.0, 0.0
        with torch.no_grad():
            for i in range(0, len(idx), 4096):
                b = idx[i:i + 4096]
                m = mask[b]
                tot += float(((net(S(b), x[b]) - y[b]) ** 2 * m).sum())
                w += float(m.sum())
        return tot / max(w, 1)

    best, best_state, wait = np.inf, None, 0
    for epoch in range(epochs):
        t0 = time.time()
        net.train()
        perm = rng.permutation(fit)
        for i in range(0, len(perm), batch):
            b = perm[i:i + batch]
            opt.zero_grad()
            loss(net(S(b), x[b]), y[b], mask[b]).backward()
            opt.step()
        v = evaluate_loss(val)
        sched.step(v)
        if v < best - 1e-5:
            best, best_state, wait = v, copy.deepcopy(net.state_dict()), 0
        else:
            wait += 1
        print(f"    epoch {epoch}: val {v:.4f} ({time.time() - t0:.0f}s)", flush=True)
        if wait >= patience:
            break
    net.load_state_dict(best_state)
    net.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(te), 4096):
            b = te[i:i + 4096]
            out.append(net(S(b), x[b]).numpy())
    return ys.inverse(np.concatenate(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--folds", nargs="*", type=int, default=[0, 1, 2, 3, 4])
    ap.add_argument("--epochs", type=int, default=120)
    args = ap.parse_args()
    torch.set_num_threads(4)
    X, Y, info = load()
    if args.prepare or not SEQ.exists():
        prepare(X)
    seq = np.load(SEQ, mmap_mode="r")
    other = [c for c in Y.columns if c not in PHENOLOGY]
    base = baseline_oof().loc[X.index]
    groups = info["block"].to_numpy()
    part = OUT / "2_sequence_partial.parquet"
    oof = pd.read_parquet(part) if part.exists() else pd.DataFrame(np.nan, index=Y.index, columns=Y.columns)
    t0 = time.time()
    for k, (tr, te) in enumerate(splits(len(X), info["block"], 5, 0)):
        if k not in args.folds:
            continue
        print(f"fold {k}", flush=True)
        p = fit_predict(seq, X.to_numpy(float), Y[other].to_numpy(float), groups, tr, te, args.epochs)
        oof.iloc[te, [oof.columns.get_loc(c) for c in other]] = p
        for c in PHENOLOGY:
            if c in Y:
                oof.iloc[te, oof.columns.get_loc(c)] = base.iloc[te][c].to_numpy()
        oof.to_parquet(part)
        print(f"fold {k} done ({(time.time() - t0) / 60:.0f} min)", flush=True)
    if oof["HWAM"].notna().all():
        oof.to_parquet(OUT / "2_sequence_oof.parquet")
        evaluate("2_sequence", oof, Y, info, (time.time() - t0) / 60, note="CNN 1D sobre o clima diário (-30..+170 d) + entradas atuais")


if __name__ == "__main__":
    main()
