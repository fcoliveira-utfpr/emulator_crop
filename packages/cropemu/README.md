# cropemu

[![PyPI](https://img.shields.io/pypi/v/cropemu)](https://pypi.org/project/cropemu/)
[![Python](https://img.shields.io/pypi/pyversions/cropemu)](https://pypi.org/project/cropemu/)
[![Downloads](https://img.shields.io/pepy/dt/cropemu?label=downloads)](https://pepy.tech/projects/cropemu)
[![Downloads/month](https://img.shields.io/pypi/dm/cropemu?label=downloads%2Fmonth)](https://pypistats.org/packages/cropemu)
[![License: MIT](https://img.shields.io/pypi/l/cropemu)](https://opensource.org/licenses/MIT)

**Crop model simulations in a fraction of a millisecond, anywhere on the globe, without installing the crop models.**

`cropemu` ships validated neural-network emulators of two widely used process-based crop models,
**DSSAT CROPGRO-Soybean** and **FAO AquaCrop**. Give it the daily weather, the soil, the sowing
date, the cultivar and the plant population, and it returns the whole season: phenology dates, yield,
biomass, evapotranspiration, water balance, stress indices and the daily curves of leaf area, biomass,
grain and water stress. A season runs in about 0.1–0.2 ms (v2, v3) or 10 µs (v1), against 0.05–1 s for the crop model, so you can simulate millions of seasons on a laptop: decades of
weather × sowing dates × cultivars × climate scenarios, for one field or a whole region.

Every prediction says how far it can be trusted: each output carries an acceptance level from a
spatial cross-validation, and every season is checked against the range of the training data.

| Emulator | Crop model | Inputs | Outputs |
|---|---|---|---|
| `dssat-soybean-v3` | DSSAT 4.8 CROPGRO-Soybean (official executable) | weather (summaries and the daily series), soil, sowing date, maturity group and 13 cultivar coefficients, plant population, water regime, CO₂ | 40 + daily curves |
| `aquacrop-soybean-v3` | FAO AquaCrop 7.3 (official executable) | weather (summaries and the daily series), soil, sowing date, 13 crop parameters, plant population, water regime, CO₂ | 44 + daily curves |

The v3 emulators (0.5.0) are the v2 networks with the plant population (15–50 plants/m²) as an
input and a second output: the shape of the season's daily curves (leaf area or canopy cover,
biomass, grain, water stress). The v2 emulators (0.4.0) read the daily weather of the season with a convolutional network, which
cut the yield error on unseen regions from 454 to 335 kg/ha (DSSAT) and from 0.58 to 0.50 t/ha
(AquaCrop); the development dates come from the mean of four dense networks. The v1 emulators
(dense networks on weather summaries only) and the v2 ones still ship for comparison.

Both were trained on ~118,000 seasons simulated with the official executables at ~2,000 points
of the world's soybean area (NASA POWER weather, SoilGrids soils, GGCMI crop calendar, perturbed
cultivars and climate). They ship inside the package (~4.3 MB each for v3) and need only `numpy`,
`pandas` and `onnxruntime`.

**No Python?** The same emulators run in the browser in the
[CropEmu web app](https://fcoliveira-utfpr.github.io/emulator_crop/): one season, many years, sowing
window, cultivars, climate scenarios and crop monitoring of the season in progress, anywhere in
the world, with NASA POWER weather, SoilGrids soil or your own spreadsheets.

## What's new in 0.5.0

- **v3 emulators** `dssat-soybean-v3` and `aquacrop-soybean-v3`, trained on a new campaign with the
  plant population sampled from 15 to 50 plants/m² per season (the other season inputs are those of
  v1/v2). The population is part of the cultivar dictionary (`population`, default 30):
  `emu.predict(..., cultivar={**emu.cultivar(mg=6.5), "population": 40})`. Out of sample, the
  emulated yield gain per 10 plants/m² matches the crop model (emulated vs. simulated: DSSAT rainfed +63 vs. +61 kg/ha,
  without water stress +124 vs. +128; AquaCrop +0.133 t/ha in both).
- **Daily curves:** `res.curves()` returns `{curve: table (season × day after sowing)}` for leaf
  area index (DSSAT) or canopy cover (AquaCrop), aboveground biomass, grain and water stress (0-1).
  The growth curves end at the emulated season values and are placed on days by the emulated
  emergence, flowering and maturity. Shape R² in the block validation: leaf 0.98/0.93,
  biomass 0.95/0.97, grain 0.99/0.98, stress 0.80/0.66 (DSSAT/AquaCrop).
- Same accuracy as v2 for the season outputs (yield 343 kg/ha and 0.51 t/ha on unseen regions).
- `CH4EM` (DSSAT methane) is now an output, marked *not recommended*.

## In 0.4.0

- **v2 emulators** `dssat-soybean-v2` and `aquacrop-soybean-v2`: a 1-D convolutional network reads
  the daily weather from 30 days before to 170 days after sowing (temperature, radiation, rain,
  ETo, vapour pressure deficit, day length, a soil-water stress index), so it sees *when* heat,
  drought or rain happen in the cycle. Yield error on unseen regions: 454 → 335 kg/ha (DSSAT) and
  0.58 → 0.50 t/ha (AquaCrop); lower in all eight world regions of the soybean area.
- `emu.inputs()` keeps the daily series of each season and adds a `sequence_id` column; tables
  built from it (and `prediction.inputs`) can be edited and passed to `predict_inputs`, or pass
  `sequence=` (rows × channels × days) yourself. `emu.uses_sequence` and `emu.weather_days_after`
  tell what an emulator needs.
- Weather must now cover 170 days after sowing for v2 (130 for v1).
- The v1 emulators are still shipped; `cropemu.load("dssat-soybean-v1")` keeps old results reproducible.

## What you can do with it

- **Sowing window:** yield and risk for every sowing date × every year of the climate record.
- **Cultivar choice:** compare maturity groups or cycle lengths at a site, or across a region.
- **Climate scenarios:** warming, CO₂ and rain changes, as in the training design.
- **Water:** rainfed vs. irrigated yield, the yield gap due to water.
- **Plant population:** yield response to 15–50 plants/m² (v3).
- **Daily curves:** leaf area, biomass, grain and water stress through the season (v3).
- **Season monitoring:** observed weather up to today, then each past year (or a forecast) for the
  rest of the cycle, to follow the expected yield and the yield gap during the season.
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

emu = cropemu.load("dssat-soybean-v3")                             # cropemu.available() lists them
emu.describe()                                                     # outputs, units, validation error, level

res = emu.predict(weather, lat=lat, elev=600, soil=soil,
                  sowing=["2020-10-15", "2021-10-15", "2022-10-15"],
                  cultivar=emu.cultivar(mg=6.5))                   # default coefficients of MG 6.5
res.outputs[["ADAT_dap", "MDAT_dap", "HWAM", "ETCM"]]              # flowering, maturity (days after sowing), yield (kg/ha), ET (mm)
res.recommended("caution")                                         # only the outputs that passed validation
res.out_of_domain, res.rare_inputs                                 # inputs outside the training data
res.curves()["leaf"]                                               # daily leaf area index (season x day after sowing)
```

Scenarios and water regime: `emu.predict(..., dt=2.0, co2=550, rain_factor=0.9, irrigated=True)`.
Plant population: `cultivar={**emu.cultivar(mg=6.5), "population": 40}` (plants/m², default 30).

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
| | Maturity date | Yield | Evapotranspiration |
|---|---|---|---|
| `dssat-soybean-v3` | 2.9 d (R² 0.99) | 343 kg/ha (R² 0.97) | 24 mm (R² 0.98) |
| `aquacrop-soybean-v3` | 4.4 d (R² 0.98) | 0.51 t/ha (R² 0.93) | 47 mm (R² 0.92) |
| `dssat-soybean-v2` | 3.1 d (R² 0.98) | 335 kg/ha (R² 0.97) | 23 mm (R² 0.98) |
| `aquacrop-soybean-v2` | 4.3 d (R² 0.99) | 0.50 t/ha (R² 0.93) | 45 mm (R² 0.93) |
| `dssat-soybean-v1` | 3.3 d (R² 0.98) | 454 kg/ha (R² 0.94) | 32 mm (R² 0.96) |
| `aquacrop-soybean-v1` | 4.4 d (R² 0.99) | 0.58 t/ha (R² 0.91) | 52 mm (R² 0.90) |

By world region, the v2 yield error ranges from 223 kg/ha (Europe and Central Asia) to 439 kg/ha
(North America) for DSSAT and from 0.38 to 0.59 t/ha for AquaCrop. At 7 sites outside the training
data (Brazil, Argentina, USA, China), the v2 yield error against new runs of the crop models was
224 kg/ha (DSSAT) and 0.33 t/ha (AquaCrop), about half of the values above. For the v3 emulators (plant
population sampled in 15-50 plants/m², 420 seasons) it was 341 kg/ha (DSSAT) and 0.34 t/ha
(AquaCrop), and the yield gain from 15 to 50 plants/m² matched the crop models (rainfed: DSSAT
+0.31 t/ha simulated, +0.30 emulated; AquaCrop +0.53 and +0.51).

- **Acceptance level of every output** (`emu.describe()`, `res.levels`):
  - *recommended*: dates with RMSE ≤ 5 days, other outputs with RMSE < 0.25 of the within-site standard deviation;
  - *caution*: relative error < 0.5;
  - *not recommended*: everything else.
- **`out_of_domain`**: inputs outside the range of the training data. The prediction is an
  extrapolation; do not trust it.
- **`rare_inputs`**: inputs outside the 0.5–99.5 % range of the training data. Trust it less.

## Inputs, as in training

- **Weather:** daily radiation, Tmax, Tmin, rain (humidity and wind optional), summarised in
  windows from 30 days before to 130 days after sowing; the v2 emulators also read the daily
  series up to 170 days after sowing.
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

A paper describing the emulators, their validation by world region and the web app is in preparation; until then, please cite
the package and its version.
