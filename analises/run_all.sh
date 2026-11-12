#!/bin/bash
# Long analyses of the paper, in order; each step can be restarted.
cd "$(dirname "$0")/.."
.venv/bin/python analises/run_benchmark.py >> analises/logs/benchmark.log 2>&1
[ -f analises/tables/learning_curve_all.csv ] || .venv/bin/python analises/03_learning_curve.py >> analises/logs/learning_curve.log 2>&1
echo finished > analises/logs/all_done
