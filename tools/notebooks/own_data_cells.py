"""Section 11 of the model notebooks: your own data (station weather, measured soil, cultivars,
field trials, calibration), illustrated with published trials of the DSSAT example data."""
import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell


def cells(key):
    dssat = key == "dssat"
    trials_doc = """| trial | site | season | cultivars | treatments | observed |
|---|---|---|---|---|---|
| `UFGA7801` | Gainesville, Florida, USA (29.6° N) | 1978 | Bragg | irrigated, rainfed | yield, flowering, maturity |
| `IUAM8801`, `IUAM9001` | Ames, Iowa, USA (42.0° N) | 1988, 1990 | Williams-82, Elgin-87 | rainfed | yield, flowering, maturity |
| `PARA1801` | Paragominas, Pará, Brazil (3.4° S) | 2018 (calibration), 2019 (evaluation) | MG 7.7, MG 8.8 | 4 sowing dates, 10-40 plants/m², rainfed | yield, flowering, maturity |"""
    if dssat:
        trials_doc += """
| `LQBR1905` (Piracicaba only) | Piracicaba, São Paulo, Brazil (22.7° S) | 2017-2019 | M 7062 | rainfed, irrigated | yield |"""
    trial_list = '["UFGA7801", "IUAM8801", "IUAM9001", "PARA1801"' + (', "LQBR1905"]' if dssat else "]")

    out = [
md(f"""## 11. Your own data

Everything above used NASA POWER weather and SoilGrids soil, as in training. The library also runs
on **your own data**: a weather station, a measured soil profile, a cultivar calibrated for the
crop model, the treatments of a field trial. This section shows each step with published field
trials of the DSSAT example data ([dssat-csm-data](https://github.com/DSSAT/dssat-csm-data), files
downloaded from the public repository at a fixed commit, not redistributed here):

{trials_doc}

They are used **only to show how**: the same calls work with any station, profile or trial.

1. station weather: read, check, compare with NASA POWER, complete the missing days;
2. measured soil: read, compare with the water retention used in training, complete missing properties;
3. the cultivar of the trial and the training domain;
4. emulator vs. observations;
5. calibration with the emulator (thousands of seasons per second);
6. export the results."""),
code("""import os, urllib.request
from pathlib import Path
from cropemu.io import read_wth, read_sol, read_cul, read_experiment, read_observed
from cropemu.weather import check, fill_from
from cropemu.soil import fill_from as soil_fill_from
from cropemu.features import co2_at

DSSAT_DATA = "https://raw.githubusercontent.com/DSSAT/dssat-csm-data/99c95b340acb9515c2d0a8ab582f5fbbf076f345"
DSSAT_CUL = ("https://raw.githubusercontent.com/DSSAT/dssat-csm-os/25c93b9a2f73f8ec45bf441b198dac5fb7b22849"
             "/Data/Genotype/SBGRO048.CUL")
FILES = Path(os.environ.get("CROPEMU_CACHE", Path.home() / ".cache" / "cropemu")) / "dssat-example-data"

def get(rel, url=None):
    \"\"\"Download a file of the DSSAT example data once (cached) and return its local path.\"\"\"
    p = FILES / rel
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url or f"{DSSAT_DATA}/{rel}", p)
    return p

# sites of the trials: weather files, soil profile and coordinates
SITES = {
    "UFGA": dict(name="Gainesville", lat=29.63, lon=-82.37, elev=10, weather=["UFGA7801"],
                 soil=("SOIL", "IBSB910015")),
    "IUAM": dict(name="Ames", lat=42.00, lon=-93.50, elev=290, weather=["IUAM8801", "IUAM9001"],
                 soil=("SOIL", "IBSB910049")),
    "PARA": dict(name="Paragominas", lat=-3.383, lon=-47.417, elev=176, weather=["PARA1801", "PARA1901"],
                 soil=("BR", "BRPA080004")),
    "PIR2": dict(name="Piracicaba", lat=-22.725, lon=-47.648, elev=524,
                 weather=["PIR21701", "PIR21801", "PIR21901", "PIR22001"], soil=("BR", "BRNITOSSO3")),
}
TRIALS = """ + trial_list + """
for t in TRIALS:
    get(f"Soybean/{t}.SBX"); get(f"Soybean/{t}.SBA")
CUL = get("SBGRO048.CUL", DSSAT_CUL)
print(len([p for p in FILES.rglob("*") if p.is_file()]), "files of the DSSAT example data (downloaded once, cached)")"""),
md("""### 11.1 Station weather

`cropemu.io.read_wth` reads DSSAT weather files (one or several years) into the standard daily table:
`srad`, `tmax`, `tmin`, `rain` and, when the station has them, `dewp`, `rhum` and `wind` (converted
to m/s at 2 m). Missing humidity is handled day by day (dew point, else relative humidity, else
Tmin), and missing wind is taken as 2 m/s in the reference evapotranspiration (FAO-56).

Any other station works the same way: a `DataFrame` indexed by date with these column names, and
the site in `attrs`. `check` reports missing days (here, between the files of different years),
missing values and values out of range:

```python
w = pd.read_csv("my_station.csv", index_col="date", parse_dates=True)
w = w.rename(columns={"radiation": "srad", "t_max": "tmax", "t_min": "tmin", "precip": "rain"})
w.attrs = {"lat": -23.3, "lon": -51.2, "elev": 560}
```

Always check the header: in these files the longitude of the Piracicaba station is written as
+47.6 (east) instead of -47.6, which is why the coordinates of each site are set above."""),
code("""stations = {}
for sid, s in SITES.items():
    w = read_wth(*[get(f"Weather/{f}.WTH") for f in s["weather"]])
    if "wind" in w and (w["wind"].fillna(0) == 0).all():        # a column of zeros is a missing sensor
        w = w.drop(columns="wind")
    stations[sid] = w
    print(f"{s['name']:12s} {w.index.min():%Y-%m-%d} to {w.index.max():%Y-%m-%d}  columns: {list(w.columns)}  "
          f"file lat/lon: {w.attrs['lat']}, {w.attrs['lon']}  missing days: {check(w)['missing_days']}")"""),
md("""**Station vs. NASA POWER.** The emulator was trained with NASA POWER; a station is usually more
accurate locally, but check how much the two differ before mixing them. At Paragominas (2018-2019):"""),
code("""st = stations["PARA"]
power = fill_gaps(fetch(SITES["PARA"]["lat"], SITES["PARA"]["lon"], "2017-11-01", "2019-12-31"))
both = st[["srad", "tmax", "tmin", "rain"]].join(power[["srad", "tmax", "tmin", "rain"]], rsuffix="_power").dropna()
fig, axes = plt.subplots(1, 4, figsize=(14, 3.4))
for ax, (v, lab) in zip(axes, [("srad", "radiation (MJ/m²/d)"), ("tmax", "Tmax (°C)"), ("tmin", "Tmin (°C)"),
                               ("rain", "rain (mm/10 days)")]):
    a, b = both[v], both[v + "_power"]
    if v == "rain":                                   # daily rain is too noisy: 10-day totals
        a, b = a.resample("10D").sum(), b.resample("10D").sum()
    ax.scatter(a, b, s=8, alpha=0.5, color=SERIES[0], lw=0)
    lim = [min(a.min(), b.min()), max(a.max(), b.max())]
    ax.plot(lim, lim, color="0.4", lw=1)
    ax.set(xlabel="station", ylabel="NASA POWER", title=f"{lab}\\nbias {(b - a).mean():+.2f}, r {np.corrcoef(a, b)[0, 1]:.2f}")
fig.suptitle("Paragominas: station vs. NASA POWER on the same days", y=1.04)
fig.tight_layout(); plt.show()"""),
md("""**Completing the station.** A season needs weather from 30 days before sowing to at least 130 days
after (more for the AquaCrop thermal time). The Paragominas file starts on 1 January 2018, a week
before the first sowing: `fill_from` takes the missing days (and missing columns, such as humidity)
from NASA POWER and records how many values it took."""),
code("""def season_weather(sid, sowing, after=150):
    \"\"\"Station weather of a season, completed with NASA POWER where the station has no data.\"\"\"
    s, w = SITES[sid], stations[sid]
    start, end = pd.Timestamp(sowing) - pd.Timedelta(days=31), pd.Timestamp(sowing) + pd.Timedelta(days=after)
    if w.reindex(pd.date_range(start, end))[["srad", "tmax", "tmin", "rain"]].notna().all().all():
        return w
    if start.year < 1984:                               # NASA POWER starts in 1984
        raise ValueError(f"{s['name']}: the station does not cover {start:%Y-%m-%d} to {end:%Y-%m-%d}")
    return fill_from(w, fill_gaps(fetch(s["lat"], s["lon"], start.date(), end.date())))

w = season_weather("PARA", "2018-01-06")
print(w.attrs["filled_from"])
fig, ax = plt.subplots(figsize=(12, 2.6))
win = w.loc["2017-12-01":"2018-07-31"]
src = stations["PARA"].reindex(win.index)["tmax"].notna()
ax.bar(win.index, win["rain"], color=np.where(src, "#2a78d6", "#eb6834"), width=1)
ax.set(ylabel="rain (mm/d)", title="Paragominas 2018: station days (blue) and days taken from NASA POWER (orange)")
ax.axvline(pd.Timestamp("2018-01-06"), color="k", lw=1, ls="--")
fig.tight_layout(); plt.show()"""),
md("""### 11.2 Measured soil

`cropemu.io.read_sol` reads a profile of a DSSAT soil file with its **measured water limits**
(`ll`, `dul`, `sat`). The emulator uses them as they are; it only computes the water retention
(with the method used in training) when they are missing. Profiles deeper than 2 m are cut at
2 m, the depth of every training profile (`emu.training_soil`).

Missing properties can be taken from SoilGrids at the same point with `cropemu.soil.fill_from`:
the Ames profile has water limits but no texture or organic carbon (0 in the file)."""),
code("""soils = {}
for sid, s in SITES.items():
    f, pid = s["soil"]
    p = read_sol(get(f"Soil/{f}.SOL"), pid)
    p.loc[p["soc"] <= 0, "soc"] = np.nan                    # 0 % organic carbon: not measured
    if p[["clay", "sand", "soc", "bdod"]].isna().any().any():
        p = soil_fill_from(p, soilgrids.fetch(s["lat"], s["lon"]), ["clay", "sand", "silt", "soc", "bdod"])
        print(f"{s['name']}: taken from SoilGrids: {p.attrs['filled_from']}")
    soils[sid] = p
show = ["UFGA", "IUAM", "PARA", "PIR2"]
fig, axes = plt.subplots(1, 4, figsize=(14, 4), sharey=True)
rows = []
for ax, sid in zip(axes, show):
    m = soils[sid]
    ptf = hydraulics(m.drop(columns=["ll", "dul", "sat", "ksat"]), method=emu.card["hydraulics"], lat=SITES[sid]["lat"])
    mid = (m["top"] + m["bottom"]) / 2
    for col, colr in (("ll", "#e34948"), ("dul", "#2a78d6")):
        ax.plot(m[col], mid, color=colr, lw=2, marker="o", ms=3, label=f"{col} measured")
        ax.plot(ptf[col], mid, color=colr, lw=1.5, ls="--", label=f"{col} {emu.card['hydraulics']} PTF")
    ax.invert_yaxis() if sid == show[0] else None
    paw = lambda d: float(((d["dul"] - d["ll"]) * (d["bottom"].clip(upper=200) - d["top"]).clip(lower=0) * 10).sum())
    rows.append({"site": SITES[sid]["name"], "profile": m.attrs["name"], "clay 0-30 cm (%)": m.loc[m["top"] < 30, "clay"].mean(),
                 "PAW measured (mm)": paw(m), "PAW from PTF (mm)": paw(ptf)})
    ax.set(title=f"{SITES[sid]['name']}: {m.attrs['name'].split('!')[0][:24].title()}", xlabel="water content (cm³/cm³)")
axes[0].set_ylabel("depth (cm)"); axes[0].legend(fontsize=7, loc="lower left")
fig.suptitle("measured water limits (solid) vs. the pedotransfer function used in training (dashed)", y=1.02)
fig.tight_layout(); plt.show()
pd.DataFrame(rows).set_index("site").round(1)"""),
md("""The measured and estimated limits can differ a lot (e.g. the sandy Millhopper profile of
Gainesville, or the very clayey Oxisol of Paragominas). Use the measured profile when you have it;
the emulator then shows if the soil falls outside the training data (`out_of_domain`)."""),
    ]

    if dssat:
        out += [
md("""### 11.3 The cultivar of the trial

`cropemu.io.read_cul` reads the coefficients of a DSSAT cultivar, and `emu.cultivar_from_dssat`
turns them into the emulator cultivar. The emulator also takes the maturity group (MG): taken from
the cultivar name when it states it (MG77PA, MG88PA), otherwise estimated from the critical day
length CSDL (`emu.mg_from_csdl`, the inverse of the default coefficients).

**Training domain.** The emulator was trained with coefficients varying around the defaults of each
MG. Cultivars calibrated in a study often fall outside that range; `emu.cultivar_domain` shows where
each coefficient sits (0 = training minimum, 1 = maximum)."""),
code("""MG_IN_NAME = {"RB0002": 7.7, "RB0003": 8.8}            # MG77PA and MG88PA
def load_trial(t):
    # treatments (only those at the sites above) and observations of a trial
    x = read_experiment(FILES / f"Soybean/{t}.SBX")
    return x[x["WSTA"].isin(SITES)], read_observed(FILES / f"Soybean/{t}.SBA")

trials = {t: load_trial(t) for t in TRIALS}
cultivars = {}
for t, (x, _) in trials.items():
    for ing, name in x[["INGENO", "CNAME"]].drop_duplicates().itertuples(index=False):
        coef = read_cul(CUL, ing)
        cultivars[name.strip()] = emu.cultivar_from_dssat(coef, mg=MG_IN_NAME.get(ing))
dom = pd.concat({n: emu.cultivar_domain(c) for n, c in cultivars.items()}, names=["cultivar"])
pos = dom["position"].unstack()
fig, ax = plt.subplots(figsize=(12, 3.4))
for i, (name, r) in enumerate(pos.iterrows()):
    x = np.arange(len(r))
    ax.scatter(x + (i - len(pos) / 2) * 0.08, r.clip(-0.6, 1.6), s=28, label=name,
               marker="o" if r.between(0, 1).all() else "X")
ax.axhspan(0, 1, color="0.92", zorder=0)
ax.set_xticks(np.arange(pos.shape[1]), pos.columns, rotation=0)
ax.set(ylabel="position in training range", ylim=(-0.7, 1.7),
       title="cultivar coefficients of the trials in the training range (grey band); X: some coefficient outside")
ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.12))
fig.tight_layout(); plt.show()
dom[dom["status"] != "ok"][["value", "min", "max", "status"]].round(3)"""),
        ]
    else:
        out += [
md("""### 11.3 The cultivar of the trial

AquaCrop's soybean cycle is a thermal time. With an observed sowing and maturity date, the
`gdd_maturity` of the cultivar is the growing degrees between them at the station
(`cropemu.gdd_between`, Tbase 5 °C, Tupper 30 °C); the other parameters keep the middle of their
training range. For a forecast (the maturity is not known yet), use the mean `gdd_maturity` of the
past seasons of the same cultivar, as in the calibration below."""),
code("""def load_trial(t):
    # treatments (only those at the sites above) and observations of a trial
    x = read_experiment(FILES / f"Soybean/{t}.SBX")
    return x[x["WSTA"].isin(SITES)], read_observed(FILES / f"Soybean/{t}.SBA")

trials = {t: load_trial(t) for t in TRIALS}
rows = []
for t, (x, obs) in trials.items():
    for trno, r in x.iterrows():
        mat = obs.loc[trno, "MDAT"] if trno in obs.index and "MDAT" in obs else pd.NaT
        if pd.notna(mat):
            w = season_weather(r["WSTA"], r["sowing"])
            rows.append({"trial": t, "cultivar": r["CNAME"].strip(), "sowing": r["sowing"],
                         "maturity (DAS)": (mat - r["sowing"]).days,
                         "gdd_maturity": cropemu.gdd_between(w, r["sowing"], mat)})
gdd_obs = pd.DataFrame(rows).drop_duplicates(["trial", "cultivar", "sowing"])
lo, hi = emu.card["domain"]["gdd_maturity"]["min"], emu.card["domain"]["gdd_maturity"]["max"]
print(f"training range of gdd_maturity: {lo:.0f}-{hi:.0f} °C·d")
gdd_obs.round(0)"""),
        ]

    # ---------------------------------------------------------------- 11.4 trials
    if dssat:
        cult_line = 'cv = cultivars[r["CNAME"].strip()]'
        pred_cols = '"yield": p.outputs["HWAM"].iloc[0], "anthesis": p.outputs["ADAT_dap"].iloc[0], "maturity": p.outputs["MDAT_dap"].iloc[0]'
        obs_cols = '"obs_yield": o.get("HWAM", np.nan), "obs_anthesis": das(o.get("ADAT")), "obs_maturity": das(o.get("MDAT"))'
        ylab, yunit, yscale = "yield (kg/ha)", "kg/ha", 1
        pheno = [("anthesis", "anthesis (DAS)"), ("maturity", "maturity (DAS)")]
    else:
        cult_line = ('mat = o.get("MDAT", pd.NaT)\n'
                     '        if pd.isna(mat):\n'
                     '            continue\n'
                     '        cv = emu.cultivar(gdd_maturity=cropemu.gdd_between(w, r["sowing"], mat))')
        pred_cols = '"yield": p.outputs["Y(dry)"].iloc[0] * 1000, "anthesis": p.outputs["FLO_dap"].iloc[0], "maturity": p.outputs["MAT_dap"].iloc[0]'
        obs_cols = '"obs_yield": o.get("HWAM", np.nan), "obs_anthesis": das(o.get("ADAT")), "obs_maturity": das(o.get("MDAT"))'
        ylab, yunit, yscale = "yield (kg/ha, dry)", "kg/ha", 1
        pheno = [("anthesis", "flowering (DAS)"), ("maturity", "maturity (DAS)")]

    out += [
md(f"""### 11.4 Emulator vs. observations

Every treatment is predicted with its station weather (completed with NASA POWER), its measured
soil, its cultivar, its sowing date and its water regime (`irrigated=True` means no water stress:
the trials with limited irrigation are not exactly that). CO₂ follows the Mauna Loa record, with
the 1978 value (335 ppm) raised to the training minimum (345 ppm).

What the emulator does **not** know: plant density and row spacing (fixed at 30 plants/m² and
50 cm in training), nitrogen, pests and diseases. The comparison mixes the error of the emulator
(validation: {"~450 kg/ha and ~3 days" if dssat else "~0.6 t/ha and ~4 days"}) with the error of the crop model itself, which was not
calibrated for these sites."""),
code(f"""CO2_MIN = emu.card["domain"]["co2"]["min"]
das = lambda d: np.nan if d is None or pd.isna(d) else (d - r["sowing"]).days
rows = []
for t, (x, obs) in trials.items():
    for trno, r in x.iterrows():
        sid, o = r["WSTA"], (obs.loc[trno] if trno in obs.index else pd.Series(dtype=float))
        s = SITES[sid]
        w = season_weather(sid, r["sowing"])
        {cult_line}
        co2 = max(co2_at(r["sowing"] + pd.Timedelta(days=60)), CO2_MIN)
        p = emu.predict(w, lat=s["lat"], elev=s["elev"], soil=soils[sid], sowing=r["sowing"], cultivar=cv,
                        irrigated=r["irrigated"], co2=co2)
        rows.append({{"trial": t, "trno": trno, "site": s["name"], "cultivar": r["CNAME"].strip(),
                     "sowing": r["sowing"], "plants_m2": r["plants_m2"], "irrigated": r["irrigated"],
                     {obs_cols}, {pred_cols},
                     "out_of_domain": ", ".join(p.out_of_domain.iloc[0])}})
field = pd.DataFrame(rows)
field.head(8).round(1)"""),
code(f"""def scores(d, a, b):
    d = d[[a, b]].dropna()
    e = d[b] - d[a]
    return pd.Series({{"n": len(d), "RMSE": np.sqrt((e ** 2).mean()), "bias": e.mean(),
                      "r": d[a].corr(d[b]) if len(d) > 2 else np.nan}})

fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
groups = list(field.groupby("trial"))
for ax, (v, lab) in zip(axes, [("yield", {ylab!r})] + {pheno!r}):
    for i, (t, d) in enumerate(groups):
        d = d.dropna(subset=["obs_" + v])
        ood = d["out_of_domain"] != ""
        ax.scatter(d.loc[~ood, "obs_" + v], d.loc[~ood, v], color=SERIES[i], s=36, label=t)
        ax.scatter(d.loc[ood, "obs_" + v], d.loc[ood, v], facecolor="none", edgecolor=SERIES[i], s=36, lw=1.4)
    lim = np.nanpercentile(field[["obs_" + v, v]].to_numpy(float), [0, 100])
    lim = [lim[0] * 0.9, lim[1] * 1.05]
    ax.plot(lim, lim, color="0.4", lw=1); ax.set(xlim=lim, ylim=lim)
    sc = scores(field, "obs_" + v, v)
    ax.set(xlabel="observed", ylabel="emulated", title=f"{{lab}}\\nRMSE {{sc['RMSE']:.0f}}, bias {{sc['bias']:+.0f}}, n {{sc['n']:.0f}}")
axes[0].legend(loc="upper left")
fig.suptitle("emulator vs. field observations (hollow: some input out of the training domain)", y=1.03)
fig.tight_layout(); plt.show()
pd.concat({{v: field.groupby("trial")[["obs_" + v, v]].apply(lambda d, v=v: scores(d, "obs_" + v, v))
           for v in ("yield", "anthesis", "maturity")}}, axis=1).round(1)"""),
md("""**Plant density.** At Paragominas the observed yield rises with density, from 10 to 40 plants/m²; the
emulator, trained at 30 plants/m², gives one value per sowing date and cultivar:"""),
code("""d = field[field["trial"] == "PARA1801"]
fig, ax = plt.subplots(figsize=(9, 3.6))
for i, ((cv, sow), g) in enumerate(d.groupby(["cultivar", "sowing"])):
    g = g.sort_values("plants_m2")
    ax.plot(g["plants_m2"], g["obs_yield"], marker="o", color=SERIES[i % len(SERIES)], label=f"{cv[:6]} {sow:%d %b %Y}")
    ax.axhline(g["yield"].iloc[0], color=SERIES[i % len(SERIES)], lw=1, ls=":")
ax.axvline(30, color="0.5", lw=1)
ax.set(xlabel="plants/m²", ylabel="yield (kg/ha)", title="observed (lines) vs. emulated at the training density of 30 plants/m² (dotted)")
ax.legend(ncol=2, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
fig.tight_layout(); plt.show()"""),
    ]

    out += [md("""**Reading the comparison.** """ + ("""The dates are close to the observations (anthesis within a
few days); the yields scatter more, as expected from a crop model that was not calibrated for these
sites and from what the emulator does not see (density, nitrogen, diseases, the exact irrigation).
The hollow points warn where the inputs left the training data: the sandy soil of Gainesville and
the calibrated cultivars of the studies. Their predictions are extrapolations."""
        if dssat else """The maturity dates are close because the cycle (`gdd_maturity`)
was taken from the observed maturity. Flowering is later than observed: AquaCrop's soybean places the
start of flowering at a fixed share of the cycle, which is not the R1 stage of the field notes. The
yields of the default AquaCrop soybean are lower than observed at Paragominas and collapse in the 1988
drought at Ames: the crop parameters were not calibrated for these sites (next step).""")),
    ]

    # ---------------------------------------------------------------- 11.5 calibration
    if dssat:
        out += [
md("""### 11.5 Calibration with the emulator

The Paragominas trial was designed for calibration (2018) and evaluation (2019). The calibrated
cultivars of the study fall outside the training domain (11.3), so here the cultivar is calibrated
**inside** it, starting from the default cultivar of a maturity group:

1. the MG (0.05 steps) that best reproduces the observed anthesis and maturity dates of 2018;
2. then the maximum leaf photosynthesis `LFMAX` and the seed filling duration `SFDUR` (a grid
   inside their training range) that best reproduce the 2018 yields (densities 20-40 plants/m²);
3. evaluation on 2019, which the calibration never saw.

The inputs of every season are computed once (`emu.inputs`); trying a cultivar only changes the
cultivar columns and runs the network (`emu.predict_inputs`), so a grid of thousands of cultivars ×
seasons takes a fraction of a second.

When the best value lies on the edge of the training range, the observations ask for parameters the
emulator never saw: the calibration stops there, and going further needs the crop model itself."""),
code("""para = field[(field["trial"] == "PARA1801") & (field["plants_m2"] >= 20)].copy()
para["year"] = para["sowing"].dt.year
s = SITES["PARA"]

def season_table(rows, cultivar):
    \"\"\"Emulator inputs of each season (one row per treatment) for a starting cultivar.\"\"\"
    X = [emu.inputs(season_weather("PARA", r.sowing), lat=s["lat"], elev=s["elev"], soil=soils["PARA"],
                    sowing=r.sowing, cultivar=cultivar) for r in rows.itertuples()]
    return pd.concat(X, ignore_index=True)

t0 = time.time()
calib = {}
for cv in ("MG77PA (13)", "MG88PA (13)"):
    cal, val = para[(para["cultivar"] == cv) & (para["year"] == 2018)], para[(para["cultivar"] == cv) & (para["year"] == 2019)]
    Xc, Xv = season_table(cal, emu.cultivar(mg=8)), season_table(val, emu.cultivar(mg=8))
    # step 1: MG from the dates
    mgs = np.round(np.arange(5.0, 10.0001, 0.05), 2)
    big = pd.concat([Xc.assign(**emu.cultivar(mg=m)) for m in mgs], ignore_index=True)
    P = emu.predict_inputs(big).outputs
    err = ((P["ADAT_dap"].to_numpy() - np.tile(cal["obs_anthesis"].to_numpy(), len(mgs))) ** 2 +
           (P["MDAT_dap"].to_numpy() - np.tile(cal["obs_maturity"].to_numpy(), len(mgs))) ** 2).reshape(len(mgs), -1)
    rmse_mg = np.sqrt(err.mean(axis=1) / 2)
    mg = float(mgs[rmse_mg.argmin()])
    # step 2: LFMAX x SFDUR from the yields
    d = emu.card["domain"]
    grid = [(a, b) for a in np.linspace(d["LFMAX"]["min"], d["LFMAX"]["max"], 15)
            for b in np.linspace(d["SFDUR"]["min"], d["SFDUR"]["max"], 15)]
    big = pd.concat([Xc.assign(**emu.cultivar(mg=mg, LFMAX=a, SFDUR=b)) for a, b in grid], ignore_index=True)
    Y = emu.predict_inputs(big).outputs["HWAM"].to_numpy().reshape(len(grid), -1)
    rmse_y = np.sqrt(((Y - cal["obs_yield"].to_numpy()) ** 2).mean(axis=1))
    a, b = grid[int(rmse_y.argmin())]
    best = emu.cultivar(mg=mg, LFMAX=a, SFDUR=b)
    calib[cv] = dict(cultivar=best, rmse_mg=rmse_mg, mgs=mgs, rmse_y=rmse_y.reshape(15, 15), grid=grid,
                     val=val.assign(**{k + "_cal": v for k, v in emu.predict_inputs(Xv.assign(**best)).outputs[
                         ["HWAM", "ADAT_dap", "MDAT_dap"]].set_axis(val.index).items()}),
                     n=len(big) + len(mgs) * len(Xc))
    print(f"{cv}: MG {mg:.2f}, LFMAX {a:.3f}, SFDUR {b:.2f}  ({calib[cv]['n']} emulated seasons)")
print(f"calibration time: {time.time() - t0:.1f} s (including the inputs from daily weather)")"""),
code("""fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
ax = axes[0]
for i, (cv, c) in enumerate(calib.items()):
    ax.plot(c["mgs"], c["rmse_mg"], color=SERIES[i], lw=2, label=cv)
    ax.axvline(c["cultivar"]["mg"], color=SERIES[i], lw=1, ls=":")
ax.set(xlabel="maturity group", ylabel="RMSE of anthesis and maturity (days)", title="step 1: MG from the 2018 dates", ylim=(0, 30))
ax.legend()
ax = axes[1]
c = calib["MG77PA (13)"]
lf = np.unique([g[0] for g in c["grid"]]); sf = np.unique([g[1] for g in c["grid"]])
im = ax.pcolormesh(sf, lf, c["rmse_y"], cmap="viridis_r", shading="nearest")
ax.scatter([c["cultivar"]["SFDUR"]], [c["cultivar"]["LFMAX"]], marker="*", s=150, color="w", edgecolor="k")
plt.colorbar(im, ax=ax, label="RMSE of yield (kg/ha)")
ax.set(xlabel="SFDUR", ylabel="LFMAX", title="step 2 (MG77PA): yield RMSE on the 2018 grid")
ax = axes[2]
for i, (cv, c) in enumerate(calib.items()):
    v = c["val"]
    ax.scatter(v["obs_yield"], v["yield"], color=SERIES[i], marker="x", s=40, label=f"{cv[:6]} study cultivar")
    ax.scatter(v["obs_yield"], v["HWAM_cal"], color=SERIES[i], s=40, label=f"{cv[:6]} calibrated in domain")
lim = [1500, 6000]; ax.plot(lim, lim, color="0.4", lw=1); ax.set(xlim=lim, ylim=lim)
ax.set(xlabel="observed yield 2019 (kg/ha)", ylabel="emulated", title="evaluation: 2019 (not used in the calibration)")
ax.legend(fontsize=7)
fig.tight_layout(); plt.show()

ev = pd.concat([c["val"].assign(cv=cv) for cv, c in calib.items()])
pd.DataFrame({
    "study cultivar (out of domain)": [scores(ev, "obs_yield", "yield")["RMSE"], scores(ev, "obs_anthesis", "anthesis")["RMSE"],
                                       scores(ev, "obs_maturity", "maturity")["RMSE"]],
    "calibrated inside the domain": [scores(ev, "obs_yield", "HWAM_cal")["RMSE"], scores(ev, "obs_anthesis", "ADAT_dap_cal")["RMSE"],
                                     scores(ev, "obs_maturity", "MDAT_dap_cal")["RMSE"]]},
    index=["yield RMSE (kg/ha)", "anthesis RMSE (d)", "maturity RMSE (d)"]).round(1)"""),
        ]
    else:
        out += [
md("""### 11.5 Calibration with the emulator

The Paragominas trial was designed for calibration (2018) and evaluation (2019). In a forecast the
maturity date is not known, so the calibration keeps one set of parameters per cultivar:

1. `gdd_maturity`: the mean of the 2018 seasons of the cultivar (11.3);
2. the reference harvest index `hio` and the water productivity `wp` (a grid inside their training
   range) that best reproduce the 2018 yields (densities 20-40 plants/m²);
3. evaluation on 2019, which the calibration never saw (maturity and yield).

When the best value lies on the edge of the training range (as here: both parameters end at their
maximum), the observations ask for parameters the emulator never saw: the calibration stops there,
and going further needs the crop model itself.

The inputs of every season are computed once (`emu.inputs`); trying a parameter set only changes
the cultivar columns and runs the network (`emu.predict_inputs`). `gdd_maturity` also changes the
thermal-time inputs, so the seasons are rebuilt once with the calibrated cycle."""),
code("""para = field[(field["trial"] == "PARA1801") & (field["plants_m2"] >= 20)].copy()
para["year"] = para["sowing"].dt.year
s = SITES["PARA"]

def season_table(rows, cultivar):
    \"\"\"Emulator inputs of each season (one row per treatment) for a cultivar.\"\"\"
    X = [emu.inputs(season_weather("PARA", r.sowing), lat=s["lat"], elev=s["elev"], soil=soils["PARA"],
                    sowing=r.sowing, cultivar=cultivar) for r in rows.itertuples()]
    return pd.concat(X, ignore_index=True)

t0 = time.time()
calib = {}
d = emu.card["domain"]
for cv in ("MG77PA (13)", "MG88PA (13)"):
    cal, val = para[(para["cultivar"] == cv) & (para["year"] == 2018)], para[(para["cultivar"] == cv) & (para["year"] == 2019)]
    g = gdd_obs[(gdd_obs["cultivar"] == cv) & (gdd_obs["sowing"].dt.year == 2018)]["gdd_maturity"].mean()
    base = emu.cultivar(gdd_maturity=g)
    Xc, Xv = season_table(cal, base), season_table(val, base)
    grid = [(a, b) for a in np.linspace(d["hio"]["min"], d["hio"]["max"], 15)
            for b in np.linspace(d["wp"]["min"], d["wp"]["max"], 15)]
    big = pd.concat([Xc.assign(hio=a, wp=b) for a, b in grid], ignore_index=True)
    Y = emu.predict_inputs(big).outputs["Y(dry)"].to_numpy().reshape(len(grid), -1) * 1000
    rmse_y = np.sqrt(((Y - cal["obs_yield"].to_numpy()) ** 2).mean(axis=1))
    a, b = grid[int(rmse_y.argmin())]
    best = {**base, "hio": a, "wp": b}
    P = emu.predict_inputs(Xv.assign(hio=a, wp=b)).outputs
    calib[cv] = dict(cultivar=best, rmse_y=rmse_y.reshape(15, 15), grid=grid, n=len(big),
                     val=val.assign(yield_cal=P["Y(dry)"].to_numpy() * 1000, maturity_cal=P["MAT_dap"].to_numpy(),
                                    anthesis_cal=P["FLO_dap"].to_numpy()))
    print(f"{cv}: gdd_maturity {g:.0f} °C·d, hio {a:.1f} %, wp {b:.2f} g/m²  ({len(big)} emulated seasons)")
print(f"calibration time: {time.time() - t0:.1f} s (including the inputs from daily weather)")"""),
code("""fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
c = calib["MG77PA (13)"]
hi_ = np.unique([g[0] for g in c["grid"]]); wp_ = np.unique([g[1] for g in c["grid"]])
ax = axes[0]
im = ax.pcolormesh(wp_, hi_, c["rmse_y"], cmap="viridis_r", shading="nearest")
ax.scatter([c["cultivar"]["wp"]], [c["cultivar"]["hio"]], marker="*", s=150, color="w", edgecolor="k")
plt.colorbar(im, ax=ax, label="RMSE of yield (kg/ha)")
ax.set(xlabel="wp (g/m²)", ylabel="hio (%)", title="MG77PA: yield RMSE on the 2018 grid")
ax = axes[1]
for i, (cv, c) in enumerate(calib.items()):
    v = c["val"]
    ax.scatter(v["obs_maturity"], v["maturity"], color=SERIES[i], marker="x", s=40, label=f"{cv[:6]} observed cycle")
    ax.scatter(v["obs_maturity"], v["maturity_cal"], color=SERIES[i], s=40, label=f"{cv[:6]} cycle of 2018")
lim = [80, 105]; ax.plot(lim, lim, color="0.4", lw=1); ax.set(xlim=lim, ylim=lim)
ax.set(xlabel="observed maturity 2019 (DAS)", ylabel="emulated", title="evaluation: maturity 2019"); ax.legend(fontsize=7)
ax = axes[2]
for i, (cv, c) in enumerate(calib.items()):
    v = c["val"]
    ax.scatter(v["obs_yield"], v["yield"], color=SERIES[i], marker="x", s=40, label=f"{cv[:6]} default parameters")
    ax.scatter(v["obs_yield"], v["yield_cal"], color=SERIES[i], s=40, label=f"{cv[:6]} calibrated")
lim = [1500, 6000]; ax.plot(lim, lim, color="0.4", lw=1); ax.set(xlim=lim, ylim=lim)
ax.set(xlabel="observed yield 2019 (kg/ha)", ylabel="emulated (dry)", title="evaluation: yield 2019"); ax.legend(fontsize=7)
fig.tight_layout(); plt.show()

ev = pd.concat([c["val"].assign(cv=cv) for cv, c in calib.items()])
pd.DataFrame({
    "default parameters, observed cycle": [scores(ev, "obs_yield", "yield")["RMSE"], scores(ev, "obs_maturity", "maturity")["RMSE"]],
    "calibrated on 2018": [scores(ev, "obs_yield", "yield_cal")["RMSE"], scores(ev, "obs_maturity", "maturity_cal")["RMSE"]]},
    index=["yield RMSE (kg/ha)", "maturity RMSE (d)"]).round(1)"""),
        ]

    out += [
md("""### 11.6 Export the results

Predictions are `pandas` tables: save them with `to_csv` (or `to_excel` with `openpyxl`,
`to_parquet` with `pyarrow`). Keep the inputs and the domain flags with them."""),
code("""out_dir = Path("results"); out_dir.mkdir(exist_ok=True)
field.to_csv(out_dir / f"field_trials_{emu.card['name']}.csv", index=False)
pd.DataFrame({cv: c["cultivar"] for cv, c in calib.items()}).to_csv(out_dir / f"calibrated_cultivars_{emu.card['name']}.csv")
print(sorted(p.name for p in out_dir.iterdir()))"""),
    ]
    return out
