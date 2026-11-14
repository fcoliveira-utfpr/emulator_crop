"""Where the emulators were trained and tested: global map of the sites and their roles.

    python analises/05_sites.py

(a) the 1,962 training points (60 simulated seasons each) by world region, soybean area or
expansion area, and the 7 independent sites where the emulators were compared with new runs of the
crop models; (b) the 5° blocks coloured by the cross-validation fold that held them out.
Writes figures/fig_sites.png and tables/sites_by_region.csv.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

from common import REGIONS, ROOT, SERIES, TAB, draw_land, regions, save
from cropemu_bench.evaluate import splits

#: Independent sites of examples/compare_emulator_simulator.ipynb (not in the training data).
INDEPENDENT = [("Londrina", -23.19, -51.18), ("Rio Verde", -17.80, -50.92), ("Sorriso", -12.55, -55.71),
               ("Passo Fundo", -28.26, -52.41), ("Pergamino", -33.89, -60.57), ("Ames", 42.03, -93.62),
               ("Harbin", 46.20, 126.70)]

pts = pd.read_parquet(ROOT / "data" / "dssat_v1" / "points.parquet")
pts = pd.concat([pts.reset_index(drop=True), regions(pts["lat"], pts["lon"])], axis=1)
pts["kind_label"] = pts["kind"].map({"soy": "soybean area", "expansion": "expansion area"})

# folds of the block validation (same as the benchmark: one fold per 5° block)
fold_of_block = {}
for k, (_, te) in enumerate(splits(len(pts), pts["block"], 5, 0)):
    for b in pts["block"].iloc[te]:
        fold_of_block[b] = k

tab = (pts.groupby("region").agg(points=("id", "size"), soybean=("kind", lambda s: int((s == "soy").sum())),
                                 expansion=("kind", lambda s: int((s == "expansion").sum())),
                                 blocks=("block", "nunique"), countries=("country", "nunique"),
                                 lat_min=("lat", "min"), lat_max=("lat", "max"))
       .reindex(REGIONS))
tab["seasons"] = tab["points"] * 60
tab.to_csv(TAB / "sites_by_region.csv")
print(tab.to_string())

colors = dict(zip(REGIONS, SERIES))
fig, axes = plt.subplots(2, 1, figsize=(7.5, 8.2))
ax = axes[0]
draw_land(ax)
for reg in REGIONS:
    for kind, marker, face in (("soy", "o", True), ("expansion", "^", False)):
        d = pts[(pts["region"] == reg) & (pts["kind"] == kind)]
        ax.scatter(d["lon"], d["lat"], s=7 if kind == "soy" else 9, marker=marker, linewidths=0.6,
                   facecolors=colors[reg] if face else "none", edgecolors=colors[reg], zorder=2)
ind = pd.DataFrame(INDEPENDENT, columns=["name", "lat", "lon"])
ax.scatter(ind["lon"], ind["lat"], marker="*", s=110, c="k", edgecolors="white", linewidths=0.8, zorder=4)
for r in ind.itertuples():
    dx, ha = (3, "left") if r.name not in ("Pergamino", "Passo Fundo", "Londrina") else (-3, "right")
    ax.annotate(r.name, (r.lon, r.lat), xytext=(dx, 2), textcoords="offset points", fontsize=6.5, ha=ha,
                zorder=5, bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.75))
handles = [Line2D([], [], marker="o", ls="", color=colors[r], ms=4.5, label=f"{r} ({tab.loc[r, 'points']})")
           for r in REGIONS]
handles += [Line2D([], [], marker="o", ls="", color="0.4", ms=4.5, label="soybean area (1,671)"),
            Line2D([], [], marker="^", ls="", mfc="none", mec="0.4", ms=5, label="expansion area (291)"),
            Line2D([], [], marker="*", ls="", color="k", ms=9, label="independent site (7)")]
ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.06), fontsize=6.3, ncol=4, frameon=False,
          handletextpad=0.2, columnspacing=1.0)
ax.set(xlim=(-130, 155), ylim=(-50, 66), aspect="equal", ylabel="latitude",
       title="(a) Training points (60 seasons each) by world region, and independent test sites")

ax = axes[1]
draw_land(ax)
for b, g in pts.groupby("block"):
    lon0, lat0 = np.floor(g["lon"].min() / 5) * 5, np.floor(g["lat"].min() / 5) * 5
    ax.add_patch(Rectangle((lon0, lat0), 5, 5, facecolor=SERIES[fold_of_block[b]], alpha=0.55,
                           edgecolor="white", linewidth=0.4, zorder=1))
ax.scatter(pts["lon"], pts["lat"], s=1.2, c="k", linewidths=0, zorder=2)
ax.legend(handles=[Patch(facecolor=SERIES[k], alpha=0.55, label=f"fold {k + 1}") for k in range(5)],
          loc="upper center", bbox_to_anchor=(0.5, -0.13), fontsize=6.5, ncol=5, frameon=False)
ax.set(xlim=(-130, 155), ylim=(-50, 66), aspect="equal", xlabel="longitude", ylabel="latitude",
       title=f"(b) Cross-validation: {pts['block'].nunique()} blocks of 5° × 5°, each held out in one of five folds")
for a in axes:
    a.grid(False)
fig.tight_layout()
save(fig, "fig_sites")
