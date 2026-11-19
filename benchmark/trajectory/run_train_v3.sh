#!/bin/bash
# v3 point outputs (v2 architecture + plant population input): block CV then final fit, DSSAT and AquaCrop in parallel.
cd /c/Python/emulator_crop/emulator_crop
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=9 MKL_NUM_THREADS=9
PY=.venv/Scripts/python.exe
run() { $PY benchmark/train_sequence.py --name $1 cv && $PY benchmark/train_sequence.py --name $1 fit; }
run dssat_v3 > logs/train_dssat_v3.log 2>&1 &
run aquacrop_v3 > logs/train_aquacrop_v3.log 2>&1 &
wait
echo TRAIN DONE
