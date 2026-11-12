"""Builds artigo/references.bib from Crossref (DOI content negotiation or title search)."""
import json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

UA = {"User-Agent": "cropemu-paper/0.1 (bibliography builder)"}
REFS = {  # key: DOI or ("title", "first author surname")
    "jones2003": "10.1016/S1161-0301(02)00107-7", "hoogenboom2019": "10.19103/AS.2019.0061.10",
    "kelly2021": "10.1016/j.agwat.2021.106976", "kothari2022": "10.1016/j.eja.2022.126482",
    "battisti2017": "10.1016/j.fcr.2016.10.004", "sentelhas2015": "10.1017/S0021859615000313",
    "sampaio2021": "10.1017/S0021859621000204", "monteiro2018": "10.1002/joc.5282",
    "duarte2020": "10.1007/s00484-019-01810-1", "vonbloh2023": "10.1016/j.agrformet.2023.109670",
    "beck2023": "10.1038/s41597-023-02549-6", "oliveira2021": "10.1590/0102-77863630001",
    "willmott2012": "10.1002/joc.2419",
    "steduto2009": ("AquaCrop The FAO crop model to simulate yield response to water: I. Concepts and underlying principles", "Steduto"),
    "raes2009": "10.2134/agronj2008.0140s",
    "johnston2023": "10.1016/j.envsoft.2023.105634",
    "franke2020": "10.5194/gmd-13-3995-2020",
    "folberth2019": ("Spatio-temporal downscaling of gridded crop model yield estimates based on machine learning", "Folberth"),
    "ringeval2021": ("Potential yield simulated by global gridded crop models: using a process-based emulator to explain their differences", "Ringeval"),
    "liu2026": ("A food crop yield emulator for integration in the compact Earth system model OSCAR (OSCAR-crop v1.0)", "Liu"),
    "alimagham2025": ("Integrating crop models and machine learning for projecting climate change impacts on crops in data-limited environments", "Alimagham"),
    "garg2026": ("Integrating AquaCrop-OSPy and machine learning to develop transferable surrogates for balancing wheat yield irrigation trade-offs under deficit irrigation in semi-arid NW India", "Garg"),
    "garofalo2026": "10.3390/agriculture16080890",
    "razavi2012": ("Review of surrogate modeling in water resources", "Razavi"),
    "hou2024": ("A protocol for developing and evaluating neural network-based surrogate models and its application to building energy prediction", "Hou"),
    "park2023": ("Limitations and issues of conventional artificial neural network-based surrogate models for building energy retrofit", "Park"),
    "shahhosseini2019": ("Maize yield and nitrate loss prediction with machine learning algorithms", "Shahhosseini"),
    "dokoohaki2022": ("Linking Remote Sensing with APSIM through Emulation and Bayesian Optimization to Improve Yield Prediction", "Dokoohaki"),
    "pohjankukka2017": ("Estimating the prediction performance of spatial models via spatial k-fold cross validation", "Pohjankukka"),
    "kattenborn2022": ("Spatially autocorrelated training and validation samples inflate performance assessment of convolutional neural networks", "Kattenborn"),
    "roberts2017": ("Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure", "Roberts"),
    "poggio2021": ("SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty", "Poggio"),
    "saxton2006": ("Soil water characteristic estimates by texture and organic matter for hydrologic solutions", "Saxton"),
    "reichert2009": ("Estimation of water retention and availability in soils of Rio Grande do Sul", "Reichert"),
    "jagermeyr2021": ("Climate impacts on global agriculture emerge earlier in new generation of climate and crop models", "Jägermeyr"),
    "lobell2010": ("On the use of statistical models to predict crop yield responses to climate change", "Lobell"),
    "li2024": ("Knowledge-guided machine learning for improving crop yield projections of waterlogging effects under climate change", "Li"),
    "angione2022": ("Using machine learning as a surrogate model for agent-based simulations", "Angione"),
    "battisti2019": "10.1016/j.fcr.2019.06.007",
}

def get(url, accept=None):
    req = urllib.request.Request(url, headers={**UA, **({"Accept": accept} if accept else {})})
    return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")

out, log = [], []
for key, ref in REFS.items():
    try:
        if isinstance(ref, tuple):
            title, author = ref
            q = urllib.parse.urlencode({"query.bibliographic": title, "query.author": author, "rows": 3})
            items = json.loads(get("https://api.crossref.org/works?" + q))["message"]["items"]
            norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
            best = next((i for i in items if norm(title)[:40] in norm(" ".join(i.get("title", [""])))), None)
            if best is None:
                log.append(f"{key}: NOT FOUND ({[i.get('title') for i in items][:2]})"); continue
            doi = best["DOI"]
        else:
            doi = ref
        bib = get("https://doi.org/" + urllib.parse.quote(doi), "application/x-bibtex").strip()
        bib = re.sub(r"^(@\w+)\{[^,]*,", lambda m: f"{m.group(1)}{{{key},", bib, count=1)
        out.append(bib)
        t = re.search(r"title\s*=\s*\{(.*?)\},", bib, re.S)
        y = re.search(r"year\s*=\s*\{?(\d{4})", bib)
        log.append(f"{key}: {doi} | {y.group(1) if y else '?'} | {(t.group(1) if t else '?')[:80]}")
    except Exception as e:
        log.append(f"{key}: ERROR {e}")
    time.sleep(0.3)
Path(sys.argv[1]).write_text("\n\n".join(out) + "\n")
print("\n".join(log))
