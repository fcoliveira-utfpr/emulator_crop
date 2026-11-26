"""Lower tail of yield and risk (R3): does the emulator reproduce the risk of poor seasons at a site?

v3 campaign, out-of-fold predictions of the released emulators (5° spatial blocks), rainfed seasons under
historical climate. Per site: threshold = 20th percentile of the simulated yield; share of the emulated
seasons below it (should be 20 %), hit rate (emulated below | simulated below) and false alarm rate; 10th
percentile of the yield, simulated against emulated; and the share of seasons below 1 t/ha (crop failure).

    python analises/08_tail_risk.py
"""
import numpy as np
import pandas as pd

from common import ROOT, TAB
from cropemu_bench.dataset import build

YLD = {"dssat": ("HWAM", 1e-3), "aquacrop": ("Y(dry)", 1.0)}
rows, sites = [], []
for model, (col, sc) in YLD.items():
    folder = ROOT / "data" / f"{model}_v3"
    X, Y, info = build(folder, derived=True)
    design = pd.read_parquet(folder / "design.parquet").set_index("sample").loc[Y.index]
    P = pd.read_parquet(folder / "benchmark" / "cnn_block_oof.parquet").loc[Y.index]
    d = pd.DataFrame({"site": info["point"], "sim": Y[col] * sc, "emu": P[col] * sc,
                      "rainfed": design["water"].astype(bool), "perturbed": design["perturbed"].astype(bool)})
    d = d[d.rainfed & ~d.perturbed].dropna()
    for site, g in d.groupby("site"):
        if len(g) < 15:
            continue
        thr = g["sim"].quantile(0.2)
        sb, eb = g["sim"] < thr, g["emu"] < thr
        sites.append(dict(model=model, site=site, n=len(g), thr=thr, share_emu=eb.mean(), share_sim=sb.mean(),
                          hit=(eb & sb).sum() / max(sb.sum(), 1), false_alarm=(eb & ~sb).sum() / max((~sb).sum(), 1),
                          p10_sim=g["sim"].quantile(0.1), p10_emu=g["emu"].quantile(0.1),
                          p50_sim=g["sim"].median(), p50_emu=g["emu"].median(),
                          fail_sim=(g["sim"] < 1).mean(), fail_emu=(g["emu"] < 1).mean()))
    s = pd.DataFrame([r for r in sites if r["model"] == model])
    e10 = s["p10_emu"] - s["p10_sim"]
    sf = d["sim"] < 1
    ef = d["emu"] < 1
    rows.append(dict(model=model, sites=len(s), seasons=len(d),
                     share_below_p20_emu=100 * s["share_emu"].mean(),
                     share_below_p20_emu_p10_p90=f"{100 * s['share_emu'].quantile(0.1):.0f}-{100 * s['share_emu'].quantile(0.9):.0f}",
                     hit_rate=100 * s["hit"].mean(), false_alarm=100 * s["false_alarm"].mean(),
                     p10_bias=e10.mean(), p10_rmse=np.sqrt((e10 ** 2).mean()), p10_r=np.corrcoef(s["p10_sim"], s["p10_emu"])[0, 1],
                     p50_bias=(s["p50_emu"] - s["p50_sim"]).mean(),
                     failure_sim=100 * sf.mean(), failure_emu=100 * ef.mean(),
                     failure_hit=100 * (sf & ef).sum() / max(sf.sum(), 1),
                     failure_false=100 * (ef & ~sf).sum() / max((~sf).sum(), 1),
                     failure_sites_sim=100 * (s["fail_sim"] > 0.2).mean(), failure_sites_emu=100 * (s["fail_emu"] > 0.2).mean()))
t = pd.DataFrame(rows)
t.round(3).to_csv(TAB / "tail_risk.csv", index=False)
pd.DataFrame(sites).round(4).to_csv(TAB / "tail_risk_by_site.csv", index=False)
pd.set_option("display.width", 220)
print(t.round(3).T.to_string())
