# cropemu

[![PyPI](https://img.shields.io/pypi/v/cropemu)](https://pypi.org/project/cropemu/)
[![Python](https://img.shields.io/pypi/pyversions/cropemu)](https://pypi.org/project/cropemu/)
[![Downloads](https://img.shields.io/pepy/dt/cropemu?label=downloads)](https://pepy.tech/projects/cropemu)
[![Downloads/month](https://img.shields.io/pypi/dm/cropemu?label=downloads%2Fmonth)](https://pypistats.org/packages/cropemu)
[![License: MIT](https://img.shields.io/pypi/l/cropemu)](https://opensource.org/licenses/MIT)

**Crop model simulations in microseconds, anywhere on the globe, without installing the crop models.**

`cropemu` ships validated neural-network emulators of two widely used process-based crop models,
**DSSAT CROPGRO-Soybean** and **FAO AquaCrop**. Give it the daily weather, the soil, the sowing
date and the cultivar, and it returns the whole season: phenology dates, yield, biomass,
evapotranspiration, water balance and stress indices. A season runs in microseconds, against
0.1–1 s for the crop model, so you can simulate millions of seasons on a laptop: decades of
weather × sowing dates × cultivars × climate scenarios, for one field or a whole region.

Every prediction says how far it can be trusted: each output carries an acceptance level from a
spatial cross-validation, and every season is checked against the range of the training data.

| Emulator | Crop model | Inputs | Outputs |
|---|---|---|---|
| `dssat-soybean-v1` | DSSAT 4.8 CROPGRO-Soybean (official executable) | weather, soil, sowing date, maturity group and 13 cultivar coefficients, water regime, CO₂ | 41 |
| `aquacrop-soybean-v1` | FAO AquaCrop 7.3 (official executable) | weather, soil, sowing date, 13 crop parameters, water regime, CO₂ | 44 |

Both were trained on ~118,000 seasons simulated with the official executables at ~2,000 points
of the world's soybean area (NASA POWER weather, SoilGrids soils, GGCMI crop calendar, perturbed
cultivars and climate). They ship inside the package (~1.3 MB each) and need only `numpy`,
`pandas` and `onnxruntime`.

## What you can do with it

- **Sowing window:** yield and risk for every sowing date × every year of the climate record.
- **Cultivar choice:** compare maturity groups or cycle lengths at a site, or across a region.
- **Climate scenarios:** warming, CO₂ and rain changes, as in the training design.
- **Water:** rainfed vs. irrigated yield, the yield gap due to water.
- **Regional maps:** thousands of points × decades in seconds.
- **Your own data:** station weather, measured soils, field trials from spreadsheets or DSSAT files.
- **Calibration:** fit cultivar parameters to your observations by trying thousands of
  candidates in seconds.
- **Sensitivity analysis and screening** before running the full crop model where it matters.

Source, example notebooks and issues: <https://github.com/fcoliveira-utfpr/emulator_crop>.

## Install

```bash
pip install cropemu            # emulators + NASA POWER weather + readers of your own data
pip install "cropemu[soil]"    # + SoilGrids soil profiles anywhere (rasterio)
```

Python ≥ 3.10. On Intel Macs, add `--prefer-binary` (the newest rasterio has no wheel for them).

## Quick start: any point of the globe

```python
import cropemu
from cropemu.weather import fetch, fill_gaps
from cropemu.soil import soilgrids

lat, lon = -23.19, -51.18                                          # Londrina, Brazil
weather = fill_gaps(fetch(lat, lon, "2000-01-01", "2024-12-31"))   # NASA POWER, downloaded once
soil = soilgrids.fetch(lat, lon)                                   # SoilGrids 2.0, downloaded once

emu = cropemu.load("dssat-soybean-v1")                             # cropemu.available() lists them
emu.describe()                                                     # outputs, units, validation error, level

res = emu.predict(weather, lat=lat, elev=600, soil=soil,
                  sowing=["2020-10-15", "2021-10-15", "2022-10-15"],
                  cultivar=emu.cultivar(mg=6.5))                   # default coefficients of MG 6.5
res.outputs[["ADAT_dap", "MDAT_dap", "HWAM", "ETCM"]]              # flowering, maturity (days after sowing), yield (kg/ha), ET (mm)
res.recommended("caution")                                         # only the outputs that passed validation
res.out_of_domain, res.rare_inputs                                 # inputs outside the training data
```

Scenarios and water regime: `emu.predict(..., dt=2.0, co2=550, rain_factor=0.9, irrigated=True)`.

## Your own data

**Spreadsheets** (CSV or Excel; English or Portuguese headers; units in parentheses):

```python
from cropemu.io import write_templates, read_sites, read_weather, read_soils, read_seasons

write_templates("my_data", lang="pt")        # locais, clima, solo, safras ("en": sites, weather, soil, seasons)
sites = read_sites("my_data/locais.csv")     # name, lat, lon, elevation
weather = read_weather("my_data/clima.csv", lat=-24.5, lon=-51.6, elev=600)
soils = read_soils("my_data/solo.csv")       # {profile: layers}; measured wilting point / field capacity are used as given
seasons = read_seasons("my_data/safras.csv") # farm, field, sowing, cultivar, irrigated, observed yield and dates
```

Column names such as `Chuva (mm)`, `Argila (g/kg)` or `MO (%)` are recognised, and common unit
mistakes (radiation in W/m², humidity as a fraction, texture in g/kg, organic matter instead of
carbon) are converted with a warning.

**Filling the gaps:** `cropemu.weather.fill_from(station, power)` completes a station with NASA
POWER; `cropemu.soil.fill_from(profile, soilgrids.fetch(lat, lon))` completes a profile with SoilGrids.

**DSSAT files:** `cropemu.io` reads weather (`read_wth`), soil (`read_sol`), cultivar (`read_cul`),
experiment (`read_experiment`) and observed data (`read_observed`):

```python
from cropemu.io import read_cul
cultivar = emu.cultivar_from_dssat(read_cul("SBGRO048.CUL", "IB0001"))
emu.cultivar_domain(cultivar)                # where each coefficient sits in the training range
```

**AquaCrop cycle from an observed season:**
`aq.cultivar(gdd_maturity=cropemu.gdd_between(weather, sowing, maturity))`.

## Calibration in seconds

The inputs of every season are computed once; a candidate cultivar only changes the cultivar
columns and runs the network:

```python
import numpy as np
dates = [f"{y}-10-15" for y in range(2000, 2024)]
X = emu.inputs(weather, lat=lat, elev=600, soil=soil, sowing=dates, cultivar=emu.cultivar(mg=6))
grid = [emu.cultivar(mg=m, LFMAX=l) for m in np.arange(5, 8, 0.05) for l in np.linspace(1.0, 1.18, 10)]
pred = [emu.predict_inputs(X.assign(**c)).outputs["HWAM"] for c in grid]   # pick the best against your yields
```

600 candidates × 24 seasons take a few seconds; stacking the candidates in one table
(`pd.concat`) and calling `predict_inputs` once is faster still.

## How far to trust a prediction

Validation: 5-fold cross-validation by 5° spatial blocks (the emulator never saw the region it is
tested on), against the crop model:

| | Maturity date | Yield | Evapotranspiration |
|---|---|---|---|
| DSSAT emulator | 3.3 d (R² 0.98) | 454 kg/ha (R² 0.94) | 32 mm (R² 0.96) |
| AquaCrop emulator | 4.4 d (R² 0.99) | 0.58 t/ha (R² 0.91) | 52 mm (R² 0.90) |

At 7 sites outside the training data the error against the crop models was about 0.6 of these values.

- **Acceptance level of every output** (`emu.describe()`, `res.levels`):
  - *recommended*: dates with RMSE ≤ 5 days, other outputs with RMSE < 0.25 of the within-site standard deviation;
  - *caution*: relative error < 0.5;
  - *not recommended*: everything else.
- **`out_of_domain`**: inputs outside the range of the training data. The prediction is an
  extrapolation; do not trust it.
- **`rare_inputs`**: inputs outside the 0.5–99.5 % range of the training data. Trust it less.

## Inputs, as in training

- **Weather:** daily radiation, Tmax, Tmin, rain (humidity and wind optional), summarised in
  windows from 30 days before to 130 days after sowing.
- **Soil:** profile to 2 m. Water retention, unless measured: Reichert et al. (2009), field
  capacity at 10 kPa, up to 30° latitude; Saxton & Rawls (2006) from 40°; a linear blend in between.
- **Cultivar:** DSSAT coefficients around the defaults of each maturity group; AquaCrop crop
  parameters within their usual ranges and a cycle (growing degrees) fitted to the local calendar.
- **Fixed in training:** 30 plants/m², 50 cm rows, no nitrogen stress, half of the available water
  30 days before sowing.

## Limitations

- An emulator reproduces its crop model, not the field: errors of the crop model are inherited,
  and the crop models were not calibrated for each site.
- Plant density, row spacing, nitrogen, pests and diseases are not inputs.
- Soybean only for now; maize is planned.
- Alpha: output names follow the crop models and the API may still change.

## License and data

MIT. Training data: NASA POWER, SoilGrids 2.0 (ISRIC, CC-BY 4.0), GGCMI Phase 3 crop calendar;
crop models: DSSAT (BSD-3) and FAO AquaCrop 7.3. `cropemu` is not affiliated with the DSSAT
Foundation or FAO.

A paper describing the benchmark and the emulators is in preparation; until then, please cite
the package and its version.
