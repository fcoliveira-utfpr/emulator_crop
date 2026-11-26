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


## 06_hindcast.py (hindcast do monitoramento, 25/11/2026)

Scripts: `benchmark/hindcast_sims.py` (DSSAT e AquaCrop nas safras do hindcast, com o clima real) e
`web/tests/hindcast_monitor.mjs` (cenários com o `monitor.js` do app, sem mudanças). 7 sítios independentes ×
safras de 1995 a 2024 × DSSAT v3 e AquaCrop v3; semeadura no dia GGCMI do sítio (31/out Londrina e Sorriso,
15/nov Rio Verde, 30/nov Passo Fundo e Pergamino, 2–3/mai Ames e Harbin), todo ano no mesmo dia e mês; cultivar
típica da latitude sem perturbação (DSSAT) e meio da faixa dos parâmetros com o tempo térmico do calendário
(AquaCrop), a mesma para emulador e simulador (`data/hindcast/sims/cultivars.json`); 30 plantas/m²; CO₂ observado.
Para o ano-alvo Y, o clima de Y é conhecido até k dias após a semeadura e os outros 40 anos (1984–2025,
deixa-um-ano-fora) completam o ciclo, em sequeiro e sem estresse. Modo "anos passados" (sem previsão sazonal).
Referências: (A) o emulador com o clima completo de Y (mede só o método de cenários); (B) o modelo de cultura
com o clima de Y (emulação + cenários). ~375 mil safras emuladas em 12 min (Node) e 840 simuladas em 40 s.
Tabelas `hindcast_by_das.csv`, `hindcast_by_site.csv`, `hindcast_seasons.csv`; figuras `fig_hindcast` e
`fig_hindcast_case`.

Emulador × modelo de cultura nas 210 safras de sequeiro por modelo (clima completo): RMSE 0,21 t/ha (DSSAT,
média 4,38, DP 1,67) e 0,33 t/ha (AquaCrop, média 2,47, DP 0,99).

| Dias após a semeadura | 0 | 30 | 45 | 60 | 75 | 90 | 120 |
|---|---|---|---|---|---|---|---|
| DSSAT: MAE da mediana, ref. A (t/ha) | 0,85 | 0,79 | 0,71 | 0,61 | 0,47 | 0,33 | 0,06 |
| DSSAT: MAE do ano mais parecido (A) | 1,11 | 1,06 | 0,91 | 0,82 | 0,65 | 0,42 | 0,09 |
| DSSAT: MAE da mediana, ref. B | 0,89 | 0,85 | 0,76 | 0,66 | 0,53 | 0,40 | 0,16 |
| DSSAT: r das anomalias dentro do sítio (A) | 0,10 | 0,33 | 0,49 | 0,61 | 0,80 | 0,90 | 1,00 |
| DSSAT: skill do CRPS vs semeadura (A) | 0 | 0,05 | 0,14 | 0,25 | 0,43 | 0,60 | 0,92 |
| DSSAT: cobertura 10–90%, A / B / B com erro de emulação | 74/71/79 | 74/68/78 | 75/68/80 | 74/70/81 | 73/65/85 | 74/62/88 | 75/32/96 |
| DSSAT: Brier skill, safras < P20 (A) | −0,09 | −0,06 | −0,03 | 0,10 | 0,30 | 0,61 | 0,84 |
| AquaCrop: MAE da mediana, ref. A | 0,62 | 0,43 | 0,32 | 0,21 | 0,12 | 0,08 | 0,03 |
| AquaCrop: MAE do ano mais parecido (A) | 0,77 | 0,57 | 0,42 | 0,28 | 0,17 | 0,10 | 0,04 |
| AquaCrop: MAE da mediana, ref. B | 0,66 | 0,47 | 0,37 | 0,28 | 0,22 | 0,19 | 0,18 |
| AquaCrop: r das anomalias (A) | 0,25 | 0,72 | 0,85 | 0,93 | 0,98 | 0,99 | 1,00 |
| AquaCrop: skill do CRPS (A) | 0 | 0,30 | 0,47 | 0,65 | 0,79 | 0,87 | 0,95 |
| AquaCrop: cobertura, A / B / B com erro | 77/72/88 | 77/71/90 | 79/69/90 | 80/64/94 | 78/54/94 | 77/39/94 | 78/20/94 |
| AquaCrop: Brier skill, safras < P20 (A) | −0,03 | 0,24 | 0,39 | 0,53 | 0,67 | 0,85 | 0,87 |

