# cropemu

Fast emulators of process-based crop models, usable anywhere on the globe without
installing the models. An emulator is a neural network trained on ~118,000 simulated
seasons at ~2,000 points of the soybean area of the world. It predicts a whole season
(phenology dates, yield, biomass, water balance) in about 10 µs instead of the 0.1–1 s
of the crop model.

| Emulator | Crop model | Inputs | Outputs |
|---|---|---|---|
| `dssat-soybean-v1` | DSSAT 4.8 CROPGRO-Soybean (official executable) | weather, soil, sowing date, 14 cultivar coefficients, water regime, CO₂ | 41 |
| `aquacrop-soybean-v1` | FAO AquaCrop 7.3 (official executable) | weather, soil, sowing date, 13 crop parameters, water regime, CO₂ | 44 |

Both emulators ship inside the package (~1.3 MB each) and run with `onnxruntime` only.

## Install

```bash
pip install cropemu            # emulators + NASA POWER weather
pip install "cropemu[soil]"    # + SoilGrids soil profiles (rasterio)
```

On Intel Macs, add `--prefer-binary` (the newest rasterio has no wheel for them).

## Quick start

```python
import cropemu
from cropemu.weather import fetch, fill_gaps
from cropemu.soil import soilgrids

lat, lon = -23.19, -51.18                                   # Londrina, Brazil
weather = fill_gaps(fetch(lat, lon, "2000-01-01", "2024-12-31"))   # NASA POWER, cached
soil = soilgrids.fetch(lat, lon)                            # SoilGrids 2.0 profile, cached

emu = cropemu.load("dssat-soybean-v1")
emu.describe()                                              # outputs, units, validation error, level

res = emu.predict(weather, lat=lat, elev=600, soil=soil,
                  sowing=["2020-10-15", "2021-10-15", "2022-10-15"],
                  cultivar=emu.cultivar(mg=6.5))
res.outputs[["MDAT_dap", "HWAM", "ETCM"]]                    # maturity (days after sowing), yield (kg/ha), ET (mm)
res.recommended("caution")                                  # only outputs that passed validation
res.out_of_domain, res.rare_inputs                          # inputs outside the training data
```

Climate scenarios as in training: `emu.predict(..., dt=2.0, rain_factor=0.9, co2=550)`.
Irrigated (no water stress): `irrigated=True`.

## What every prediction tells you

- **Acceptance level of each output**, from a 5-fold cross-validation by 5° spatial blocks
  (the emulator never saw the region it is tested on):
  - *recommended*: dates with RMSE ≤ 5 days; other outputs with RMSE < 0.25 of the
    within-site standard deviation;
  - *caution*: relative error < 0.5;
  - *not recommended*: everything else.
- **`out_of_domain`**: inputs outside the range of the training data (do not trust).
- **`rare_inputs`**: inputs outside the 0.5–99.5 % range of the training data (less trust).

Validation, by spatial blocks:

| | Maturity date | Yield | Evapotranspiration |
|---|---|---|---|
| DSSAT | 3.3 d (R² 0.98) | 454 kg/ha (R² 0.94) | 32 mm (R² 0.96) |
| AquaCrop | 4.4 d (R² 0.99) | 0.58 t/ha (R² 0.91) | 52 mm (R² 0.90) |

## Inputs, as in training

- **Weather:** NASA POWER daily data, gaps filled. The emulator summarises it in windows from
  30 days before to 130 days after sowing.
- **Soil:** SoilGrids 2.0 (1 km, 3 × 3 km median, 6 layers to 2 m). Water retention:
  Reichert et al. (2009) with field capacity at 10 kPa up to 30° latitude, Saxton & Rawls
  (2006) from 40°, and a linear blend in between.
- **Cultivar:**
  - `emu.cultivar(mg=...)` gives the DSSAT default coefficients of a maturity group.
  - For AquaCrop it gives the middle of the training range of every crop parameter. The cycle
    length comes from the local climate: `emu.cultivar(weather=..., sowing=..., cycle_days=...)`.
  - Any value can be overridden: `emu.cultivar(mg=6, LFMAX=1.1)`.
- **Fixed in training:** 30 plants/m², 50 cm rows, no nitrogen stress, 50 % of the available
  water at the start of the simulation (30 days before sowing).

## Limitations

- An emulator reproduces its crop model, not the field: model errors are inherited.
- Soybean only (maize planned).
- Pre-alpha: the output names follow the crop models and may change.

## License

MIT. Data sources: NASA POWER, SoilGrids 2.0 (CC-BY 4.0), GGCMI Phase 3 crop calendar.
