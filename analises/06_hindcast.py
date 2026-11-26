"""Hindcast of the crop monitoring (web/tests/hindcast_monitor.mjs): skill of the expected yield along the season.

For each independent site, target season Y (1995-2024) and day k after sowing, the scenarios are the other
years completing the weather of Y after k (leave-one-year-out); the reference is the emulator with the
complete weather of Y. Metrics by day after sowing, pooled over sites and years:
  - RMSE and bias of the median of the scenarios (the expected yield of the app);
  - CRPS of the scenario ensemble and its skill against the forecast at sowing;
  - coverage of the 10-90 % range (80 % expected if the scenarios are calibrated);
  - poor seasons (reference below the site's 20th percentile): Brier skill score of the share of scenarios
    below the threshold, against the climatological 0.2;
  - the scenario of the most similar year against the median (mean absolute error).

    python analises/06_hindcast.py [data/hindcast/hindcast_monitor.csv]
"""
import sys

import numpy as np
import pandas as pd

from common import ROOT, TAB, plt, save, SERIES

csv = sys.argv[1] if len(sys.argv) > 1 else ROOT / "data" / "hindcast" / "hindcast_monitor.csv"
d = pd.read_csv(csv)
scale = {"dssat": 1e-3, "aquacrop": 1.0}                                   # -> t/ha
for c in ["truth_rf", "truth_p", "rf", "p"]:
    d[c] = d[c] * d["model"].map(scale)
d = d.dropna(subset=["rf", "truth_rf"])
LABEL = {"dssat": "DSSAT", "aquacrop": "AquaCrop"}

# reference B: the crop models run with the actual weather (benchmark/hindcast_sims.py), same inputs
sims_csv = ROOT / "data" / "hindcast" / "sims" / "sim_yields.csv"
SIM = None
if sims_csv.exists():
    sy = pd.read_csv(sims_csv)
    SIM = sy.pivot_table(index=["site", "model", "year"], columns="rainfed", values="yield").rename(
        columns={True: "sim_rf", False: "sim_p"}).reset_index()
    d = d.merge(SIM, on=["site", "model", "year"], how="left")


def crps(x, y):
    x = np.sort(x)
    n = len(x)
    # mean |x_i - y| - 0.5 mean |x_i - x_j|  (sorted form of the second term)
    return np.mean(np.abs(x - y)) - np.sum((2 * np.arange(1, n + 1) - n - 1) * x) / n ** 2


# poor-season threshold: 20th percentile of the reference yield of each site and model
thr = d.drop_duplicates(["site", "model", "year"]).groupby(["site", "model"])["truth_rf"].quantile(0.2).rename("thr")
d = d.join(thr, on=["site", "model"])

rows = []
for (site, model, year, das), g in d.groupby(["site", "model", "year", "das"]):
    x, y = g["rf"].to_numpy(), g["truth_rf"].iloc[0]
    best = g.loc[g["sim_rank"] == 1, "rf"]
    gap_t = max(g["truth_p"].iloc[0] - y, 0)
    rows.append(dict(site=site, model=model, year=year, das=das, truth=y, truth_mat=g["truth_mat"].iloc[0],
                     med=np.median(x), p10=np.quantile(x, 0.1), p90=np.quantile(x, 0.9), crps=crps(x, y),
                     prob_poor=np.mean(x < g["thr"].iloc[0]), poor=float(y < g["thr"].iloc[0]),
                     similar=best.iloc[0] if len(best) else np.nan,
                     gap_true=gap_t, gap_med=np.median(np.maximum(g["p"].to_numpy() - x, 0)), n=len(x),
                     sim=g["sim_rf"].iloc[0] if "sim_rf" in g else np.nan,
                     crps_sim=crps(x, g["sim_rf"].iloc[0]) if "sim_rf" in g else np.nan))
s = pd.DataFrame(rows)
s["err"] = s["med"] - s["truth"]
s["inside"] = ((s["truth"] >= s["p10"]) & (s["truth"] <= s["p90"])).astype(float)
s["brier"] = (s["prob_poor"] - s["poor"]) ** 2
s["ae_sim"] = (s["similar"] - s["truth"]).abs()
s["ae_med"] = s["err"].abs()
s["ae_gap"] = (s["gap_med"] - s["gap_true"]).abs()
# range widened by the emulation error: spatial-block yield RMSE of the v3 emulators added in quadrature
SIGMA = {"dssat": 0.343, "aquacrop": 0.510}
z = 1.2816                                                               # 10th/90th percentile of a normal
sg = s["model"].map(SIGMA) * z
s["p10w"] = s["med"] - np.sqrt((s["med"] - s["p10"]) ** 2 + sg ** 2)
s["p90w"] = s["med"] + np.sqrt((s["p90"] - s["med"]) ** 2 + sg ** 2)
# anomalies from the site mean (removes the differences between sites from the correlation)
s["truth_anom"] = s["truth"] - s.groupby(["site", "model", "das"])["truth"].transform("mean")
s["med_anom"] = s["med"] - s.groupby(["site", "model", "das"])["med"].transform("mean")


