#!/bin/bash
# Phase 2 / v3: campaign with daily trajectories and sampled plant population (15-50 plants/m²);
# DSSAT, then AquaCrop on the same seasons. Other season inputs are the same as dssat_v1.
set -e
cd /c/Python/emulator_crop/emulator_crop
export CROPEMU_DSSAT_EXE=C:/DSSAT48/DSCSM048.EXE CROPEMU_DSSAT_HOME=C:/DSSAT48
export CROPEMU_AQUACROP_EXE="$USERPROFILE/aquacrop73/aquacrop-7.3-x86_64-windows/aquacrop.exe"
export PYTHONUNBUFFERED=1
PY=.venv/Scripts/python.exe
$PY benchmark/generate_dssat.py --name dssat_v3 --points 2000 --seasons 60 --jobs 16 \
    --population-range 15 50 --daily > logs/dssat_v3.log 2>&1
$PY benchmark/generate_aquacrop.py --seasons-from dssat_v3 --name aquacrop_v3 \
    --crop-dir packages/cropemu-bench/tests/data/aquacrop --jobs 16 --daily > logs/aquacrop_v3.log 2>&1
echo CAMPAIGN DONE
