# cropemu

[![PyPI](https://img.shields.io/pypi/v/cropemu)](https://pypi.org/project/cropemu/)
[![Python](https://img.shields.io/pypi/pyversions/cropemu)](https://pypi.org/project/cropemu/)
[![Downloads](https://img.shields.io/pepy/dt/cropemu?label=downloads)](https://pepy.tech/projects/cropemu)
[![Downloads/month](https://img.shields.io/pypi/dm/cropemu?label=downloads%2Fmonth)](https://pypistats.org/packages/cropemu)
[![License: MIT](https://img.shields.io/pypi/l/cropemu)](https://opensource.org/licenses/MIT)

Fast, validated emulators of process-based crop models: neural networks trained on ~118,000
seasons simulated with the official **DSSAT CROPGRO-Soybean** and **FAO AquaCrop 7.3** executables at
~2,000 points of the world's soybean area. They predict a whole season (phenology, yield, biomass,
water balance) in microseconds, anywhere on the globe, without installing the crop models.

```bash
pip install "cropemu[soil]"
```

## Packages

| Package | Purpose | Status |
|---|---|---|
| [`cropemu`](packages/cropemu) | Library for end users: the emulators (shipped inside), weather (NASA POWER) and soil (SoilGrids) anywhere, readers of your own data (spreadsheets, DSSAT files), prediction with validation levels and domain checks. Depends only on numpy, pandas and onnxruntime. | [on PyPI](https://pypi.org/project/cropemu/), 0.3.0 |
| [`cropemu-bench`](packages/cropemu-bench) | Research package: crop model adapters (DSSAT, AquaCrop), experimental design, simulation, emulator training, benchmarking and export to ONNX. | in this repository |

## Emulators

| Emulator | Crop model | Validation by 5° spatial blocks: maturity, yield |
|---|---|---|
| `dssat-soybean-v1` | DSSAT 4.8 CROPGRO-Soybean | 3.3 d; 454 kg/ha (R² 0.94) |
| `aquacrop-soybean-v1` | FAO AquaCrop 7.3 | 4.4 d; 0.58 t/ha (R² 0.91) |

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
