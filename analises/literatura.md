# Literatura levantada para o artigo (EMS)

Fontes: Zotero do autor (Z), Consensus (C). Metadados e DOI conferidos no Crossref antes de entrar no .bib.

## Emuladores e substitutos de modelos de cultura
- (C) Johnston et al. 2023, Environ. Model. Softw. "Comparison of machine learning methods emulating process driven crop models" — comparação de métodos; referência direta na EMS.
- (C) Franke et al. 2020, GMD. "The GGCMI Phase 2 emulators" — emuladores polinomiais da resposta climatológica (CTWN), 9 modelos, 5 culturas.
- (C) Folberth et al. 2019, Agric. For. Meteorol. "Spatio-temporal downscaling of gridded crop model yield estimates based on machine learning" — meta-modelos XGBoost/RF, R² > 0,96; precisa de preditores sazonais para a variabilidade interanual.
- (C) Ringeval et al. 2020, GMD. emulador mecanístico simples de GGCMs.
- (C) Liu et al. 2026, GMD. OSCAR-crop v1.0, emulador de produtividade treinado no GGCMI/ISIMIP3.
- (C) Lin et al. 2025 (preprint) NeuralCrop: GGCM híbrido diferenciável, treinado primeiro para emular.
- (C) Alimagham et al. 2025, Agric. Syst. — RF + modelo de cultura para África subsaariana (datas, soma térmica, produtividade).
- (C) Li et al. 2024, Resour. Environ. Sustain. — KGML replica APSIM com encharcamento (R² 0,83; RMSE 272 kg/ha).
- (C) Kheir et al. 2023, Agron. J. — APSIM + RNA para distribuição espacial de trigo.
- (C) Garg et al. 2026, Agric. Water Manag. — substitutos do AquaCrop-OSPy (RF, XGBoost), R² > 0,90, transferência entre distritos.
- (C) Garofalo et al. 2026, Agriculture — 5 métodos emulando AquaCrop-GIS (342 casos), MLP melhor (R² 0,966).
- (C) Ren et al. 2026, Agric. Syst. — substituto derivado do AquaCrop para déficit de irrigação mensal.

## Substitutos em outras áreas (método, protocolo, limites)
- (C) Razavi et al. 2012, Water Resour. Res. "Review of surrogate modeling in water resources".
- (C) Hou et al. 2024, Renew. Sustain. Energy Rev. — protocolo para desenvolver e avaliar substitutos de redes neurais; falta de validação documentada.
- (C) Park et al. 2023, J. Build. Perform. Simul. — RMSE baixo não garante reproduzir as relações causais entrada-saída.
- (C) Angione et al. 2022, PLoS ONE — RNA e gradient boosting superam processos gaussianos como substitutos.
- (C) Shang et al. 2023, J. Agric. Econ. — substituto de modelo de fazenda, MLP com melhor compromisso.
- (C) Garzón et al. 2021/2022, Water Resour. Res. — revisão de metamodelos de redes de água urbana; pede bases de benchmark.

## Zotero do autor (relevantes)
- Jones et al. 2003, Eur. J. Agron. "The DSSAT cropping system model" (10.1016/S1161-0301(02)00107-7)
- Hoogenboom et al. 2019 "The DSSAT crop modeling ecosystem" (10.19103/AS.2019.0061.10)
- Boote et al. 1998/2018 "Simulation of crop growth: CROPGRO model"
- Steduto et al. 2009 "AquaCrop: concepts" (10.1007/978-3-642-01132-0_19); Raes et al. 2017/2018 (manual); Steduto et al. 2012 FAO 66
- Kelly & Foster 2021, Agric. Water Manag. "AquaCrop-OSPy" (10.1016/j.agwat.2021.106976)
- Kothari et al. 2022, Eur. J. Agron. "Are soybean models ready for climate change food impact assessments?" (10.1016/j.eja.2022.126482)
- Battisti et al. 2017, Field Crops Res. "Inter-comparison of performance of soybean crop simulation models and their ensemble in southern Brazil" (10.1016/j.fcr.2016.10.004)
- Battisti et al. 2019, Field Crops Res. water deficit patterns (10.1016/j.fcr.2019.06.007)
- Sentelhas et al. 2015, J. Agric. Sci. soybean yield gap in Brazil (10.1017/S0021859615000313)
- Sampaio et al. 2020/2021, J. Agric. Sci. CSM-CROPGRO-Soybean, low latitude, Paragominas (10.1017/S0021859621000204) — ensaio PARA1801
- Nóia Júnior & Sentelhas 2019, Eur. J. Agron. soybean-maize succession (10.1016/j.eja.2018.12.008)
- Silva et al. 2019, Agric. Water Manag. soybean irrigation requirements southern Brazil (10.1016/j.agwat.2019.03.003)
- Monteiro et al. 2018, Int. J. Climatol. NASA/POWER for Brazil (10.1002/joc.5282)
- Duarte & Sentelhas 2020, Int. J. Biometeorol. NASA/POWER and DailyGridded maize (10.1007/s00484-019-01810-1)
- Rodrigues & Braga 2021, Agronomy NASA POWER (10.3390/agronomy11061207)
- von Bloh et al. 2023, Agric. For. Meteorol. ML soybean yield forecasting Brazil (10.1016/j.agrformet.2023.109670)
- Schwalbert et al. 2020, Agric. For. Meteorol. (10.1016/j.agrformet.2019.107886)
- Torsoni et al. 2023, Theor. Appl. Climatol. (10.1007/s00704-022-04341-9)
- Liakos et al. 2018, Sensors ML in agriculture review (10.3390/s18082674)
- Allen et al. 1998 FAO-56; Willmott et al. 2012 (10.1002/joc.2419)
- Beck et al. 2023, Sci. Data Köppen-Geiger 1 km (10.1038/s41597-023-02549-6); Alvares et al. 2013
- Oliveira et al. 2021, Rev. Bras. Meteorol. (autocitação: preenchimento de falhas ETo, 10.1590/0102-77863630001)

## A buscar ainda
- validação cruzada espacial (Roberts et al. 2017; Ploton et al. 2020; Meyer & Pebesma)
- metamodelos de DSSAT/APSIM (Shahhosseini et al. 2019)
- SoilGrids 2.0 (Poggio et al. 2021), Saxton & Rawls 2006, Reichert et al. 2009, NASA POWER, GGCMI calendário (Jägermeyr et al. 2021), ONNX

## Buscas adicionais (Consensus)
- Pohjankukka et al. 2017, Int. J. Geogr. Inf. Sci. — validação cruzada k-fold espacial; CV comum até 40% mais otimista.
- Kattenborn et al. 2022, ISPRS Open J. — amostras autocorrelacionadas inflam o desempenho em até 28%.
- Karasiak et al. 2021/2022, Machine Learning — dependência espacial treino/teste.
- Kumar et al. 2025, Remote Sensing — CV aleatória 6–18% otimista.
- Shahhosseini et al. 2019, Environ. Res. Lett. — metamodelos do APSIM (>3 milhões de simulações), XGBoost RRMSE 13,5%; erro cai 10–40% com mais dados.
- Shahhosseini et al. 2021 (Sci. Rep.) — acoplar APSIM + ML reduz RMSE 7–20%.
- Dokoohaki et al. 2022, Remote Sensing — emuladores do APSIM para otimização bayesiana de parâmetros.
- Akhavizadegan et al. 2021, Sci. Rep. — estimativa de parâmetros dependentes do tempo.
