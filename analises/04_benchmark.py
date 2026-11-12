"""Benchmark of emulation methods (spatial blocks vs random folds) and learning curve: tables and figures.

    python analises/04_benchmark.py
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from common import MODELS, ROOT, SERIES, TAB, save

NAMES = {"ridge": "Ridge\nregression", "gb": "Gradient\nboosting", "mlp": "MLP", "mlp_grouped": "MLP by\noutput group",
         "mlp_offset": "MLP by group\n+ thermal offset"}
KEY = {"dssat": ("HWAM", "MDAT_dap", "ETCM", 1e-3), "aquacrop": ("Y(dry)", "MAT_dap", "ET_crop", 1.0)}
rows, per_output = [], []
for m, cfg in MODELS.items():
    b = ROOT / "data" / cfg["data"] / "benchmark"
    s = pd.read_csv(b / "summary.csv")
    yld, mat, et, sc = KEY[m]
    for r in s.itertuples():
        met = pd.read_csv(b / f"{r.emulator}_{r.validation}_metrics.csv", index_col=0)
        met = met[~met["derived"]]
        rows.append({"model": m, "emulator": r.emulator, "validation": r.validation, "outputs": r.outputs,
                     "median_r2": met["r2"].median(), "yield_rmse": met.loc[yld, "rmse"] * sc, "yield_r2": met.loc[yld, "r2"],
                     "maturity_rmse": met.loc[mat, "rmse"], "et_rmse": met.loc[et, "rmse"],
                     "fit_s_per_fold": r.fit_s_per_fold, "predict_us_per_row": r.predict_us_per_row})
        per_output.append(met.assign(model=m, emulator=r.emulator, validation=r.validation))
bench = pd.DataFrame(rows)
bench.to_csv(TAB / "benchmark_methods.csv", index=False)
print(bench.round(3).to_string())

# optimism of random folds, per output (same emulator, same outputs)
po = pd.concat(per_output).reset_index().rename(columns={"index": "target", "target": "target"})
piv = po.pivot_table(index=["model", "emulator", "target"], columns="validation", values="rmse")
piv = piv.dropna()
piv["inflation_%"] = 100 * (piv["block"] / piv["random"] - 1)
infl = piv.groupby(["model", "emulator"])["inflation_%"].describe()[["count", "50%", "min", "max"]]
infl.to_csv(TAB / "random_vs_block_inflation.csv")
print(infl.round(1).to_string())

fig, axes = plt.subplots(1, 2, figsize=(7.5, 3.2), sharey=True)
order = ["ridge", "gb", "mlp", "mlp_grouped", "mlp_offset"]
for ax, (m, cfg) in zip(axes, MODELS.items()):
    t = bench[bench["model"] == m].set_index(["emulator", "validation"])
    ems = [e for e in order if (e, "block") in t.index and (e, "random") in t.index]
    x = np.arange(len(ems))
    ax.bar(x - 0.2, [t.loc[(e, "random"), "yield_rmse"] for e in ems], 0.4, color="#9ec5f4", label="random folds")
    ax.bar(x + 0.2, [t.loc[(e, "block"), "yield_rmse"] for e in ems], 0.4, color=SERIES[0], label="5° spatial blocks")
    for i, e in enumerate(ems):
        ax.text(i + 0.2, t.loc[(e, "block"), "yield_rmse"], f"{t.loc[(e, 'block'), 'median_r2']:.2f}", ha="center", va="bottom", fontsize=6)
    ax.set_xticks(x, [NAMES[e] for e in ems], fontsize=6.5)
    ax.set(title=cfg["label"], ylabel="RMSE of grain yield (t ha$^{-1}$)" if m == "dssat" else "")
    ax.grid(axis="x", visible=False)
axes[0].legend(loc="upper right")
fig.tight_layout()
save(fig, "fig_methods")

# learning curve
lc = pd.read_csv(TAB / "learning_curve_all.csv")
g = lc.groupby(["model", "fraction"]).agg(points=("points", "mean"), seasons=("seasons", "mean"),
                                         yield_rmse=("rmse_yield", "mean"), yield_sd=("rmse_yield", "std"),
                                         maturity_rmse=("rmse_maturity", "mean"), et_rmse=("rmse_et", "mean"),
                                         median_r2=("median_r2", "mean"), fit_s=("fit_s", "mean")).reset_index()
g.loc[g["model"] == "dssat", ["yield_rmse", "yield_sd"]] *= 1e-3
g.to_csv(TAB / "learning_curve_summary.csv", index=False)
print(g.round(3).to_string())
fig, axes = plt.subplots(1, 3, figsize=(7.5, 2.6))
for k, (m, cfg) in enumerate(MODELS.items()):
    d = g[g["model"] == m]
    for ax, col, lab in zip(axes, ["yield_rmse", "maturity_rmse", "median_r2"],
                            ["RMSE of yield (t ha$^{-1}$)", "RMSE of maturity (d)", "median R² of all outputs"]):
        ax.plot(d["points"], d[col], marker="o", ms=3.5, color=SERIES[k], label=cfg["label"])
        ax.set(xscale="log", xlabel="training points (60 seasons each)", ylabel=lab)
fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.01))
fig.tight_layout(rect=(0, 0.1, 1, 1))
save(fig, "fig_learning_curve")
