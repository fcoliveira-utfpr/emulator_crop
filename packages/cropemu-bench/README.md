# cropemu-bench

Research package behind `cropemu`: crop model adapters, experimental design,
batch simulation, emulator training and benchmarking.

## DSSAT adapter

Runs the DSSAT CSM executable directly (no DSSATTools in the loop): writes weather
(`.WTH`), soil (`SOIL.SOL`), cultivar (`.CUL`) and experiment (FileX) files, runs
batches of up to 99 treatments per FileX in parallel and reads **all** outputs:
every column of `Summary.OUT`, the stress table of `OVERVIEW.OUT` and any daily
output file (`PlantGro.OUT`, `SoilWat.OUT`, ...).

```python
from cropemu_bench.models.dssat import DSSAT, Treatment, Weather, SoilProfile

model = DSSAT(executable="/path/to/dscsm048", dssat_home="/path/to/DSSAT/Data")
result = model.simulate(treatments, weather={...}, soils={...}, n_jobs=8)
result.summary          # all Summary.OUT columns, one row per season
result.daily["PlantGro"]
```
