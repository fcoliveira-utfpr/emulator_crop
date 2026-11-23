"""Phase 2 pilot: what the daily trajectories look like and how compactly they can be described.

Reads data/traj_pilot_dssat and data/traj_pilot_aquacrop (pilot_dssat.py, pilot_aquacrop.py) and
writes to benchmark/trajectory/results/, per model:
- consistency of the daily tables with the season summary (last yield = season yield, max leaf
  area / canopy cover = season maximum);
- curves of a few seasons in calendar days and in phenological time (emergence -> flowering ->
  maturity mapped to 0..1 and 1..2), the representation proposed for the emulator;
- how well K points per phase reproduce the daily growth curves (linear interpolation back to the
  days), and K-1 bin means per phase the water stress (against its 7-day running mean);
- the size of the daily data per season, to size the full campaign.

Usage (repository root): python benchmark/trajectory/pilot_analysis.py [dssat|aquacrop ...]
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from cropemu_bench.pipeline import load

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(exist_ok=True)

#: per model: dataset, daily table, growth variables (leaf area, biomass, yield), water stress and
#: its scale, summary columns of the final yield and of the leaf area maximum.
MODELS = {
    "dssat": dict(data="traj_pilot_dssat", table="daily_PlantGro", growth=["LAID", "CWAD", "GWAD"],
                  stress="WSPD", stress_scale=1.0, yield_=("GWAD", "HWAM"), leaf=("LAID", "LAIX"), missing=-99),
    "aquacrop": dict(data="traj_pilot_aquacrop", table="daily_day", growth=["CC", "Biomass", "Y(dry)"],
                     stress="StSto", stress_scale=100.0, yield_=("Y(dry)", "Y(dry)"), leaf=("CC", "CC_max"),
                     missing=-9),
}


def phen_time(dap, edat, adat, mdat):
    """Days after sowing -> phenological time: 0 at emergence, 1 at flowering, 2 at maturity."""
    return np.where(dap <= adat, (dap - edat) / max(adat - edat, 1), 1 + (dap - adat) / max(mdat - adat, 1))


def dates(s: pd.DataFrame, model: str) -> pd.DataFrame:
    """Emergence, flowering and maturity in days after sowing (NaN when not reached)."""
    if model == "aquacrop":
        return s[["EMR_dap", "FLO_dap", "MAT_dap"]].set_axis(["E", "A", "M"], axis=1)
    out = {}
    pdat = pd.to_datetime(s["PDAT"].astype("Int64").astype(str), format="%Y%j", errors="coerce")
    for c, n in (("EDAT", "E"), ("ADAT", "A"), ("MDAT", "M")):
        out[n] = (pd.to_datetime(s[c].astype("Int64").astype(str), format="%Y%j", errors="coerce") - pdat).dt.days
    return pd.DataFrame(out, index=s.index)


def analyse(model: str) -> list[str]:
    cfg = MODELS[model]
    data = ROOT / "data" / cfg["data"]
    t = load(data)
    s = t["summary"].set_index("sample")
    d = t[cfg["table"]].copy()
    num = [c for c in d.columns if c not in ("sample", "DAP")]
    d[num] = d[num].where(d[num] > cfg["missing"])          # first DSSAT pilot run kept -99 as a value
    d = d.join(dates(s, model), on="sample")
    lines = [f"== {model} =="]

    ycol, ysum = cfg["yield_"]
    lcol, lsum = cfg["leaf"]
    last = d.groupby("sample").last()
    ok = s.loc[last.index, ysum] > 0
    rel = ((last[ycol] - s.loc[last.index, ysum]).abs() / s.loc[last.index, ysum])[ok]
    leaf = d.groupby("sample")[lcol].max()
    n = d["sample"].nunique()
    lines += [f"seasons: {n}, daily rows: {len(d)} ({len(d) / n:.0f} per season)",
              f"last {ycol} vs season {ysum}: median rel. diff {rel.median():.4f}, 99th pct {rel.quantile(.99):.4f}",
              f"max {lcol} vs {lsum}: median abs diff {(leaf - s.loc[leaf.index, lsum]).abs().median():.3f}",
              f"seasons without maturity: {(~s['matured'].astype(bool)).sum() if 'matured' in s else dates(s, model)['M'].isna().sum()} of {len(s)}",
              "missing share: " + ", ".join(f"{c} {d[c].isna().mean():.3f}" for c in num)]

    full = d.dropna(subset=["E", "A", "M"])
    full = full[(full["A"] > full["E"]) & (full["M"] > full["A"])]
    for k in (8, 12, 16, 24):
        errs = {c: [] for c in cfg["growth"]}
        errs["stress bins"] = []
        for _, g in full.groupby("sample"):
            r = g.iloc[0]
            g = g[(g["DAP"] >= r.E) & (g["DAP"] <= r.M)]
            if model == "aquacrop":       # last day: AquaCrop sets CC to 0 (end of cycle, not senescence)
                g = g.iloc[:-1]
            if len(g) < 10:
                continue
            tau = phen_time(g["DAP"].to_numpy(), r.E, r.A, r.M)
            grid = np.concatenate([np.linspace(0, 1, k), np.linspace(1, 2, k)[1:]])
            for c in cfg["growth"]:
                y = g[c].to_numpy(dtype=float)
                if np.isnan(y).any() or np.nanmax(np.abs(y)) == 0:
                    continue
                back = np.interp(tau, grid, np.interp(grid, tau, y))
                errs[c].append(np.sqrt(np.mean((back - y) ** 2)) / np.nanmax(np.abs(y)))
            y = np.nan_to_num(g[cfg["stress"]].to_numpy(dtype=float)) / cfg["stress_scale"]
            if y.max() > 0:
                idx = np.clip(np.digitize(tau, grid) - 1, 0, len(grid) - 2)
                means = np.array([y[idx == i].mean() if (idx == i).any() else 0 for i in range(len(grid) - 1)])
                smooth = pd.Series(y).rolling(7, center=True, min_periods=1).mean().to_numpy()
                errs["stress bins"].append(np.sqrt(np.mean((means[idx] - smooth) ** 2)))
        lines.append(f"K={k:>2} per phase: rel. RMSE " + ", ".join(
            f"{c} {np.median(v):.3f} (p95 {np.quantile(v, .95):.3f})" for c, v in errs.items() if v)
            + f"  [stress {cfg['stress']} bins: abs. RMSE on 0..1]")

    rng = np.random.default_rng(0)
    pick = rng.choice(full["sample"].unique(), size=8, replace=False)
    show = [cfg["growth"][0], cfg["growth"][1], cfg["stress"]]
    fig, ax = plt.subplots(3, 2, figsize=(11, 9), constrained_layout=True)
    for sid in pick:
        g = full[full["sample"] == sid]
        r = g.iloc[0]
        tau = phen_time(g["DAP"].to_numpy(), r.E, r.A, r.M)
        for row, c in enumerate(show):
            ax[row, 0].plot(g["DAP"], g[c], lw=1)
            ax[row, 1].plot(tau, g[c], lw=1)
            ax[row, 0].set_ylabel(c)
    ax[0, 0].set_title(f"{model}: days after sowing")
    ax[0, 1].set_title("phenological time (0 emergence, 1 flowering, 2 maturity)")
    for a in ax[:, 1]:
        a.set_xlim(-0.2, 2.05)
    fig.savefig(OUT / f"pilot_curves_{model}.png", dpi=110)
    plt.close(fig)

    size = sum(f.stat().st_size for f in (data / cfg["table"]).glob("*.parquet"))
    lines.append(f"daily parquet: {size / 1e6:.1f} MB for {n} seasons -> {size / n * 117720 / 1e9:.2f} GB for 117,720")
    return lines


def main():
    models = sys.argv[1:] or [m for m, c in MODELS.items() if (ROOT / "data" / c["data"]).exists()]
    for m in models:
        lines = analyse(m)
        (OUT / f"pilot_summary_{m}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