def summarise(g):
    c0 = g.attrs.get("c0")
    return pd.Series(dict(
        n=len(g), rmse=np.sqrt(np.mean(g["err"] ** 2)), bias=g["err"].mean(), mae=g["ae_med"].mean(),
        crps=g["crps"].mean(), coverage=100 * g["inside"].mean(), width=(g["p90"] - g["p10"]).mean(),
        brier=g["brier"].mean(), bss=1 - g["brier"].mean() / (0.2 * 0.8),
        mae_similar=g["ae_sim"].mean(), mae_gap=g["ae_gap"].mean(),
        corr=np.corrcoef(g["med"], g["truth"])[0, 1] if g["med"].std() > 0 else np.nan,
        r_anom=np.corrcoef(g["med_anom"], g["truth_anom"])[0, 1] if g["med_anom"].std() > 0 else np.nan,
        sd_truth=g["truth_anom"].std(),
        # against the crop models (emulation + scenario error)
        mae_sim=(g["med"] - g["sim"]).abs().mean(), crps_sim=g["crps_sim"].mean(),
        coverage_sim=100 * ((g["sim"] >= g["p10"]) & (g["sim"] <= g["p90"])).mean(),
        emu_rmse=np.sqrt(np.mean((g["truth"] - g["sim"]) ** 2)),
        coverage_sim_wide=100 * ((g["sim"] >= g["p10w"]) & (g["sim"] <= g["p90w"])).mean()))


by = s.groupby(["model", "das"]).apply(summarise, include_groups=False).reset_index()
c0 = by[by["das"] == 0].set_index("model")["crps"]
by["crpss"] = 1 - by["crps"] / by["model"].map(c0)
by.round(4).to_csv(TAB / "hindcast_by_das.csv", index=False)
site = s.groupby(["model", "site", "das"]).apply(summarise, include_groups=False).reset_index()
site.round(4).to_csv(TAB / "hindcast_by_site.csv", index=False)
mat = s.drop_duplicates(["site", "model", "year"]).groupby("model")["truth_mat"].median()

pd.set_option("display.width", 200)
s.round(4).to_csv(TAB / "hindcast_seasons.csv", index=False)
print(by[["model", "das", "n", "rmse", "sd_truth", "bias", "r_anom", "crps", "crpss", "coverage", "width", "bss", "mae", "mae_similar", "mae_gap"]].round(3).to_string(index=False))
print("\nagainst the crop models (reference B):")
print(by[["model", "das", "mae", "mae_sim", "crps", "crps_sim", "coverage", "coverage_sim", "coverage_sim_wide", "emu_rmse"]].round(3).to_string(index=False))
print("median cycle (days):", mat.to_dict())

# ---- figure: 4 panels against days after sowing
fig, ax = plt.subplots(2, 2, figsize=(7.2, 5.4), sharex=True)
for k, (model, col) in enumerate([("dssat", SERIES[0]), ("aquacrop", SERIES[1])]):
    b = by[by["model"] == model]
    for st, gs in site[site["model"] == model].groupby("site"):
        ax[1, 0].plot(gs["das"], gs["coverage"], color=col, lw=0.5, alpha=0.35)
    ax[0, 0].plot(b["das"], b["mae"], color=col, lw=2, marker="o", ms=3, label=LABEL[model])
    ax[0, 1].plot(b["das"], b["crpss"], color=col, lw=2, marker="o", ms=3, label=LABEL[model])
    ax[1, 0].plot(b["das"], b["coverage"], color=col, lw=2, marker="o", ms=3)
    ax[1, 1].plot(b["das"], b["bss"], color=col, lw=2, marker="o", ms=3)
    ax[0, 0].plot(b["das"], b["mae_similar"], color=col, lw=1.4, ls=":")
    if SIM is not None:
        ax[0, 0].plot(b["das"], b["mae_sim"], color=col, lw=1.4, ls="--")
        ax[1, 0].plot(b["das"], b["coverage_sim"], color=col, lw=1.4, ls="--")
        ax[1, 0].plot(b["das"], b["coverage_sim_wide"], color=col, lw=1.4, ls=":")
    for a in ax.flat:
        a.axvline(mat[model], color=col, lw=0.6, ls="-.", alpha=0.5)
ax[0, 0].plot([], [], color="0.4", ls=":", lw=1.4, label="most similar year")
if SIM is not None:
    ax[0, 0].plot([], [], color="0.4", ls="--", lw=1.4, label="against the crop model")
