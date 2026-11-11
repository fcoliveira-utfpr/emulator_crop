"""Synthetic example data of examples/your_data.ipynb: 8 fictitious farms in the Brazilian soybean
belt, 1993-2024 (sites, daily weather, soil profiles, 4,800 seasons with observations).

Only to illustrate the workflow. The weather comes from a simple stochastic generator; the
"observations" come from the DSSAT emulator itself with hidden "true" cultivars (saved in
hidden_cultivars.csv) plus field, farm-year and measurement noise.

    python examples/data/make_example_data.py          # writes examples/data/your_data/
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import cropemu
from cropemu.io import read_soils, read_weather
from cropemu.weather.eto import extraterrestrial_radiation

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "your_data"
rng = np.random.default_rng(2024)

FARMS = pd.DataFrame([
    # farm,        lat,    lon,  elev, clay %, sowing window starts
    ("Fazenda A", -12.6, -56.0, 380, 38, "10-01"),
    ("Fazenda B", -15.6, -54.3, 600, 48, "10-05"),
    ("Fazenda C", -17.8, -51.0, 750, 55, "10-10"),
    ("Fazenda D", -20.5, -54.8, 480, 26, "10-10"),
    ("Fazenda E", -23.3, -51.2, 600, 65, "10-01"),
    ("Fazenda F", -24.9, -53.4, 700, 70, "09-25"),
    ("Fazenda G", -28.3, -52.4, 680, 45, "10-20"),
    ("Fazenda H", -29.7, -55.5, 120, 20, "11-01"),
], columns=["fazenda", "lat", "lon", "elev", "clay", "window"])
CATALOGUE = {"Cultivar 5.5": 5.5, "Cultivar 6.4": 6.4, "Cultivar 7.4": 7.4, "Cultivar 8.3": 8.3}
YEARS = range(1994, 2024)                           # sowing years (harvest the year after)


def generate_weather(lat, elev, start="1993-01-01", end="2024-12-31"):
    """Daily weather from a simple, coherent stochastic generator.

    Rain: two-state Markov chain (wet days persist) with a seasonal wet-day probability and amount
    (dry winter in the tropics, rain spread over the year in the south), gamma amounts.
    Temperature: annual mean falling with latitude and elevation, seasonal cycle growing with
    latitude, persistent AR(1) anomalies, cooler wet days with a smaller daily range.
    Radiation: a fraction of the extraterrestrial radiation, lower on wet days. Humidity: higher
    on wet days and in the rainy season. Wind: around 2 m/s.
    """
    idx = pd.date_range(start, end)
    doy, n, a = idx.dayofyear.to_numpy(), len(idx), abs(lat)
    summer = np.cos(2 * np.pi * (doy - (15 if lat < 0 else 196)) / 365.25)        # +1 mid-summer
    tropical = np.clip((30 - a) / 15, 0, 1)                                        # 1 below 15°, 0 above 30°
    p_wet = np.clip(0.33 + 0.27 * tropical * summer, 0.03, 0.75)
    p11 = np.clip(p_wet + 0.25, 0, 0.95)                                           # persistence
    p01 = p_wet * (1 - p11) / (1 - p_wet)
    wet = np.zeros(n, bool)
    u = rng.random(n)
    for i in range(1, n):
        wet[i] = u[i] < (p11[i] if wet[i - 1] else p01[i])
    mean_amount = 11 + 5 * tropical * summer
    rain = np.where(wet, rng.gamma(0.75, mean_amount / 0.75), 0.0)
    anom = np.zeros(n)
    e = rng.normal(0, 1.4, n)
    for i in range(1, n):
        anom[i] = 0.75 * anom[i - 1] + e[i]
    tmean = 27.5 - 0.28 * max(a - 10, 0) - 0.0055 * elev + (0.6 + 0.25 * max(a - 10, 0)) * summer + anom - 0.8 * wet
    dtr = np.where(wet, 7.0, 11.0 + 2.5 * (1 - tropical * np.clip(summer, 0, 1))) + rng.normal(0, 1, n)
    ra = extraterrestrial_radiation(lat, doy)
    kt = np.clip(np.where(wet, 0.40, 0.62) + rng.normal(0, 0.06, n), 0.15, 0.78)
    rh = np.clip(np.where(wet, 86, 62 + 12 * tropical * summer - 8 * tropical * (summer < 0)) + rng.normal(0, 5, n), 25, 99)
    return pd.DataFrame({"data": idx.strftime("%Y-%m-%d"), "radiacao (MJ/m2/d)": np.round(kt * ra, 1),
                         "tmax (C)": np.round(tmean + dtr / 2, 1), "tmin (C)": np.round(tmean - dtr / 2, 1),
                         "chuva (mm)": np.round(rain, 1), "umidade (%)": np.round(rh, 0),
                         "vento (m/s)": np.round(rng.gamma(4, 0.5, n), 1)})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FARMS[["fazenda", "lat", "lon", "elev"]].rename(columns={"elev": "altitude (m)"}).to_csv(OUT / "locais.csv", index=False)

    # weather; farm H as a station logger: radiation in W/m², dates day first, ';' and decimal ','
    for f in FARMS.itertuples():
        w = generate_weather(f.lat, f.elev)
        name = OUT / f"clima_{f.fazenda.split()[-1]}.csv"
        if f.fazenda == "Fazenda H":
            w["radiacao (MJ/m2/d)"] = np.round(w["radiacao (MJ/m2/d)"] / 0.0864, 0)
            w = w.rename(columns={"radiacao (MJ/m2/d)": "radiacao (W/m2)"})
            w["data"] = pd.to_datetime(w["data"]).dt.strftime("%d/%m/%Y")
            w.to_csv(name, index=False, sep=";", decimal=",")
        else:
            w.to_csv(name, index=False)

    # soil: clay increasing and carbon decreasing with depth; farm E with laboratory water limits
    rows = []
    for f in FARMS.itertuples():
        for k, (top, bot) in enumerate([(0, 20), (20, 40), (40, 60), (60, 100), (100, 200)]):
            clay = min(f.clay + 4 * k + rng.normal(0, 2), 80)
            sand = max(100 - clay - (18 + rng.normal(0, 3)), 3) if f.clay > 30 else 100 - clay - 12
            soc = max(1.9 * np.exp(-k / 1.6) * (0.8 + f.clay / 150) + rng.normal(0, 0.05), 0.2)
            bd = 1.55 - 0.004 * clay + 0.03 * k + rng.normal(0, 0.02)
            row = {"perfil": f.fazenda, "topo (cm)": top, "base (cm)": bot, "argila (%)": round(clay, 1),
                   "areia (%)": round(sand, 1), "silte (%)": round(100 - clay - sand, 1),
                   "carbono (%)": round(soc, 2), "densidade (g/cm3)": round(bd, 2),
                   "pmp (cm3/cm3)": None, "cc (cm3/cm3)": None}
            if f.fazenda == "Fazenda E":
                row["pmp (cm3/cm3)"], row["cc (cm3/cm3)"] = round(0.27 + 0.01 * k, 3), round(0.40 + 0.005 * k, 3)
            rows.append(row)
    pd.DataFrame(rows).to_csv(OUT / "solo.csv", index=False)

    # seasons: two cultivars per farm (closest to the typical MG of its latitude), 20 fields
    emu = cropemu.load("dssat-soybean-v1")
    true = {name: emu.cultivar(mg=mg + 0.4, LFMAX=1.10, SFDUR=24.5, SDPDV=2.2) for name, mg in CATALOGUE.items()}
    pd.DataFrame(true).T.rename_axis("cultivar").to_csv(OUT / "hidden_cultivars.csv")
    rows = []
    for f in FARMS.itertuples():
        typ = emu.typical_mg(f.lat)
        names = sorted(CATALOGUE, key=lambda c: abs(CATALOGUE[c] - typ))[:2]
        for field in range(1, 21):
            for y in YEARS:
                rows.append({"fazenda": f.fazenda, "talhao": f"T{field:02d}",
                             "semeadura": pd.Timestamp(f"{y}-{f.window}") + pd.Timedelta(days=int(rng.integers(0, 50))),
                             "cultivar": names[int(rng.integers(0, 2))],
                             "irrigado": "sim" if field <= 2 and f.fazenda == "Fazenda C" else "nao"})
    plan = pd.DataFrame(rows)
    plan["gm"] = plan["cultivar"].map(CATALOGUE)

    # "observations": the emulator with the hidden true cultivar, plus noise
    sites = FARMS.set_index("fazenda")
    soils = read_soils(OUT / "solo.csv")
    out = []
    for (farm, cv, irr), g in plan.groupby(["fazenda", "cultivar", "irrigado"]):
        s = sites.loc[farm]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            w = read_weather(OUT / f"clima_{farm.split()[-1]}.csv", lat=s.lat, lon=s.lon, elev=s.elev)
        p = emu.predict(w, lat=s.lat, elev=s.elev, soil=soils[farm], sowing=list(g["semeadura"]),
                        cultivar=true[cv], irrigated=irr == "sim").outputs
        out.append(p.set_index(g.index))
    out = pd.concat(out).loc[plan.index]
    field_eff = plan.groupby(["fazenda", "talhao"])["fazenda"].transform(lambda s: rng.normal(1, 0.06))
    farm_year = plan.groupby(["fazenda", plan["semeadura"].dt.year])["fazenda"].transform(lambda s: rng.normal(1, 0.05))
    plan["produtividade (kg/ha)"] = np.round(np.clip(out["HWAM"] * field_eff * farm_year
                                                     + rng.normal(0, 150, len(plan)), 0, None), 0)
    plan["florescimento"] = plan["semeadura"] + pd.to_timedelta(np.round(out["ADAT_dap"] + rng.normal(0, 2, len(plan))), unit="D")
    plan["maturacao"] = plan["semeadura"] + pd.to_timedelta(np.round(out["MDAT_dap"] + rng.normal(0, 2.5, len(plan))), unit="D")
    plan.loc[rng.random(len(plan)) < 0.6, "florescimento"] = pd.NaT          # flowering rarely recorded
    plan.loc[rng.random(len(plan)) < 0.2, "maturacao"] = pd.NaT
    plan.loc[rng.random(len(plan)) < 0.03, "produtividade (kg/ha)"] = np.nan
    for c in ("semeadura", "florescimento", "maturacao"):
        plan[c] = plan[c].dt.strftime("%d/%m/%Y")
    plan.drop(columns="gm").assign(gm=plan["gm"]).to_csv(OUT / "safras.csv", index=False)
    print(f"{len(plan)} seasons; files in {OUT}: {sorted(p.name for p in OUT.iterdir())}")


if __name__ == "__main__":
    main()
