"""Structure of the emulation error (out-of-fold predictions, 5° spatial blocks): outputs, strata,
maps, within-site variability and response to the climate perturbations.

    python analises/02_error_structure.py
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from common import FIG, LEVEL_COLOR, MODELS, ROOT, SERIES, TAB, load, r2, rmse, save

data = {m: load(m) for m in MODELS}

# ---------------------------------------------------------------- 1. outputs and acceptance levels
rows = []
for m, cfg in MODELS.items():
    b = ROOT / "data" / cfg["data"] / "benchmark"
    met = pd.read_csv(b / f"{cfg['emulator']}_block_metrics.csv", index_col=0)
    acc = pd.read_csv(b / f"acceptance_{cfg['emulator']}_block.csv", index_col=0)
    t = met.join(acc[[c for c in acc.columns if c not in met.columns]])
    t.insert(0, "model", m)
    rows.append(t)
outputs = pd.concat(rows)
outputs.to_csv(TAB / "outputs_metrics.csv")
print(outputs.groupby("model")["level"].value_counts().unstack(fill_value=0))
print(outputs.groupby("model")["r2"].describe()[["50%", "min", "max"]].round(3))

fig, axes = plt.subplots(1, 2, figsize=(7.5, 6.2))
for ax, (m, cfg) in zip(axes, MODELS.items()):
    t = outputs[outputs["model"] == m].dropna(subset=["r2"]).sort_values("r2")
    ax.hlines(range(len(t)), 0, t["r2"].clip(lower=0), color="0.85", lw=1)
    ax.scatter(t["r2"].clip(lower=0), range(len(t)), c=[LEVEL_COLOR.get(v, "0.5") for v in t["level"]], s=22, zorder=3)
    ax.set_yticks(range(len(t)), t.index, fontsize=6)
    ax.set(xlim=(0, 1.02), xlabel="R² (spatial block validation)", title=cfg["label"])
    ax.grid(axis="y", visible=False)
handles = [plt.Line2D([], [], marker="o", ls="", color=col, ms=5, label=lev) for lev, col in LEVEL_COLOR.items()]
fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.01), title="acceptance level")
fig.tight_layout(rect=(0, 0.06, 1, 1))
save(fig, "fig_outputs_r2")

# ---------------------------------------------------------------- 2. simulated vs emulated (key outputs)
fig, axes = plt.subplots(2, 3, figsize=(7.5, 5))
key_rows = []
for r, (m, cfg) in enumerate(MODELS.items()):
    X, Y, P, info = data[m]
    for c, (col, lab, sc) in enumerate([(cfg["yld"], "grain yield (t ha$^{-1}$)", cfg["yscale"]),
                                        (cfg["mat"], "maturity (days after sowing)", 1),
                                        (cfg["et"], "evapotranspiration (mm)", 1)]):
        ax = axes[r, c]
        y, p = Y[col] * sc, P[col] * sc
        ok = y.notna() & p.notna()
        lo, hi = np.nanpercentile(y[ok], [0.1, 99.9])
        ax.hexbin(y[ok], p[ok], gridsize=60, cmap="Blues", mincnt=1, bins="log", extent=(lo, hi, lo, hi), linewidths=0)
        ax.plot([lo, hi], [lo, hi], color="0.3", lw=0.8)
        e = (p - y)[ok]
        key_rows.append({"model": m, "output": col, "n": int(ok.sum()), "rmse": rmse(e), "bias": e.mean(),
                         "r2": r2(y[ok], p[ok]), "mean": y[ok].mean()})
        ax.set(xlim=(lo, hi), ylim=(lo, hi), title=f"{cfg['label'].split()[0]}: {lab}\nRMSE {rmse(e):.2f}, R² {r2(y[ok], p[ok]):.3f}"
               if sc != 1 or "yield" in lab else f"{cfg['label'].split()[0]}: {lab}\nRMSE {rmse(e):.1f}, R² {r2(y[ok], p[ok]):.3f}")
        if r == 1:
            ax.set_xlabel("simulated")
        if c == 0:
            ax.set_ylabel("emulated")
fig.tight_layout()
save(fig, "fig_scatter_key")
pd.DataFrame(key_rows).to_csv(TAB / "key_outputs.csv", index=False)

# ---------------------------------------------------------------- 3. error by strata (yield)
def strata(info):
    lat = info["lat"].abs()
    s = pd.DataFrame(index=info.index)
    s["Köppen group"] = info["koppen"].str[0].map({"A": "A tropical", "B": "B arid", "C": "C temperate", "D": "D continental"})
    s["latitude"] = pd.cut(lat, [0, 15, 30, 45, 90], labels=["0-15°", "15-30°", "30-45°", ">45°"], include_lowest=True)
    s["water regime"] = np.where(info["water"], "rainfed", "no water stress")
    s["climate"] = np.where(info["perturbed"], "perturbed", "historical")
    s["point"] = info["kind"].map({"soy": "soybean area", "expansion": "outside soybean area"})
    return s

rows = []
for m, cfg in MODELS.items():
    X, Y, P, info = data[m]
    y, p = Y[cfg["yld"]] * cfg["yscale"], P[cfg["yld"]] * cfg["yscale"]
    s = strata(info)
    s["yield level"] = pd.qcut(y, 3, labels=["low", "medium", "high"])
    for col in s:
        for g, idx in s.groupby(col, observed=True).groups.items():
            e = (p - y).loc[idx]
            rows.append({"model": m, "stratum": col, "class": str(g), "n": int(e.notna().sum()), "mean_yield": y.loc[idx].mean(),
                         "rmse": rmse(e), "bias": e.mean(), "r2": r2(y.loc[idx], p.loc[idx]),
                         "rrmse_%": 100 * rmse(e) / y.loc[idx].mean()})
st = pd.DataFrame(rows)
st.to_csv(TAB / "yield_error_by_stratum.csv", index=False)
print(st.round(3).to_string())

fig, axes = plt.subplots(1, 2, figsize=(7.5, 4.6), sharey=True)
order = st[st["model"] == "dssat"].reset_index(drop=True)
labels = [f"{a}: {b}" for a, b in zip(order["stratum"], order["class"])]
for ax, (m, cfg) in zip(axes, MODELS.items()):
    t = st[st["model"] == m].reset_index(drop=True)
    colors = [SERIES[list(dict.fromkeys(t["stratum"])).index(v) % len(SERIES)] for v in t["stratum"]]
    ax.barh(range(len(t)), t["rmse"], color=colors, height=0.7)
    for i, v in enumerate(t["rrmse_%"]):
        ax.text(t["rmse"][i], i, f" {v:.0f}%", va="center", fontsize=6)
    ax.set_yticks(range(len(t)), labels, fontsize=6.5)
    ax.invert_yaxis(); ax.grid(axis="y", visible=False)
    ax.set(xlabel="RMSE of grain yield (t ha$^{-1}$); label: % of the mean", title=cfg["label"])
fig.tight_layout()
save(fig, "fig_error_strata")

# ---------------------------------------------------------------- 4. maps: per-point error of yield
fig, axes = plt.subplots(2, 1, figsize=(7.5, 6.4))
rows = []
for ax, (m, cfg) in zip(axes, MODELS.items()):
    X, Y, P, info = data[m]
    e = (P[cfg["yld"]] - Y[cfg["yld"]]) * cfg["yscale"]
    g = pd.DataFrame({"e": e, "y": Y[cfg["yld"]] * cfg["yscale"], "point": info["point"]}).groupby("point")
    pt = pd.DataFrame({"rmse": g["e"].apply(rmse), "bias": g["e"].mean(), "sd": g["y"].std()})
    pt = pt.join(info.groupby("point")[["lat", "lon"]].first())
    pt["model"] = m
    rows.append(pt)
    sc = ax.scatter(pt["lon"], pt["lat"], c=pt["rmse"], s=5, cmap="viridis_r", vmin=0, vmax=np.nanpercentile(pt["rmse"], 98), linewidths=0)
    plt.colorbar(sc, ax=ax, label="RMSE of yield (t ha$^{-1}$)", shrink=0.85, pad=0.01)
    ax.set(xlim=(-130, 150), ylim=(-45, 62), aspect="equal", title=f"{cfg['label']}: median {pt['rmse'].median():.2f} t ha$^{{-1}}$ per point",
           xlabel="longitude" if m == "aquacrop" else "", ylabel="latitude")
points = pd.concat(rows)
points.to_csv(TAB / "yield_error_by_point.csv")
fig.tight_layout()
save(fig, "fig_error_map")
print(points.groupby("model")["rmse"].describe()[["25%", "50%", "75%", "max"]].round(3))

# ---------------------------------------------------------------- 5. within-site variability (rainfed, historical climate)
rows = []
fig, axes = plt.subplots(1, 2, figsize=(7.5, 3))
for k, (m, cfg) in enumerate(MODELS.items()):
    X, Y, P, info = data[m]
    sel = info["water"] & ~info["perturbed"]
    d = pd.DataFrame({"y": Y.loc[sel, cfg["yld"]] * cfg["yscale"], "p": P.loc[sel, cfg["yld"]] * cfg["yscale"],
                      "point": info.loc[sel, "point"]}).dropna()
    g = d.groupby("point")
    w = pd.DataFrame({"n": g.size(), "r": g.apply(lambda x: x["y"].corr(x["p"]), include_groups=False),
                      "sd_sim": g["y"].std(), "sd_emu": g["p"].std(), "mean_sim": g["y"].mean(), "mean_emu": g["p"].mean()})
    w = w[w["n"] >= 15]
    w["sd_ratio"] = w["sd_emu"] / w["sd_sim"]
    w["model"] = m
    rows.append(w)
    axes[0].hist(w["r"].dropna(), bins=np.linspace(0, 1, 41), alpha=0.6, color=SERIES[k], label=f"{cfg['label'].split()[0]} (median {w['r'].median():.2f})")
    axes[1].hist(w["sd_ratio"].dropna().clip(0, 2), bins=np.linspace(0.3, 1.7, 41), alpha=0.6, color=SERIES[k],
                 label=f"{cfg['label'].split()[0]} (median {w['sd_ratio'].median():.2f})")
axes[0].set(xlabel="correlation between simulated and emulated yield within a point", ylabel="points"); axes[0].legend()
axes[1].set(xlabel="emulated / simulated standard deviation of yield within a point"); axes[1].axvline(1, color="0.3", lw=0.8); axes[1].legend()
fig.tight_layout()
save(fig, "fig_within_site")
within = pd.concat(rows)
within.to_csv(TAB / "within_site_variability.csv")
summ = []
for m, w in within.groupby("model"):
    summ.append({"model": m, "points": len(w), "r_median": w["r"].median(), "r_p10": w["r"].quantile(0.1),
                 "share_r_above_0.8": (w["r"] > 0.8).mean(), "sd_ratio_median": w["sd_ratio"].median(),
                 "sd_ratio_p10": w["sd_ratio"].quantile(0.1), "sd_ratio_p90": w["sd_ratio"].quantile(0.9),
                 "r_of_site_means": np.corrcoef(w["mean_sim"], w["mean_emu"])[0, 1],
                 "rmse_of_site_means": rmse(w["mean_emu"] - w["mean_sim"])})
summ = pd.DataFrame(summ)
summ.to_csv(TAB / "within_site_summary.csv", index=False)
print(summ.round(3).to_string())

# ---------------------------------------------------------------- 6. response to the climate perturbations
fig, axes = plt.subplots(2, 3, figsize=(7.5, 4.6), sharey="row")
rows = []
for r, (m, cfg) in enumerate(MODELS.items()):
    X, Y, P, info = data[m]
    sel = info["perturbed"] & Y[cfg["yld"]].notna()
    d = pd.DataFrame({"y": Y.loc[sel, cfg["yld"]] * cfg["yscale"], "p": P.loc[sel, cfg["yld"]] * cfg["yscale"],
                      "dt": info.loc[sel, "dt"], "rain_factor": info.loc[sel, "rain_factor"], "co2": info.loc[sel, "co2"],
                      "point": info.loc[sel, "point"], "water": info.loc[sel, "water"]}).dropna()
    # sensitivity: slopes of a linear model with point effects removed
    dm = d[["y", "p", "dt", "rain_factor", "co2"]] - d.groupby("point")[["y", "p", "dt", "rain_factor", "co2"]].transform("mean")
    A = dm[["dt", "rain_factor", "co2"]].to_numpy()
    for tgt in ("y", "p"):
        coef = np.linalg.lstsq(A, dm[tgt].to_numpy(), rcond=None)[0]
        rows.append({"model": m, "source": "simulated" if tgt == "y" else "emulated", "per °C": coef[0],
                     "per 10% rain": coef[1] * 0.1, "per 100 ppm CO2": coef[2] * 100, "n": len(d)})
    for c, (v, lab, bins) in enumerate([("dt", "temperature change (°C)", np.linspace(-1, 4, 6)),
                                        ("co2", "CO$_2$ (ppm)", np.linspace(350, 800, 6)),
                                        ("rain_factor", "rain factor", np.linspace(0.7, 1.3, 5))]):
        ax = axes[r, c]
        dd = d[d["water"]] if v == "rain_factor" else d
        b = pd.cut(dd[v], bins, include_lowest=True)
        gm = dd.groupby(b, observed=True)[["y", "p"]].mean()
        mid = [i.mid for i in gm.index]
        ax.plot(mid, gm["y"], marker="o", color="0.25", lw=1.5, ms=4, label="simulated")
        ax.plot(mid, gm["p"], marker="s", color=SERIES[r], lw=1.5, ms=4, ls="--", label="emulated")
        if r == 1:
            ax.set_xlabel(lab)
        if c == 0:
            ax.set_ylabel(f"{cfg['label'].split()[0]}\nmean yield (t ha$^{{-1}}$)"); ax.legend()
fig.tight_layout()
save(fig, "fig_responses")
resp = pd.DataFrame(rows)
resp.to_csv(TAB / "climate_response_slopes.csv", index=False)
print(resp.round(4).to_string())
