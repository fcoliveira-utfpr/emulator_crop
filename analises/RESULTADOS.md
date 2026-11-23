# Resultados das análises (para o artigo)

Bases: dssat_v1 e aquacrop_v1 (solo híbrido), 117.720 safras, 1.962 pontos (1.671 na área de soja, 291 fora),
5 dobras por blocos de 5°. Emulador escolhido (v2, `cnn`): datas de desenvolvimento pela média de 4 MLPs por
grupos (sementes 0–3); demais saídas por uma rede convolucional 1-D sobre o clima diário (9 canais: Tmax, Tmin,
radiação, chuva, ETo, VPD, fotoperíodo, estresse do balde, dia após a semeadura; −30 a +170 dias) unida às
entradas da safra. Comparação com v1 (MLP por grupos no DSSAT; MLP por grupos com offset térmico no AquaCrop).

## 04_benchmark.py (validação por bloco, produtividade e maturação)

| Base | Emulador | Produtividade RMSE | R² | Maturação RMSE | ET RMSE | R² mediano das saídas |
|---|---|---|---|---|---|---|
| DSSAT | ridge | 1,122 t/ha | 0,654 | 7,9 d | 63 mm | 0,722 |
| DSSAT | gradient boosting | 0,593 | 0,904 | 4,0 | 35 | 0,911 |
| DSSAT | MLP | 0,448 | 0,945 | 3,4 | 31 | 0,942 |
| DSSAT | MLP por grupos (v1) | 0,454 | 0,944 | 3,3 | 32 | 0,941 |
| DSSAT | **CNN + datas (v2)** | **0,335** | **0,969** | **3,1** | **23** | **0,967** |
| AquaCrop | ridge | 1,137 | 0,639 | 4,5 | 106 | 0,645 |
| AquaCrop | gradient boosting | 0,636 | 0,887 | 4,5 | 53 | 0,893 |
| AquaCrop | MLP | 0,575 | 0,908 | 5,6 | 53 | 0,888 |
| AquaCrop | MLP por grupos + offset (v1) | 0,581 | 0,906 | 4,4 | 52 | 0,889 |
| AquaCrop | **CNN + datas (v2)** | **0,497** | **0,931** | **4,3** | **45** | **0,922** |

- Produtividade: −26% de RMSE no DSSAT e −14% no AquaCrop em relação à v1.
- Treino com todas as safras: v2 ~45 min (CPU, 4 threads) contra 2–3 min da v1; predição no navegador
  ~0,4–0,5 ms por safra (2.000 safras em ~0,7–0,9 s).
- Inflação do erro da validação aleatória sobre a por bloco (mediana das saídas, v1): DSSAT 12–13%, AquaCrop 20%.

## 02_error_structure.py (tabelas em analises/tables, figuras em analises/figures)
- Níveis de aceitação: DSSAT 41 saídas (17 recomendadas, 23 cautela, 1 não; v1: 5/29/7);
  AquaCrop 44 (7 / 20 / 17; v1: 6/16/22). R² mediano 0,962 (0,832–0,997) e 0,922 (−0,024–0,997).
- Produtividade por estrato (RMSE t/ha; % da média):
  - DSSAT: Köppen A 0,297 (7,7%), B 0,305 (13,5%), C 0,376 (11,5%), D 0,321 (13,2%);
    latitude 0–15° 0,278, 15–30° 0,331, 30–45° 0,381, >45° 0,241;
    sem estresse hídrico 0,334 (7,6%) vs sequeiro 0,335 (12,1%); histórico 0,314 vs perturbado 0,380;
    área de soja 0,339 vs fora 0,312; nível baixo 0,337 (viés +0,064), médio 0,358, alto 0,308 (viés −0,060).
  - AquaCrop: A 0,516 (17,3%), B 0,460 (26,5%), C 0,521 (18,2%), D 0,453 (21,5%);
    0–15° 0,625, 15–30° 0,422, 30–45° 0,536, >45° 0,402; sem estresse 0,372 (9,1%) vs sequeiro 0,524 (23,8%);
    histórico 0,467 vs perturbado 0,561; soja 0,487 vs fora 0,553; baixo 0,536 (viés +0,134), alto 0,503 (viés −0,103).