Ciclo mediano: 122 dias (DSSAT) e 104 dias (AquaCrop).

- O acerto cresce com o clima conhecido, mais cedo no AquaCrop (produtividade guiada pela transpiração acumulada)
  do que no DSSAT, cuja produtividade se decide no enchimento de grãos (60–110 dias). Na semeadura, a mediana dos
  cenários é a climatologia (r das anomalias 0,1–0,25).
- A faixa de 80% cobre 73–80% das safras na referência A. Contra o modelo de cultura (B), a cobertura cai no fim
  do ciclo (para 20–32% aos 120 dias), porque a faixa só tem a incerteza do clima e o erro da emulação passa a
  dominar (piso de ~0,16–0,18 t/ha no MAE). Somando em quadratura o RMSE da validação por blocos (0,343 e
  0,510 t/ha) às semilarguras, a cobertura volta a 78–96%: proposta para o app.
- Até ~60 dias, o MAE contra o modelo de cultura é só 0,04–0,07 t/ha maior que contra o emulador: a incerteza do
  clima domina; depois, a emulação.
- Viés positivo da mediana no início (+0,35 t/ha no DSSAT na semeadura): a distribuição da produtividade é
  assimétrica à esquerda (quebras), e a mediana fica acima da média.
- **O cenário do ano mais parecido é pior que a mediana em todas as datas** (DSSAT: 1,11 × 0,85 na semeadura;
  0,82 × 0,61 aos 60 dias). Serve como análogo para ilustrar, não como previsão pontual.
- Estudo de caso: Passo Fundo, safra 2021/22 (seca da La Niña; 144 mm de chuva nos 60 dias após a semeadura contra
  a mediana de 283 mm dos outros anos). DSSAT: 1,67 t/ha simulado e 1,82 emulado; a expectativa caiu de 4,73
  (semeadura) para 3,21 (30 dias), 2,52 (45) e 1,98 (60). AquaCrop: o modelo simulou quebra total (0,00 t/ha) e o
  emulador 1,09 t/ha; a expectativa caiu de 2,77 para 1,08 aos 60 dias. A quebra total do AquaCrop é o caso de
  regressão à média na cauda baixa (R3 do plano).
- O emulador do AquaCrop dá produtividades levemente negativas em quebras totais (mín. −0,07 t/ha): cortar em 0
  na biblioteca e no app.

## 07_folds_years.py (incerteza entre dobras e vazamento temporal, 25/11/2026)

RMSE fora da dobra (v3, validação por blocos), IC de 95% por bootstrap de blocos e DP entre as 5 dobras
(`fold_uncertainty.csv`); "v1" = MLP v1 retreinado nos dados v3 com as mesmas dobras.

| Modelo | Saída | CNN: RMSE [IC 95%] ± DP dobras | MLP v1: RMSE [IC 95%] ± DP |
|---|---|---|---|
| DSSAT | produtividade (t/ha) | 0,343 [0,319–0,368] ± 0,024 | 0,455 [0,430–0,485] ± 0,030 |
| DSSAT | maturação (d) | 2,92 [2,34–3,76] ± 0,80 | 3,07 [2,59–3,74] ± 0,86 |
| DSSAT | ET (mm) | 23,7 [19,5–28,3] ± 3,4 | 32,5 [27,9–37,5] ± 4,2 |
| AquaCrop | produtividade (t/ha) | 0,510 [0,462–0,576] ± 0,047 | 0,591 [0,546–0,644] ± 0,057 |
| AquaCrop | maturação (d) | 4,42 [3,89–5,04] ± 0,68 | 4,51 [3,95–5,12] ± 0,67 |
| AquaCrop | ET (mm) | 46,7 [39,3–54,3] ± 10,1 | 54,7 [48,4–61,1] ± 10,7 |

