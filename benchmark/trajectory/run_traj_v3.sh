#!/bin/bash
# v3 trajectory head: targets, then block CV and final fit, once the daily sequences of the main training exist.
cd /c/Python/emulator_crop/emulator_crop
export PYTHONUNBUFFERED=1
PY=.venv/Scripts/python.exe
run() {
  $PY benchmark/trajectory/train_trajectory.py --name $1 targets || return 1
  until [ -f data/$1/sequence_index.parquet ]; do sleep 30; done
  $PY benchmark/trajectory/train_trajectory.py --name $1 cv && $PY benchmark/trajectory/train_trajectory.py --name $1 fit
}
run dssat_v3 > logs/traj_dssat_v3.log 2>&1 &
run aquacrop_v3 > logs/traj_aquacrop_v3.log 2>&1 &
wait
echo TRAJ DONE