- Erro por região do mundo (países do Natural Earth; RMSE de produtividade t/ha, v1 → v2):

  | Região | Pontos | DSSAT | AquaCrop |
  |---|---|---|---|
  | América do Norte | 346 | 0,573 → 0,439 (R² 0,93) | 0,638 → 0,589 (0,90) |
  | Brasil | 348 | 0,375 → 0,277 (0,97) | 0,477 → 0,459 (0,88) |
  | Argentina, Uruguai, Paraguai | 297 | 0,431 → 0,311 (0,97) | 0,520 → 0,414 (0,96) |
  | Outros da América Latina | 87 | 0,443 → 0,295 (0,98) | 0,518 → 0,429 (0,96) |
  | Europa e Ásia Central | 156 | 0,311 → 0,223 (0,98) | 0,455 → 0,375 (0,96) |
  | África e Oriente Médio | 183 | 0,444 → 0,303 (0,98) | 0,704 → 0,553 (0,94) |
  | Sul da Ásia | 248 | 0,495 → 0,366 (0,94) | 0,632 → 0,533 (0,91) |
  | Leste da Ásia e Oceania | 297 | 0,439 → 0,332 (0,96) | 0,624 → 0,508 (0,92) |

  Redução de 23–33% (DSSAT) e de 4–21% (AquaCrop). Maior erro relativo: América do Norte e Sul da Ásia (DSSAT, 17%)
  e Sul da Ásia (AquaCrop, 33%, médias baixas). Tabela `yield_error_by_region.csv`, figura `fig_regions`.
- Erro por ponto (RMSE t/ha): DSSAT mediana 0,282 (quartis 0,235–0,336; máx 2,25); AquaCrop 0,340 (0,244–0,492; máx 3,11).
- Variabilidade dentro do ponto (sequeiro, clima histórico, 1.962 pontos):
  - DSSAT: r mediano 0,972 (P10 0,872); 94,6% dos pontos com r > 0,8; razão de desvio-padrão emu/sim 0,982 (P10–P90 0,90–1,09);
    médias por ponto r 0,996, RMSE 0,122 t/ha.
  - AquaCrop: r mediano 0,960 (P10 0,705); 80,4% com r > 0,8; razão 0,980 (0,83–1,25); médias r 0,979, RMSE 0,248 t/ha.
- Resposta às perturbações (inclinações com efeito de ponto removido, 35.316 safras perturbadas; t/ha):
  - DSSAT: por °C −0,153 (sim) vs −0,151 (emu); por +10% de chuva +0,193 vs +0,189; por +100 ppm CO2 +0,271 vs +0,270.
  - AquaCrop: por °C −0,195 vs −0,195; por +10% chuva +0,136 vs +0,137; por +100 ppm +0,213 vs +0,214.

## 03_learning_curve.py (v1, MLP; não refeita com a CNN pelo custo de treino)
- Produtividade, RMSE por bloco com 5/10/25/50/100% dos pontos de treino: DSSAT 0,79/0,69/0,54/0,50/0,45 t/ha;
  AquaCrop 0,88/0,80/0,67/0,64/0,58 t/ha. O erro ainda cai entre 50% e 100%.

## 05_sites.py (mapa global dos pontos, `fig_sites`)

| Região | Pontos | Área de soja | Expansão | Blocos de 5° | Países | Safras |
|---|---|---|---|---|---|---|
| América do Norte | 346 | 330 | 16 | 34 | 2 | 20.760 |
| Brasil | 348 | 335 | 13 | 29 | 1 | 20.880 |
| Argentina, Uruguai, Paraguai | 297 | 288 | 9 | 15 | 3 | 17.820 |
| Outros da América Latina | 87 | 61 | 26 | 22 | 8 | 5.220 |
| Europa e Ásia Central | 156 | 110 | 46 | 51 | 24 | 9.360 |
| África e Oriente Médio | 183 | 95 | 88 | 57 | 33 | 10.980 |
| Sul da Ásia | 248 | 197 | 51 | 28 | 6 | 14.880 |
| Leste da Ásia e Oceania | 297 | 255 | 42 | 67 | 14 | 17.820 |

Papel de cada conjunto: pontos da área de soja e de expansão (treino e validação cruzada por blocos de 5°);
7 locais independentes (Londrina, Rio Verde, Sorriso, Passo Fundo, Pergamino, Ames, Harbin), fora do treino,
para a comparação com novas rodadas dos executáveis (`examples/compare_emulator_simulator.ipynb`).

