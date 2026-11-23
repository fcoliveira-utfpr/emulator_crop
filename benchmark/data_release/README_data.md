# CropEmu simulated soybean datasets

Global soybean seasons simulated with DSSAT 4.8.5 CROPGRO-Soybean and AquaCrop 7.3, used to train and
validate the CropEmu emulators (<https://github.com/fcoliveira-utfpr/emulator_crop>).

| Dataset | Model | Seasons | Notes |
|---|---|---|---|
| `dssat_v1`, `aquacrop_v1` | DSSAT, AquaCrop | 117,720 | Campaign of the paper; plant population fixed at 30 plants m⁻² |
| `dssat_v3`, `aquacrop_v3` | DSSAT, AquaCrop | 117,720 | Same points and seasons as v1, plus plant population sampled per season (15–50 plants m⁻²) and daily trajectories |

Download and unpack with the library (checks the SHA-256):

```python
from cropemu_bench.datasets import fetch_dataset
folder = fetch_dataset("dssat_v3")          # -> data/dssat_v3
```

## Design

- **Points:** 1,962 cells of the 0.5° NASA POWER/GGCMI grid (1,671 in the soybean area of GAEZ+ 2015,
  291 in expansion areas with other field crops), allocated to Köppen-Geiger climate × 10° latitude strata;
  285 blocks of 5° × 5° (column `block`, used for spatial cross-validation).
- **Seasons:** 60 per point, Latin hypercube: year (1985–2024), sowing date (GGCMI Phase 3 calendar ± 30 days),
  maturity group (typical MG of the latitude ± 2), perturbed cultivar coefficients, water regime
  (20% without water stress), and in 30% of the seasons a climate perturbation (ΔT −1 to +4 °C on TMAX and TMIN,
  rain × 0.7–1.3, CO₂ 350–800 ppm).
- **Fixed:** row spacing 0.5 m, no nitrogen stress, 50% of available water 30 days before sowing;
  plant population 30 plants m⁻² in v1, sampled in v3 (column `population`, own random stream, so every other
  input of a season is the same as in v1).
- **Inputs:** NASA POWER daily weather; SoilGrids 2.0 soil (1 km, 3 × 3 km median), with water limits from
  pedotransfer functions (see `meta.json`).
- AquaCrop simulates the same seasons as DSSAT (`sample` is shared), with its own perturbed crop parameters.

## Files (per dataset folder)

| File | Content |
|---|---|
| `meta.json` | Design parameters, data sources, model versions |
| `points.parquet` | Usable points: `id`, `lat`, `lon`, `kind` (soy/expansion), `koppen`, `stratum`, `block`, `soy_ha`, `elev`, soil summary |
| `points_prepared.parquet` | (DSSAT) all sampled points, with `ok` and the `problem` of the 38 points left out (37 without soil data, 1 with incomplete weather) |
| `design.parquet` | One row per season (`sample`): point, year, sowing, MG, regime (`water`: water balance on), climate perturbation, `population`, cultivar or crop parameters |
| `cultivars.parquet` | (DSSAT) cultivar coefficients of every season |
| `summary/batch*.parquet` | Season outputs, native names (DSSAT `Summary.OUT`: e.g. `HWAM` yield kg ha⁻¹, `ADAT`/`MDAT` flowering/maturity, `LAIX`, `CWAM`, `ETCM`; AquaCrop: e.g. `Y(dry)` t ha⁻¹, `BioMass`, `FLO_dap`, `MAT_dap`, `ET_crop`) |
| `stress/batch*.parquet` | (DSSAT) environment and stress factors by development phase (`OVERVIEW.OUT`) |
| `daily_PlantGro/batch*.parquet` | (DSSAT v3) daily `DAP`, `GSTD`, `LAID`, `LWAD`, `SWAD`, `GWAD`, `PWAD`, `CWAD`, `P#AD`, `WSPD`, `WSGD`, `NSTD`, `CHTD`, `RDPD` from sowing |
| `daily_day/batch*.parquet` | (AquaCrop v3) daily `DAP`, `Stage`, `CC`, `Biomass`, `Y(dry)`, `Z`, `StExp`, `StSto`, `StSen`, `Tr/Trx` over the crop period |

Join tables on `sample` (season) and `point` / `id` (location). Missing values of the models (−99 in DSSAT,
−9 in AquaCrop) are NaN. `envsum` is empty in v3 (not written by DSSAT 4.8.5 on Windows; not used).
In `aquacrop_v3`, 5 seasons stopped with an AquaCrop runtime error and have NaN outputs (column `error`).

## License and attribution

The simulated data are released under CC BY 4.0 (`LICENSE-data.txt`). Please cite the CropEmu paper and
repository, and the input data: NASA POWER (NASA Langley Research Center), SoilGrids 2.0 (Poggio et al., 2021,
CC BY 4.0), GAEZ+ 2015 crop area (Grogan et al., 2022), GGCMI Phase 3 crop calendar (Jägermeyr et al., 2021)
and the Köppen-Geiger classification (Beck et al., 2023). DSSAT and AquaCrop are the property of their developers.
