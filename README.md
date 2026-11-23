# cropemu

[![PyPI](https://img.shields.io/pypi/v/cropemu)](https://pypi.org/project/cropemu/)
[![Python](https://img.shields.io/pypi/pyversions/cropemu)](https://pypi.org/project/cropemu/)
[![Downloads](https://img.shields.io/pepy/dt/cropemu?label=downloads)](https://pepy.tech/projects/cropemu)
[![Downloads/month](https://img.shields.io/pypi/dm/cropemu?label=downloads%2Fmonth)](https://pypistats.org/packages/cropemu)
[![License: MIT](https://img.shields.io/pypi/l/cropemu)](https://opensource.org/licenses/MIT)

Fast, validated emulators of process-based crop models: neural networks trained on ~118,000
seasons simulated with the official **DSSAT CROPGRO-Soybean** and **FAO AquaCrop 7.3** executables at
~2,000 points of the world's soybean area. They predict a whole season (phenology, yield, biomass,
water balance) in a fraction of a millisecond, anywhere on the globe, without installing the crop models.

```bash
pip install "cropemu[soil]"
```

## Packages

| Package | Purpose | Status |
|---|---|---|
| [`cropemu`](packages/cropemu) | Library for end users: the emulators (shipped inside), weather (NASA POWER) and soil (SoilGrids) anywhere, readers of your own data (spreadsheets, DSSAT files), prediction with validation levels and domain checks. Depends only on numpy, pandas and onnxruntime. | [on PyPI](https://pypi.org/project/cropemu/), 0.5.0 |
| [`cropemu-bench`](packages/cropemu-bench) | Research package: crop model adapters (DSSAT, AquaCrop), experimental design, simulation, emulator training, benchmarking and export to ONNX. | in this repository |

## Emulators

| Emulator | Crop model | Validation by 5° spatial blocks: maturity, yield |
|---|---|---|
| `dssat-soybean-v3` | DSSAT 4.8 CROPGRO-Soybean | 2.9 d; 343 kg/ha (R² 0.97) |
| `aquacrop-soybean-v3` | FAO AquaCrop 7.3 | 4.4 d; 0.51 t/ha (R² 0.93) |
| `dssat-soybean-v2` | DSSAT 4.8 CROPGRO-Soybean | 3.1 d; 335 kg/ha (R² 0.97) |
| `aquacrop-soybean-v2` | FAO AquaCrop 7.3 | 4.3 d; 0.50 t/ha (R² 0.93) |
| `dssat-soybean-v1` | DSSAT 4.8 CROPGRO-Soybean | 3.3 d; 454 kg/ha (R² 0.94) |
| `aquacrop-soybean-v1` | FAO AquaCrop 7.3 | 4.4 d; 0.58 t/ha (R² 0.91) |

v3: the v2 networks with the plant population (15–50 plants/m²) as an input, plus a second
network for the daily curves of leaf area (LAI or canopy cover), biomass, grain and water stress
(their shape in phenological time, scaled to the season values; block validation R² 0.95–0.99 for
biomass and grain, 0.80/0.66 for DSSAT/AquaCrop stress). Trained on the v3 campaign: the v1/v2
seasons with a sampled plant population and the daily outputs (data release
[`data-v3`](https://github.com/fcoliveira-utfpr/emulator_crop/releases/tag/data-v3)).
v2: development dates from the mean of four dense networks; the other outputs from a 1-D
convolutional network over the daily weather of the season (30 days before to 170 days after
sowing) joined to the season inputs. v1: dense networks on weather summaries in five windows.
Yield error by world region and the global map of the sites: [`analises/RESULTADOS.md`](analises/RESULTADOS.md).

## Web app

[**CropEmu**](https://fcoliveira-utfpr.github.io/emulator_crop/) runs both v3 emulators in the
browser, anywhere in the world (NASA POWER weather, SoilGrids soil, or your own spreadsheets): one
season, many years, sowing window, cultivars, climate scenarios and **crop monitoring** of the
season in progress (observed weather and the 16-day forecast from Open-Meteo, the rest of the cycle
from past years shifted by the ECMWF seasonal forecast; expected yield and yield gap week by week). The *One season* tab shows the emulated
daily curves and an animated plant that grows, flowers, fills pods and wilts with them; the plant
population is a management input.
How to read every chart and number: [guide](docs/guide.md) ([guia em português](docs/guia.md)), also in
the *Guide* tab of the app. Source in [`web/`](web).

## Example notebooks

| Notebook | What it shows |
|---|---|
| [`examples/dssat_soybean.ipynb`](examples/dssat_soybean.ipynb) | Tour of the DSSAT emulator: outputs and validation, one site, 35 years, sowing window, cultivars and sensitivity, water, climate scenarios, regional map, speed; own data with published field trials (station weather, measured soils, calibration). |
| [`examples/aquacrop_soybean.ipynb`](examples/aquacrop_soybean.ipynb) | The same tour with the AquaCrop emulator. |
| [`examples/your_data.ipynb`](examples/your_data.ipynb) | From spreadsheets (sites, weather, soil, seasons) to predictions, comparison with observations, calibration, sowing window and scenarios per farm; synthetic example spreadsheets in [`examples/data/your_data`](examples/data/your_data), downloaded by the notebook from GitHub (made by [`make_example_data.py`](examples/data/make_example_data.py)). |
| [`examples/compare_emulator_simulator.ipynb`](examples/compare_emulator_simulator.ipynb) | Emulators vs. the crop models at 7 sites outside the training data (needs the DSSAT and AquaCrop executables). |

The notebooks are written by the scripts in [`tools/notebooks`](tools/notebooks).

## Repository

- [`packages/`](packages): the two packages and their tests.
- [`web/`](web): the static web app (GitHub Pages).
- [`docs/`](docs): guide to the web app ([EN](docs/guide.md), [PT](docs/guia.md)).
- [`analises/`](analises): analyses and figures of the paper.
- [`benchmark/`](benchmark): scripts that generate the simulated data sets, train and compare the emulators, and export them.
- [`planing.md`](planing.md): research plan, decisions and results (in Portuguese).

## Development install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e "packages/cropemu[soil,test]" -e "packages/cropemu-bench[test]"
pytest packages
```

Tests and scripts that run the real crop models need their executables:

| Variable | Value |
|---|---|
| `CROPEMU_DSSAT_EXE` | path to `dscsm048` |
| `CROPEMU_DSSAT_HOME` | DSSAT `Data` directory |
| `CROPEMU_AQUACROP_EXE` | path to the AquaCrop 7.3 executable |
| `CROPEMU_AQUACROP_DATA` | AquaCrop `DATA` directory |
| `CROPEMU_CACHE` | cache of weather and soil downloads (default `~/.cache/cropemu`) |

Without them those tests are skipped.

## License

MIT. See [LICENSE](LICENSE). Data sources: NASA POWER, SoilGrids 2.0 (CC-BY 4.0), GGCMI Phase 3
crop calendar. Not affiliated with the DSSAT Foundation or FAO.