## v3: população de plantas e curvas diárias (dados para o artigo, seção 3 "Plant population and daily curves")

Segunda campanha (`data/dssat_v3`, `data/aquacrop_v3`): mesmas 117.720 safras do v1 com a população
amostrada por safra em 15–50 plantas/m² (hipercubo latino com semente própria) e tabelas diárias. Métricas de
`data/<nome>/benchmark/cnn_block_metrics.csv` e `traj_block_metrics.csv` (blocos de 5°, fora da amostra) e de
`benchmark/validate_sites.py` (7 locais, 60 safras por local, `data/sites_v3/results`).

| | DSSAT v2 (blocos) | DSSAT v3 (blocos) | DSSAT v3 (7 locais) | AquaCrop v2 (blocos) | AquaCrop v3 (blocos) | AquaCrop v3 (7 locais) |
|---|---|---|---|---|---|---|
| Floração (d) | 3,06 | 3,00 (R² 0,975) | 0,99 (0,996) | 1,01 | 1,00 (0,997) | 0,78 (0,997) |
| Maturação (d) | 3,12 | 2,93 (0,985) | 1,64 (0,993) | 4,28 | 4,42 (0,984) | 1,33 (0,998) |
| Produtividade (t/ha) | 0,335 | 0,343 (0,968) | 0,341 (0,951) | 0,497 | 0,510 (0,928) | 0,341 (0,921) |
| ET (mm) | 22,7 | 23,7 (0,978) | 11,0 (0,992) | 44,8 | 46,7 (0,922) | 25,4 (0,930) |
| Curva folha / dossel | – | 0,055 (0,976) | 0,035 (0,990) | – | 0,098 (0,930) | 0,056 (0,979) |
| Curva biomassa | – | 0,107 (0,950) | 0,048 (0,988) | – | 0,058 (0,974) | 0,034 (0,991) |
| Curva grãos | – | 0,026 (0,991) | 0,019 (0,995) | – | 0,046 (0,979) | 0,022 (0,995) |
| Curva estresse hídrico | – | 0,084 (0,799) | 0,061 (0,756) | – | 0,144 (0,656) | 0,111 (0,650) |

- Mediana da razão RMSE nos 7 locais / RMSE da ficha (todas as saídas): 0,62 (DSSAT) e 0,63 (AquaCrop).
- Resposta à população (fora da amostra, desvios da média do local, por 10 plantas/m²): DSSAT sequeiro
  +61 simulado / +63 emulado kg/ha, sem estresse +128 / +124; AquaCrop +0,133 t/ha nos dois. Mediana da
  produtividade de sequeiro simulada de 15 para 50 plantas/m²: DSSAT 2,45 → 2,70 t/ha, AquaCrop 1,89 → 2,30.
- 7 locais, mesmas safras a 15 e 50 plantas/m²: ganho médio DSSAT sequeiro 0,31 simulado / 0,30 emulado
  t/ha (sem estresse 0,51 / 0,49), AquaCrop 0,53 / 0,51 (0,56 / 0,56); correlação safra a safra do ganho
  DSSAT 0,91 / 0,95, AquaCrop 0,55 / 0,85.
- Pior local em produtividade: Ames (DSSAT 0,68 t/ha, AquaCrop 0,60 t/ha, viés positivo).

## Monitoramento (figura do app, `fig_app.mjs`, 23/11/2026)

Londrina, DSSAT v3, semeadura 20/10/2026, clima observado até 22/11 e previsão até 08/12, 35 anos (1991–2025)
com a previsão sazonal: produtividade esperada 5,64 t/ha (80 %: 4,86–5,88), −0,44 sobre os 6,08 da semeadura;
yield gap 0; chuva desde a semeadura 125 mm (anos passados 134, 77–238). Ano mais parecido 1995 (depois 2018 e
2005): 402 mm e Tmax 28,1 °C desde 30 dias antes da semeadura, contra 377 mm e 28,3 °C em 1995 e 149 mm e
34,2 °C no menos parecido (1985); cenário completado com 1995: 5,61 t/ha (100 % do potencial). Projeção só
com anos passados: mediana 6,0–6,1 t/ha até a maturidade, 80 % dos caminhos abrindo para 5,5–6,3 t/ha.

