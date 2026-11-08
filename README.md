# cropemu

Fast, validated emulators of process-based crop models.

This repository holds two Python packages:

| Package | Purpose |
|---|---|
| [`cropemu`](packages/cropemu) | Lightweight library for end users: load pre-trained emulators, build their inputs from daily weather, predict. No crop model installation needed. |
| [`cropemu-bench`](packages/cropemu-bench) | Research package: crop model adapters (DSSAT, AquaCrop), experimental design, simulation, emulator training and benchmarking. |

Status: early development (phase 0). See [planing.md](planing.md) for the research plan (in Portuguese).

## Development install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e "packages/cropemu[soil,test]" -e "packages/cropemu-bench[test]"
pytest packages
```

Tests that run the real DSSAT executable are skipped unless `CROPEMU_DSSAT_EXE`
(path to `dscsm048`) and `CROPEMU_DSSAT_HOME` (DSSAT `Data` directory) are set.

## License

MIT. See [LICENSE](LICENSE).
