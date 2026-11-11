"""Writes examples/your_data.ipynb: the whole workflow from spreadsheets (sites, weather, soil,
seasons), with synthetic data from a simple, coherent generator, only to illustrate.

    python tools/notebooks/make_your_data_nb.py examples
"""
import sys
from pathlib import Path

import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

cells = [
md("""# Your data: from spreadsheets to predictions, comparison and calibration

This notebook starts from **spreadsheets**, as a user with their own farms would:

| spreadsheet | one row per | columns |
|---|---|---|
| sites (`locais.csv`) | farm or station | name, latitude, longitude (decimal degrees, south and west negative), elevation (m) |
| weather (`clima_<farm>.csv`) | day | date, radiation (MJ/m²/d), Tmax and Tmin (°C), rain (mm); optional: humidity (%), wind (m/s at 2 m), dew point (°C) |
| soil (`solo.csv`) | layer | profile, top and bottom (cm), clay, sand, silt (%), organic carbon or matter (%), bulk density (g/cm³); optional: measured wilting point and field capacity (cm³/cm³) |
| seasons (`safras.csv`) | field × season | farm, field, sowing date, cultivar, maturity group, irrigated (sim/não); optional observations: yield (kg/ha), flowering and maturity (dates) |

Column names may be in English or Portuguese, with units in parentheses; common unit mistakes
(radiation in W/m², humidity as a fraction, texture in g/kg, organic matter instead of carbon) are
converted with a warning.

**The data here are synthetic.** Section 2 downloads them from the GitHub repository; a simple
generator made them (8 fictitious farms in the Brazilian soybean belt, 1993-2024, 20 fields each)
only to show the workflow with a large, coherent data set. The "observations" are made with the emulator itself and a hidden cultivar, plus
noise, so that the calibration can be checked against a known answer. **To use your data, replace the
files in `my_data/` and skip section 2.**

1. the spreadsheet templates;
2. example data (synthetic, downloaded from GitHub);
3. reading and checking the data;
4. predicting every season;
5. comparison with the observations;
6. calibration of the cultivars (and the check against the hidden truth);
7. using the calibrated cultivars: sowing window and climate scenarios per farm;
8. the same data with the AquaCrop emulator;
9. export."""),
code("""try:
    import cropemu
    assert tuple(int(v) for v in cropemu.__version__.split(".")[:2]) >= (0, 3)
except (ImportError, AssertionError):     # install from PyPI (Intel Macs need --prefer-binary for rasterio)
    %pip install --quiet --prefer-binary "cropemu>=0.3"
    import cropemu

import time, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from cropemu.io import write_templates, read_sites, read_weather, read_soils, read_seasons
from cropemu.weather import check

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "0.9", "grid.linewidth": 0.6, "axes.edgecolor": "0.6",
                     "axes.titlesize": 10, "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
                     "legend.fontsize": 8, "legend.frameon": False, "figure.dpi": 110,
                     "axes.prop_cycle": plt.cycler(color=SERIES)})
print("cropemu", cropemu.__version__)"""),
md("""## 1. The spreadsheet templates

`write_templates` writes one example of each spreadsheet with the expected columns and units
(`lang="pt"` for Portuguese headers, `"en"` for English). Fill them in a spreadsheet program and
save as CSV (comma or semicolon; decimal point or comma), or read Excel files directly."""),
code("""templates = write_templates("templates", lang="pt")
for p in templates:
    print(f"--- {p.name}")
    print(p.read_text())"""),
md("""## 2. Example data (synthetic)

*With your own data, skip this section and put your files in `my_data/`.*

The example spreadsheets are in the GitHub repository
([`examples/data/your_data`](https://github.com/fcoliveira-utfpr/emulator_crop/tree/main/examples/data/your_data))
and are downloaded here from their raw links. They were made by
[`make_example_data.py`](https://github.com/fcoliveira-utfpr/emulator_crop/blob/main/examples/data/make_example_data.py),
a simple, coherent generator, only to illustrate:

- **weather** (1993-2024): rain from a two-state Markov chain (wet days persist) with a seasonal
  wet-day probability and amount, dry winter in the tropics and rain spread over the year in the
  south; temperature falling with latitude and elevation, a seasonal cycle growing with latitude
  and persistent day-to-day anomalies, cooler wet days; radiation as a fraction of the
  extraterrestrial radiation, lower on wet days; humidity and wind;
- **soil**: clay increasing and carbon decreasing with depth; farm E has laboratory water limits;
- **seasons**: 20 fields per farm, one of two cultivars per field and year, sowing spread over the
  farm's window, two irrigated fields;
- **observations**: the DSSAT emulator with hidden "true" cultivars (`hidden_cultivars.csv`: a
  little later and with longer seed filling than the defaults of their maturity group), times a
  field effect and a farm-year effect, plus measurement noise; some observations are missing.

Farm H's weather is written like a station logger (radiation in W/m², dates day first, `;` and
decimal comma) to show the unit checks."""),
code("""import os, urllib.request
RAW = "https://raw.githubusercontent.com/fcoliveira-utfpr/emulator_crop/main/examples/data/your_data"
SOURCE = os.environ.get("CROPEMU_EXAMPLE_DATA", RAW)          # a local folder also works
FILES = ["locais.csv", "solo.csv", "safras.csv", "hidden_cultivars.csv"] + [f"clima_{c}.csv" for c in "ABCDEFGH"]
DATA = Path("my_data"); DATA.mkdir(exist_ok=True)
for name in FILES:
    if not (DATA / name).exists():
        src = f"{SOURCE}/{name}"
        if src.startswith("http"):
            urllib.request.urlretrieve(src, DATA / name)
        else:
            (DATA / name).write_bytes(Path(src).read_bytes())
print(sorted(p.name for p in DATA.iterdir()))
print((DATA / "clima_H.csv").read_text().splitlines()[:3])"""),
code("""emu = cropemu.load("dssat-soybean-v1")
CATALOGUE = {"Cultivar 5.5": 5.5, "Cultivar 6.4": 6.4, "Cultivar 7.4": 7.4, "Cultivar 8.3": 8.3}
TRUE = pd.read_csv(DATA / "hidden_cultivars.csv", index_col="cultivar").T.to_dict()   # only to check the calibration
YEARS = range(1994, 2024)                                     # sowing years of the example
pd.DataFrame(TRUE).T[["mg", "LFMAX", "SFDUR", "SDPDV"]].round(2)"""),
md("""## 3. Reading and checking the data

From here on, the notebook only uses the files in `my_data/`: **this is where your data come in.**"""),
code("""sites = read_sites(DATA / "locais.csv")
soils = read_soils(DATA / "solo.csv")
seasons = read_seasons(DATA / "safras.csv")
weather = {}
for farm, s in sites.iterrows():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        w = read_weather(DATA / f"clima_{farm.split()[-1]}.csv", lat=s["lat"], lon=s["lon"], elev=s["elev"])
    rep = check(w)
    weather[farm] = w
    print(f"{farm}: {w.index.min():%Y-%m-%d} to {w.index.max():%Y-%m-%d}, columns {list(w.columns)}, "
          f"missing days {rep['missing_days']}, out of range {rep['out_of_range']}"
          + (f", converted: {w.attrs['conversions']}" if w.attrs["conversions"] else ""))
print(f"soils: {list(soils)}; seasons: {len(seasons)} ({seasons['site'].nunique()} farms, "
      f"{seasons.groupby('site')['field'].nunique().sum()} fields, {seasons['sowing'].dt.year.nunique()} years)")
seasons.head()"""),
code("""fig = plt.figure(figsize=(14, 8))
gs = fig.add_gridspec(2, 4)
ax = fig.add_subplot(gs[:, 0])
ax.scatter(sites["lon"], sites["lat"], s=50, color=SERIES[0])
for farm, s in sites.iterrows():
    ax.annotate(farm.split()[-1], (s["lon"], s["lat"]), xytext=(5, 3), textcoords="offset points")
ax.set(xlim=(-62, -44), ylim=(-32, -8), aspect="equal", xlabel="longitude", ylabel="latitude", title="farms")
for k, farm in enumerate(["Fazenda A", "Fazenda E", "Fazenda H"]):
    w = weather[farm]
    ax = fig.add_subplot(gs[0, k + 1])
    rain = w["rain"].groupby([w.index.year, w.index.month]).sum().groupby(level=1).mean()
    ax.bar(rain.index, rain, color="#86b6ef", width=0.7)
    ax2 = ax.twinx()
    m = w.groupby(w.index.month)[["tmax", "tmin"]].mean()
    ax2.plot(m.index, m["tmax"], color="#eb6834", lw=2); ax2.plot(m.index, m["tmin"], color="#2a78d6", lw=2)
    ax2.set_ylim(5, 38); ax2.grid(False)
    ax.set(title=f"{farm}: {w['rain'].resample('YS').sum().mean():.0f} mm/year", xlabel="month", ylabel="rain (mm/month)")
    ax.set_xticks(range(1, 13, 2))
ax = fig.add_subplot(gs[1, 1])
paw = {f: float(((p["dul"] - p["ll"]) * (p["bottom"] - p["top"]) * 10).sum()) if "dul" in p and p["dul"].notna().all()
       else float(cropemu.features.soil_features(emu.training_soil(p, sites.loc[f, "lat"]))["paw_mm"]) for f, p in soils.items()}
ax.barh([f.split()[-1] for f in paw], list(paw.values()), color=SERIES[2])
ax.set(xlabel="available water in 2 m (mm)", title="soil water (E: measured limits)")
ax = fig.add_subplot(gs[1, 2:])
order = list(sites.index)
ax.boxplot([seasons.loc[seasons["site"] == f, "obs_yield"].dropna() for f in order],
           showfliers=False, patch_artist=True, boxprops=dict(facecolor="#d6e6fa", color="0.4"), medianprops=dict(color="k"))
ax.set_xticks(range(1, len(order) + 1), [f.split()[-1] for f in order])
ax.set(ylabel="observed yield (kg/ha)", title="observed yields by farm")
fig.tight_layout(); plt.show()"""),
md("""## 4. Predicting every season

The cultivar of each season comes from its maturity group (`emu.cultivar(mg=...)`, the default
coefficients). The seasons of a farm, cultivar and water regime share one call; the inputs are kept
for the calibration (section 6)."""),
code("""def predict_all(emu, seasons, cultivars=None, family_out=("HWAM", "ADAT_dap", "MDAT_dap"), **kw):
    \"\"\"Predict every season; returns (outputs, inputs, out-of-domain flags) aligned with ``seasons``.\"\"\"
    outs, ins, ood = [], [], []
    for (farm, cv, irr), g in seasons.groupby(["site", "cultivar", "irrigated"]):
        s = sites.loc[farm]
        cult = cultivars[cv] if cultivars else emu.cultivar(mg=g["mg"].iloc[0])
        p = emu.predict(weather[farm], lat=s["lat"], elev=s["elev"], soil=soils[farm], sowing=list(g["sowing"]),
                        cultivar=cult, irrigated=bool(irr), **kw)
        outs.append(p.outputs[list(family_out)].set_axis(g.index)); ins.append(p.inputs.set_axis(g.index))
        ood.append(p.out_of_domain.set_axis(g.index))
    return pd.concat(outs).loc[seasons.index], pd.concat(ins).loc[seasons.index], pd.concat(ood).loc[seasons.index]

t0 = time.time()
pred, X, ood = predict_all(emu, seasons)
dt = time.time() - t0
seasons[["yield", "flowering", "maturity"]] = pred.to_numpy()
print(f"{len(seasons)} seasons in {dt:.1f} s ({1e3 * dt / len(seasons):.2f} ms per season, inputs from daily weather included)")
flag = ood.explode().dropna()
print("seasons with inputs out of the training domain:", int((ood.str.len() > 0).sum()),
      "| by farm and input:", flag.groupby([seasons.loc[flag.index, "site"], flag]).size().to_dict())
seasons[["site", "field", "sowing", "cultivar", "obs_yield", "yield", "obs_maturity", "maturity"]].head().round(0)"""),
md("""The clay of the topsoil of farms E and F (65-75 %) is above the largest value of the training data
(65 %): their seasons are flagged, and their predictions are extrapolations. With your data, check
these flags first; the training range of every input is in `emu.card["domain"]`."""),
md("""## 5. Comparison with the observations"""),
code("""def scores(o, p):
    d = pd.concat([o, p], axis=1).dropna()
    e = d.iloc[:, 1] - d.iloc[:, 0]
    return pd.Series({"n": len(d), "RMSE": np.sqrt((e ** 2).mean()), "bias": e.mean(), "r": d.corr().iloc[0, 1]})

fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
for ax, (o, p, lab) in zip(axes, [("obs_yield", "yield", "yield (kg/ha)"), ("obs_flowering", "flowering", "flowering (DAS)"),
                                   ("obs_maturity", "maturity", "maturity (DAS)")]):
    d = seasons[[o, p]].dropna()
    hb = ax.hexbin(d[o], d[p], gridsize=40, cmap="Blues", mincnt=1, bins="log")
    lim = [d.min().min(), d.max().max()]; ax.plot(lim, lim, color="0.3", lw=1)
    sc = scores(d[o], d[p])
    ax.set(xlabel="observed", ylabel="emulated (default cultivar)", title=f"{lab}\\nRMSE {sc['RMSE']:.0f}, bias {sc['bias']:+.0f}, n {sc['n']:.0f}")
fig.suptitle("before calibration: default coefficients of each maturity group", y=1.03)
fig.tight_layout(); plt.show()

by_farm = seasons.groupby("site").apply(lambda g: scores(g["obs_yield"], g["yield"]), include_groups=False)
by_year = seasons.groupby(seasons["sowing"].dt.year).apply(lambda g: scores(g["obs_yield"], g["yield"]), include_groups=False)
fig, axes = plt.subplots(1, 2, figsize=(14, 3.6), gridspec_kw={"width_ratios": [1, 2]})
axes[0].barh([f.split()[-1] for f in by_farm.index], by_farm["bias"], color=SERIES[1])
axes[0].set(xlabel="bias of yield (kg/ha)", title="by farm")
axes[1].plot(by_year.index, by_year["bias"], marker="o", color=SERIES[1], label="bias"); axes[1].plot(by_year.index, by_year["RMSE"], marker="o", color=SERIES[0], label="RMSE")
axes[1].axhline(0, color="0.5", lw=1); axes[1].set(xlabel="sowing year", ylabel="kg/ha", title="by year"); axes[1].legend()
fig.tight_layout(); plt.show()"""),
md("""## 6. Calibration of the cultivars

Seasons sown in 1994-2013 calibrate, 2014-2023 evaluate. For each cultivar:

1. the maturity group (0.05 steps) that best reproduces the observed flowering and maturity dates;
2. then `LFMAX`, `SFDUR` and `SDPDV` on a grid inside their training range, against the observed yields.

The inputs of every season were computed once (section 4); a candidate cultivar only changes the
cultivar columns, so each candidate costs one call of the network for all its seasons."""),
code("""cal = seasons["sowing"].dt.year <= 2013
d = emu.card["domain"]
grid_l = np.linspace(d["LFMAX"]["min"], d["LFMAX"]["max"], 6)
grid_s = np.linspace(d["SFDUR"]["min"], d["SFDUR"]["max"], 6)
grid_p = np.linspace(d["SDPDV"]["min"], d["SDPDV"]["max"], 6)
calibrated, curves = {}, {}
t0 = time.time(); n_eval = 0
for cv, g in seasons[cal].groupby("cultivar"):
    Xc = X.loc[g.index]
    mgs = np.round(np.arange(CATALOGUE[cv] - 1.5, CATALOGUE[cv] + 1.5001, 0.05), 2)
    P = emu.predict_inputs(pd.concat([Xc.assign(**emu.cultivar(mg=m)) for m in mgs], ignore_index=True)).outputs
    k = len(Xc)
    err = []
    for i in range(len(mgs)):
        e1 = P["ADAT_dap"].to_numpy()[i * k:(i + 1) * k] - g["obs_flowering"].to_numpy()
        e2 = P["MDAT_dap"].to_numpy()[i * k:(i + 1) * k] - g["obs_maturity"].to_numpy()
        err.append(np.sqrt(np.nanmean(np.concatenate([e1, e2]) ** 2)))
    mg = float(mgs[int(np.argmin(err))]); n_eval += len(mgs) * k
    combos = [(a, b, c) for a in grid_l for b in grid_s for c in grid_p]
    base = Xc.assign(**emu.cultivar(mg=mg))
    Y = emu.predict_inputs(pd.concat([base.assign(LFMAX=a, SFDUR=b, SDPDV=c) for a, b, c in combos],
                                     ignore_index=True)).outputs["HWAM"].to_numpy().reshape(len(combos), k)
    rmse = np.sqrt(np.nanmean((Y - g["obs_yield"].to_numpy()) ** 2, axis=1)); n_eval += len(combos) * k
    a, b, c = combos[int(np.argmin(rmse))]
    calibrated[cv] = emu.cultivar(mg=mg, LFMAX=a, SFDUR=b, SDPDV=c)
    curves[cv] = (mgs, np.array(err))
print(f"{n_eval:,} emulated seasons in {time.time() - t0:.1f} s")
cmp = pd.concat({"true (hidden)": pd.DataFrame(TRUE).T[["mg", "LFMAX", "SFDUR", "SDPDV"]],
                 "default": pd.DataFrame({c: emu.cultivar(mg=m) for c, m in CATALOGUE.items()}).T[["mg", "LFMAX", "SFDUR", "SDPDV"]],
                 "calibrated": pd.DataFrame(calibrated).T[["mg", "LFMAX", "SFDUR", "SDPDV"]]}, axis=1)
cmp.loc[sorted(calibrated)].round(2)"""),
code("""pred_c, X_c, _ = predict_all(emu, seasons, cultivars={**{c: emu.cultivar(mg=m) for c, m in CATALOGUE.items()}, **calibrated})
seasons[["yield_cal", "flowering_cal", "maturity_cal"]] = pred_c.to_numpy()
ev = seasons[~cal]
fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
ax = axes[0]
for i, (cv, (m, e)) in enumerate(curves.items()):
    ax.plot(m, e, color=SERIES[i], lw=2, label=cv); ax.axvline(calibrated[cv]["mg"], color=SERIES[i], ls=":", lw=1)
    ax.axvline(TRUE[cv]["mg"], color=SERIES[i], lw=3, alpha=0.25)
ax.set(xlabel="maturity group", ylabel="RMSE of the dates (days)", title="step 1 (dotted: chosen; thick: hidden truth)", ylim=(0, 15)); ax.legend()
for ax, (p, lab) in zip(axes[1:], [("yield", "default cultivar"), ("yield_cal", "calibrated cultivar")]):
    d = ev[["obs_yield", p]].dropna()
    ax.hexbin(d["obs_yield"], d[p], gridsize=40, cmap="Blues", mincnt=1, bins="log")
    lim = [0, d.max().max()]; ax.plot(lim, lim, color="0.3", lw=1)
    sc = scores(d["obs_yield"], d[p])
    ax.set(xlabel="observed yield 2014-2023 (kg/ha)", ylabel="emulated", title=f"evaluation, {lab}\\nRMSE {sc['RMSE']:.0f}, bias {sc['bias']:+.0f}")
fig.tight_layout(); plt.show()
pd.DataFrame({k: [scores(ev["obs_" + v], ev[v + s])["RMSE"] for v in ("yield", "flowering", "maturity")]
              for k, s in (("default", ""), ("calibrated", "_cal"))},
             index=["yield RMSE (kg/ha)", "flowering RMSE (d)", "maturity RMSE (d)"]).round(1)"""),
md("""The calibration recovers the hidden maturity group and moves the yield parameters towards the hidden
values; what remains is the noise added to the observations (field, farm-year and measurement
effects, ~300-400 kg/ha), which no cultivar can explain. With real data, part of the remaining error
is also the crop model itself."""),
md("""## 7. Using the calibrated cultivars

**Sowing window per farm**: every 5 days from 15 September to 31 December, 1994-2023, rainfed, with
the calibrated cultivar the farm grows most."""),
code("""main = seasons.groupby("site")["cultivar"].agg(lambda s: s.value_counts().index[0])
offsets = np.arange(0, 107, 5)
rows = []
t0 = time.time()
for farm, cv in main.items():
    s = sites.loc[farm]
    dates = [pd.Timestamp(f"{y}-09-15") + pd.Timedelta(days=int(o)) for y in YEARS for o in offsets]
    p = emu.predict(weather[farm], lat=s["lat"], elev=s["elev"], soil=soils[farm], sowing=dates, cultivar=calibrated[cv])
    rows.append(pd.DataFrame({"site": farm, "offset": [o for _ in YEARS for o in offsets], "yield": p.outputs["HWAM"].to_numpy()}))
win = pd.concat(rows)
print(f"{len(win)} seasons in {time.time() - t0:.1f} s")
med = win.groupby(["site", "offset"])["yield"].median().unstack()
p10 = win.groupby(["site", "offset"])["yield"].quantile(0.1).unstack()
labels = [(pd.Timestamp("2001-09-15") + pd.Timedelta(days=int(o))).strftime("%d %b") for o in offsets]
fig, axes = plt.subplots(1, 2, figsize=(15, 4.2))
for ax, (tab, title) in zip(axes, [(med, "median yield (kg/ha)"), (p10, "bad year: 10th percentile (kg/ha)")]):
    im = ax.imshow(tab.to_numpy(), aspect="auto", cmap="YlGn")
    ax.set_yticks(range(len(tab)), [f.split()[-1] for f in tab.index]); ax.set_xticks(range(0, len(offsets), 2), labels[::2])
    best = tab.to_numpy().argmax(axis=1)
    ax.scatter(best, range(len(tab)), marker="*", color="k", s=60)
    plt.colorbar(im, ax=ax); ax.set(title=f"{title}; star: best date"); ax.grid(False)
fig.tight_layout(); plt.show()
pd.DataFrame({"cultivar": main, "best date (median)": [labels[i] for i in med.to_numpy().argmax(axis=1)],
              "median there (kg/ha)": med.max(axis=1).round(0),
              "best date (bad years)": [labels[i] for i in p10.to_numpy().argmax(axis=1)]})"""),
md("""**Climate scenarios per farm** (as in training: warming added to Tmax and Tmin, CO₂), with each farm's
seasons as recorded:"""),
code("""scen = {"+2 °C": dict(dt=2.0), "+2 °C, 550 ppm": dict(dt=2.0, co2=550.0), "-15 % rain": dict(rain_factor=0.85)}
cultivars_cal = {**{c: emu.cultivar(mg=m) for c, m in CATALOGUE.items()}, **calibrated}
base = seasons.groupby("site")["yield_cal"].mean()
change = {}
for name, kw in scen.items():
    p, _, _ = predict_all(emu, seasons, cultivars=cultivars_cal, **kw)
    change[name] = 100 * (p["HWAM"].groupby(seasons["site"]).mean() / base - 1)
change = pd.DataFrame(change)
ax = change.rename(index=lambda f: f.split()[-1]).plot.bar(figsize=(11, 3.6), color=SERIES[:3], rot=0, width=0.8)
ax.axhline(0, color="0.4", lw=1); ax.set(ylabel="mean yield change (%)", xlabel="farm", title="climate scenarios, calibrated cultivars")
plt.tight_layout(); plt.show()
change.round(1)"""),
md("""## 8. The same data with the AquaCrop emulator

AquaCrop's cycle is a thermal time: for each cultivar it is the mean growing degrees between sowing
and the observed maturity of the calibration years (`cropemu.gdd_between`); the other crop
parameters keep the middle of their training range."""),
code("""aq = cropemu.load("aquacrop-soybean-v1")
gdd = {}
for cv, g in seasons[cal & seasons["obs_maturity"].notna()].groupby("cultivar"):
    gdd[cv] = np.mean([cropemu.gdd_between(weather[r.site], r.sowing, r.sowing + pd.Timedelta(days=int(r.obs_maturity)))
                       for r in g.itertuples()])
aq_cult = {cv: aq.cultivar(gdd_maturity=v) for cv, v in gdd.items()}
p_aq, _, _ = predict_all(aq, seasons, cultivars=aq_cult, family_out=("Y(dry)", "FLO_dap", "MAT_dap"))
seasons["yield_aq"] = p_aq["Y(dry)"].to_numpy() * 1000
seasons["maturity_aq"] = p_aq["MAT_dap"].to_numpy()
ev = seasons[~cal]
fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
f = seasons.groupby("site")[["obs_yield", "yield_cal", "yield_aq"]].mean().rename(index=lambda x: x.split()[-1])
f.plot.bar(ax=axes[0], color=["0.6", SERIES[0], SERIES[1]], rot=0, width=0.8)
axes[0].legend(["observed", "DSSAT emulator (calibrated)", "AquaCrop emulator (cycle from observations)"])
axes[0].set(ylabel="mean yield (kg/ha)", xlabel="farm", title="mean yield by farm")
d = ev[["obs_maturity", "maturity_aq"]].dropna()
axes[1].hexbin(d["obs_maturity"], d["maturity_aq"], gridsize=30, cmap="Oranges", mincnt=1, bins="log")
lim = [d.min().min(), d.max().max()]; axes[1].plot(lim, lim, color="0.3", lw=1)
sc = scores(d["obs_maturity"], d["maturity_aq"])
axes[1].set(xlabel="observed maturity 2014-2023 (DAS)", ylabel="AquaCrop emulator", title=f"maturity, RMSE {sc['RMSE']:.1f} d")
fig.tight_layout(); plt.show()"""),
md("""The observations were created with the DSSAT emulator, so the AquaCrop emulator is not expected to
match them: the comparison shows how two crop models read the same farms differently, not which
one is right."""),
md("""## 9. Export"""),
code("""out = Path("results"); out.mkdir(exist_ok=True)
seasons.assign(out_of_domain=ood.str.join(", ")).to_csv(out / "seasons_with_predictions.csv", index=False)
pd.DataFrame(calibrated).T.to_csv(out / "calibrated_cultivars.csv")
summary = seasons.groupby("site").agg(seasons=("sowing", "size"), obs_yield=("obs_yield", "mean"),
                                      yield_calibrated=("yield_cal", "mean"), yield_aquacrop=("yield_aq", "mean")).round(0)
summary.join(change.add_prefix("change % ").round(1)).to_csv(out / "farm_summary.csv")
print(sorted(p.name for p in out.iterdir()))
summary"""),
]

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3",
                                                                 "language": "python"}})
out = Path(sys.argv[1] if len(sys.argv) > 1 else "examples")
nbf.write(nb, out / "your_data.ipynb")
print(out / "your_data.ipynb")
