"""Reference inputs/outputs from the Python cropemu, to check the browser port (web/tests/check_engine.mjs).

Run from the repository root: python web/tests/make_reference.py
"""
import json
from pathlib import Path

import pandas as pd

import cropemu
from cropemu.io import read_sites, read_soils, read_weather
from cropemu.weather import fill_gaps

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "examples" / "data" / "your_data"
sites = read_sites(DATA / "locais.csv")
soils = read_soils(DATA / "solo.csv")
FARM = "Fazenda A"
s = sites.loc[FARM]
w = fill_gaps(read_weather(DATA / "clima_A.csv", lat=s["lat"], lon=s["lon"], elev=s["elev"]))
SOWINGS = ["1995-10-02", "2003-11-15", "2010-09-25", "2020-12-10"]
SCEN = [dict(dt=0.0, rain_factor=1.0), dict(dt=2.0, rain_factor=0.8), dict(dt=-1.0, rain_factor=1.2)]
cases = []
for name in ("dssat-soybean-v1", "aquacrop-soybean-v1"):
    emu = cropemu.load(name)
    if emu.family == "dssat":
        cultivars = {"lat": emu.cultivar(lat=s["lat"]), "mg7": emu.cultivar(mg=7.0)}
    else:
        cultivars = {"days120": emu.cultivar(weather=w, sowing="2003-11-15", cycle_days=120),
                     "mg": emu.cultivar(weather=w, sowing="2003-11-15", cycle_days=120, mg=8.5, lat=s["lat"])}
    for cname, cult in cultivars.items():
        for sc in SCEN:
            for irr in (False, True):
                if irr and sc["dt"]:
                    continue
                p = emu.predict(w, lat=s["lat"], elev=s["elev"], soil=soils[FARM], sowing=SOWINGS,
                                cultivar=cult, irrigated=irr, **sc)
                for k, d in enumerate(SOWINGS):
                    cases.append({"model": name, "cultivar_name": cname, "cultivar": cult, "sowing": d,
                                  "irrigated": irr, **sc,
                                  "inputs": p.inputs.iloc[k].astype(float).to_dict(),
                                  "outputs": p.outputs.iloc[k].astype(float).to_dict()})
out = Path(__file__).with_name("reference.json")
out.write_text(json.dumps({"farm": FARM, "lat": float(s["lat"]), "lon": float(s["lon"]), "elev": float(s["elev"]),
                           "cases": cases}))
print(len(cases), "cases ->", out)