ax[1, 0].axhline(80, color="0.3", lw=0.8)
if SIM is not None:
    ax[1, 0].plot([], [], color="0.4", ls="--", lw=1.4, label="against the crop model")
    ax[1, 0].plot([], [], color="0.4", ls=":", lw=1.4, label="same, range + emulation error")
    ax[1, 0].legend(loc="lower left")
ax[0, 1].axhline(0, color="0.3", lw=0.8)
ax[1, 1].axhline(0, color="0.3", lw=0.8)
ax[0, 0].set_ylabel("Mean absolute error (t ha$^{-1}$)")
ax[0, 1].set_ylabel("CRPS skill vs. sowing")
ax[1, 0].set_ylabel("Seasons inside the 10–90% range (%)")
ax[1, 1].set_ylabel("Brier skill, poor seasons")
for a in ax[1]:
    a.set_xlabel("Days after sowing with known weather")
for a, t in zip(ax.flat, "abcd"):
    a.set_title(f"({t})", loc="left")
ax[0, 0].legend(loc="upper right")
fig.tight_layout()
save(fig, "fig_hindcast")
print("saved fig_hindcast and tables hindcast_by_das.csv, hindcast_by_site.csv")

# ---- case study: Passo Fundo-RS, season 2021/22 (La Niña drought), sown on 30 November 2021
CASE_SITE, CASE_YEAR, CASE_LATLON = "Passo Fundo-RS", 2021, (-28.26, -52.41)
c = s[(s["site"] == CASE_SITE) & (s["year"] == CASE_YEAR)]
if len(c):
    from datetime import date, timedelta

    from cropemu.weather import fetch, fill_gaps

    fig, ax = plt.subplots(1, 3, figsize=(7.2, 2.6))
    for k, (model, col) in enumerate([("dssat", SERIES[0]), ("aquacrop", SERIES[1])]):
        g = c[c["model"] == model].sort_values("das")
        a = ax[k]
        a.fill_between(g["das"], g["p10"], g["p90"], color=col, alpha=0.18, lw=0, label="10–90% of the scenarios")
        a.plot(g["das"], g["med"], color=col, lw=2, marker="o", ms=3, label="expected yield (median)")
        a.axhline(g["truth"].iloc[0], color="0.2", lw=1, ls="--", label="emulator, actual weather")
        if g["sim"].notna().any():
            a.axhline(g["sim"].iloc[0], color="0.2", lw=1, ls=":", label="crop model, actual weather")
        a.axvline(g["truth_mat"].iloc[0], color="0.5", lw=0.6, ls="-.")
        a.set_title(f"({'ab'[k]}) {LABEL[model]}", loc="left")
        a.set_xlabel("Days after sowing with known weather")
        a.set_ylim(bottom=0)
    ax[0].set_ylabel("Yield (t ha$^{-1}$)")
    h, lab = ax[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=4, bbox_to_anchor=(0.36, 0.02), fontsize=6.8)
    # rain accumulated since sowing: the season against the past years
    w = fill_gaps(fetch(*CASE_LATLON, "1984-01-01", "2025-12-31"))["rain"]
    sow = date(CASE_YEAR, 11, 30)
    acc = {}
    for y in range(1984, 2025):
        s0 = pd.Timestamp(date(y, 11, 30))
        r = w.loc[s0:s0 + pd.Timedelta(days=150)].to_numpy()
        if len(r) == 151:
            acc[y] = np.cumsum(r)
    days = np.arange(151)
    others = np.array([v for y, v in acc.items() if y != CASE_YEAR])
    a = ax[2]
    a.fill_between(days, np.quantile(others, 0.1, axis=0), np.quantile(others, 0.9, axis=0), color="0.6", alpha=0.3,
                   lw=0, label="other years, 10–90%")
    a.plot(days, np.median(others, axis=0), color="0.4", lw=1, label="other years, median")
    a.plot(days, acc[CASE_YEAR], color=SERIES[0], lw=2, label=f"{CASE_YEAR}/{CASE_YEAR % 100 + 1}")
    a.set_title("(c) Rain since sowing", loc="left")
    a.set_xlabel("Days after sowing")
    a.set_ylabel("mm")
    a.legend(loc="upper left", fontsize=6.3)
    fig.tight_layout()
    save(fig, "fig_hindcast_case")
    print(c[["model", "das", "med", "p10", "p90", "truth", "sim"]].round(2).to_string(index=False))
    print("rain at 60/90 DAS:", acc[CASE_YEAR][60].round(0), acc[CASE_YEAR][90].round(0),
          "other years median:", np.median(others[:, 60]).round(0), np.median(others[:, 90]).round(0))
