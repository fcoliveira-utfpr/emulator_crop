"""Full emulator benchmark on the final data sets; skips the (emulator, validation) pairs already in
data/<name>/benchmark/summary.csv, so it can be restarted.

    nohup python analises/run_benchmark.py > analises/logs/benchmark.log 2>&1 &
"""
import subprocess, sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PLAN = {"dssat_v1": ["ridge", "mlp", "gb", "mlp_grouped"],
        "aquacrop_v1": ["ridge", "mlp", "gb", "mlp_grouped", "mlp_offset"]}
for name, emulators in PLAN.items():
    for validation in ("block", "random"):
        for em in emulators:
            s = ROOT / "data" / name / "benchmark" / "summary.csv"
            done = pd.read_csv(s) if s.exists() else pd.DataFrame(columns=["emulator", "validation"])
            if ((done["emulator"] == em) & (done["validation"] == validation)).any():
                print(f"skip {name} {em} {validation}", flush=True)
                continue
            cmd = [sys.executable, str(ROOT / "benchmark" / "phase1_emulators.py"), "--name", name, "--emulators", em,
                   "--validation", validation] + (["--gb-key-only"] if em == "gb" else [])
            print("run", " ".join(cmd[2:]), flush=True)
            subprocess.run(cmd, check=False, cwd=ROOT)
(ROOT / "analises" / "logs" / "bench_done").write_text("done\n")
print("all done", flush=True)