- A CNN é melhor que o MLP v1 em produtividade e ET nas 5 dobras dos dois modelos (pareado); na maturação a
  diferença é pequena e dentro da variação entre dobras.

Vazamento temporal (`temporal_leakage.csv`, MLP v1, treino reduzido igual nas duas variantes): separar também
por anos (teste = blocos da dobra num grupo de anos; treino sem esses blocos e sem esses anos) mudou o RMSE
médio da produtividade em −0,8% (DSSAT, 0,463 → 0,459) e +1,0% (AquaCrop, 0,591 → 0,596); ET ±1%; maturação
+13% no DSSAT (puxado pela dobra 1: 4,47 → 6,39 d) e +0,4% no AquaCrop. Conclusão: não há vazamento temporal
relevante na produtividade; a validação só por blocos é adequada.

## 08_tail_risk.py (cauda inferior e risco, 25/11/2026)

Safras de sequeiro, clima histórico, predições fora da dobra; por ponto, limiar = P20 simulado
(`tail_risk.csv`, `tail_risk_by_site.csv`).

| | DSSAT | AquaCrop |
|---|---|---|
| Safras (pontos) | 65.846 (1.962) | 65.841 (1.962) |
| Fração das safras emuladas abaixo do P20 simulado (ideal 20%) | 21,1% (P10–P90 entre pontos 12–28%) | 22,8% (10–34%) |
| Acerto "safra ruim" (< P20) / alarme falso | 78,3% / 6,0% | 62,7% / 10,7% |
| P10 por ponto: viés / RMSE / r | +0,014 / 0,176 t/ha / 0,989 | +0,034 / 0,315 t/ha / 0,949 |
| Viés da mediana por ponto | +0,012 | +0,022 |
| Quebra (< 1 t/ha): fração sim / emu | 24,1% / 23,4% | 30,8% / 29,5% |
| Quebra: acerto / alarme falso | 90,0% / 2,2% | 87,9% / 3,6% |

- Desfecho A do plano (R3), com ressalva: no nível do ponto (distribuição de risco), o emulador reproduz o
  P10 e a frequência de quebras quase sem viés; safra a safra, a classificação "ruim" erra 22% (DSSAT) e 37%
  (AquaCrop) das safras ruins. O erro relativo alto no tercil inferior vem de denominadores pequenos, não de
  viés da distribuição. Usos de risco: sustentados para probabilidades por local; não para safras individuais.

## openmeteo_vs_power.mjs (R7, 25/11/2026)

7 sítios independentes, 2015–2024, Open-Meteo (arquivo ERA5) × NASA POWER, diário
(`data/hindcast/openmeteo_power_daily.csv`, `openmeteo_power_effect.csv`). Mediana entre sítios (mín.–máx.):

| Variável | Viés | RMSE |
|---|---|---|
| Tmax (°C) | −1,14 (−1,86 a −0,02) | 2,27 (1,66–2,71) |
| Tmin (°C) | +0,75 (−0,38 a 1,85) | 1,39 (1,25–3,15) |
| Radiação (MJ/m²/d) | +0,09 (−0,60 a 0,72) | 2,64 (2,19–2,82) |
| Chuva (mm/d) | 0,00 (−0,37 a 0,52) | 6,75 (3,72–8,01) |
| Ponto de orvalho (°C) | −0,70 (−1,62 a 0,48) | 1,67 (1,45–2,97) |
| Vento (m/s) | −0,16 | 0,70 |

Efeito na produtividade esperada do monitoramento (|mudança|, mediana / P90, t/ha), aos 30, 60 e 90 dias:
- Últimos 5 dias do Open-Meteo (como no app): DSSAT 0,014/0,14, 0,038/0,32, 0,034/0,15; AquaCrop 0,021/0,22,
  0,021/0,20, 0,011/0,04. Pequeno diante da faixa de 80% e do erro de emulação.
- Toda a parte observada do Open-Meteo: DSSAT 0,09/0,57, 0,16/1,19, 0,20/1,49; AquaCrop 0,17/0,58, 0,21/0,93,
  0,22/0,94. Justifica usar NASA POWER sempre que disponível e o Open-Meteo só para cobrir a defasagem.
