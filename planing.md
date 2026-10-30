# Emuladores de modelos de cultura: biblioteca e benchmark multi-modelo

Planejamento inicial da pesquisa (30/10/2026). Nasceu da calibração do CROPGRO-Soybean (projeto `calibracao_mg`, artigos ASD e MLCSE) e da discussão sobre transformar o emulador em produto próprio.

## 1. Ponto de partida

### 1.1 O que já existe no projeto DSSAT

O emulador da calibração (`calibracao_mg/src/emulador_fenologia.py`) aprende a relação

> (coeficientes da cultivar, GMR, local, semeadura, clima) → dias até emergência, R1, R5 e R7

do CSM-CROPGRO-Soybean (DSSAT 4.8).

- **Treino:** 2,81 milhões de safras simuladas em 73 locais (2°–30° S), coeficientes e datas por hipercubo latino.
- **Entradas (22):**
  - os coeficientes CSDL, PPSEN, EM-FL, FL-SD, SD-PM e R1PPO;
  - o GMR e o inteiro mais próximo (ecótipo);
  - latitude, altitude, dia da semeadura;
  - fotoperíodo na semeadura e aos 30 e 60 dias;
  - temperatura média e mínima em janelas de 0–30, 30–60, 60–90 e 90–130 dias após a semeadura.
- **Modelo:** um `HistGradientBoostingRegressor` por saída (700 iterações, taxa 0,07, 63 folhas, L2 1,0).
- **Validação:** GroupKFold com **locais inteiros fora do treino**.

Resultados (já no rascunho do MLCSE, seções 3.2 e 4.1):

| Saída | RMSE em locais não vistos (d) | R² |
|---|---|---|
| Emergência | 0,46 | 0,82 |
| R1 | 1,19 | 0,99 |
| R5 | 2,20 | 0,99 |
| R7 | 1,97 | 0,99 |

- Os erros são de 2 a 4 vezes menores que as escalas de erro das observações (3,3–8,4 d).
- **Velocidade:** cerca de 86 µs por safra (4 saídas), contra cerca de 2,4 s no DSSAT via DSSATTools (~3×10⁴ vezes mais rápido). Uma avaliação da verossimilhança leva ~0,5 s.
- **Mais locais valem mais que mais amostras:** passar de 47 para 73 locais (1,69 → 2,81 M safras) levou o RMSE do R1 de 1,42 para 1,19 d e o do R7 de 2,14 para 1,97 d.

Comparação na mesma subamostra (400 mil safras, 5 *folds* por local):

| Emulador | RMSE R1 (d) | RMSE R7 (d) | R² R1 / R7 | Treino (s/fold) | Predição (µs/linha) |
|---|---|---|---|---|---|
| Gradient boosting (usado) | 1,27 | 2,04 | 0,992 / 0,994 | 78–86 | 32–35 |
| MLP 2×128 | **0,80** | **1,00** | 0,997 / 0,998 | 58–74 | 3–5 |
| Ridge | 6,06 | 9,07 | 0,829 / 0,872 | <1 | <1 |

**Efeito na calibração (resultado pouco explorado na literatura):** reavaliar a posterior final com emuladores MLP mudou as predições na mediana em 0,6 d (R1) e 1,1–2,1 d (R5/R7). Ainda assim, a log-posterior caiu **86 unidades**, sobretudo porque as médias multi-local de R8 (as de menor escala de erro, 2,6 d) passaram de 2,2 para 3,3 d de erro. RMSE baixo não garante a mesma inferência.

Arquivos de referência:
- `calibracao_mg/src/`:
  - `emulador_fenologia.py`, `treino_fenologia.py`;
  - `comparar_emuladores.py`, `validar_emulador_fen.py`, `sensibilidade_emulador.py`;
  - `emulador.py` (versão antiga: produtividade, R1 e R7 a partir de 10 parâmetros do Morris).
- `calibracao_mg/resultados/emulador_fenologia/`: `comparacao_emuladores.csv`, `validacao_metricas.csv`, `tabela_treino.parquet`, `modelo_*.joblib`.
- `dssat_zone/src/dssat_direto.py`: execução direta do DSSAT (FileX com vários tratamentos, Summary e OVERVIEW por fase, paralelismo). Dá resultado idêntico ao DSSATTools em 45/45 safras, a ~35 ms por safra.

### 1.2 O que existe fora (busca de 30/10/2026)

- **Interfaces Python por modelo:**
  - PCSE (WOFOST);
  - AquaCrop-OSPy;
  - apsimNGpy (APSIM Next Generation);
  - pyDSSAT e DSSATTools.

  Cada uma roda o seu modelo. Nenhuma treina emuladores nem compara modelos.
- **CROMES v1.0** (Folberth et al., *GMD* 2025): pipeline de emuladores (boosting, árvores, redes) de **um** modelo (EPIC-IIASA) em grade global. Testa a generalização para GCMs fora do treino (R² 0,93–0,97 no milho de sequeiro). Os revisores apontaram possível vazamento treino/teste.
- **Johnston et al. 2023** (*EMS*): ANN, MARS e random forest emulando APSIM-NG (grão-de-bico). R² > 0,95 nos locais de treino, mas **desempenho ruim em locais não vistos**.
- **Gunarathna et al. 2023:** processos gaussianos emulando APSIM-Sugar ficam 1.700–6.900 vezes mais rápidos, mas perdem acurácia quando os parâmetros calibrados passam de 6 para 26.
- **Dokoohaki et al. 2022:** emulador + otimização bayesiana para calibrar o APSIM contra IAF de satélite (estimativa pontual).
- **Implementações diferenciáveis/aprendidas:** WUR-AI/diffWOFOST (WOFOST diferenciável) e WUR-AI/DeepCGM.
- **WOFOSTGym** (RLC 2025): simulador para aprendizado por reforço, não emulador.

**Lacuna:** não há biblioteca nem benchmark que treine e compare emuladores de **vários** modelos de cultura com o **mesmo protocolo**, avaliando generalização espacial, eficiência amostral, custo e impacto na tarefa final (calibração).

## 2. Pergunta e hipóteses

**Pergunta central:** emuladores de modelos de cultura generalizam no espaço? De que isso depende: do modelo, da representação das entradas, do desenho amostral, da família de algoritmo?

- **H1 (representação).** Entradas físicas resumidas em janelas fixas após a semeadura (fotoperíodo, temperatura, chuva, ETo, radiação) generalizam para locais não vistos. Entradas brutas ou identificadores de local não generalizam. Isso explicaria a diferença entre o nosso resultado e o de Johnston et al. 2023.
- **H2 (desenho).** Para a mesma quantidade de simulações, mais locais com menos amostras por local generalizam melhor que poucos locais densamente amostrados.
- **H3 (algoritmo).** MLP supera GB em acurácia e velocidade de predição quando há muitos dados. GB é mais robusto com poucos dados. GP só é viável em baixa dimensão.
- **H4 (tarefa).** O RMSE do emulador não prevê bem o erro induzido na calibração. Os termos de verossimilhança com menor escala de erro são os mais sensíveis às diferenças sistemáticas entre emuladores.
- **H5 (modelo).** A dificuldade de emulação difere entre modelos e saídas. A fenologia (quase determinística em temperatura e fotoperíodo) é mais fácil que a produtividade com estresse hídrico, que depende do caminho do clima diário.

## 3. Desenho experimental

### 3.1 Modelos e cultura

Cultura comum: **soja**, que os quatro modelos simulam.

| Modelo | Interface Python | Linguagem do núcleo | Licença | Custo por safra (a medir) | Prioridade |
|---|---|---|---|---|---|
| DSSAT CROPGRO-Soybean | `dssat_direto.py` (próprio), DSSATTools | Fortran | BSD-3 | ~35 ms (direto) | 1 (pronto) |
| WOFOST (PCSE) | PCSE | Python | EUPL | — | 1 |
| AquaCrop | AquaCrop-OSPy | Python (numba) | Apache-2.0 | — | 2 |
| APSIM NG | apsimNGpy | C#/.NET | uso não comercial: **verificar redistribuição das simulações** | segundos? | 3 |

O objeto de estudo é o **emulador**, não a acurácia agronômica de cada modelo. Cada modelo usa uma parametrização razoável e documentada da soja (a do DSSAT vem da calibração v13). Isso precisa estar dito no artigo para evitar a crítica "os modelos não estão calibrados igualmente".

### 3.2 Locais, clima, solo e manejo harmonizados

- **Locais:** os 73 da calibração, mais pontos do Sul e do Matopiba se necessário. Faixa de 2° a 30° S.
- **Clima:** Xavier BR-DWGD, 1980–2025 (cache já existente em `calibracao_mg/dados/brutos/xavier/`).
- **Solos:** os 3 de Battisti & Sentelhas 2019, convertidos para o formato de cada modelo.
- **Manejo:** datas de semeadura e GMR/cultivar por hipercubo latino; sequeiro e potencial.
- **Saídas comuns:** datas de R1 e R7 (ou equivalentes: floração e maturidade), produtividade de grãos, biomassa e um índice de estresse hídrico na floração/enchimento.

### 3.3 Fatores do benchmark

1. **Algoritmo:** GB (HistGradientBoosting, LightGBM), MLP, GP (esparso, só onde couber), random forest, ridge (referência linear).
2. **Representação das entradas:** (a) janelas físicas fixas; (b) séries diárias brutas com rede 1D/sequencial; (c) clima resumido + identificador do local (mostra o vazamento).
3. **Desenho amostral:** número de locais × amostras por local, com o total de simulações fixo (ex.: 10⁴, 10⁵, 10⁶).
4. **Validação:** aleatória (otimista, como referência); locais fora; anos fora; locais e anos fora; extrapolação de região (treina no Sul, testa no Norte).

### 3.4 Métricas

- **Acurácia:** RMSE, viés, R² por saída e por região; curvas de aprendizado (erro × nº de simulações e × nº de locais).
- **Custo:** tempo de simulação do modelo; tempo de treino; predição em µs por linha; aceleração; ponto de equilíbrio (quantas avaliações compensam o custo de gerar o treino).
- **Tarefa (o diferencial):** calibrar a mesma cultivar sintética com o simulador verdadeiro, em amostra pequena e viável, e com cada emulador. Comparar posterior (deslocamento das medianas, cobertura dos ICs, log-posterior, KL quando possível) e a predição final.
- **Incerteza do emulador:** calibração dos intervalos (GP, ensembles, regressão quantílica) e efeito de propagá-la na verossimilhança.

### 3.5 Alternativa: reimplementar em vez de emular

Reimplementar só o módulo de fenologia do CROPGRO (PHENOL: dias fototérmicos, CSDL/PPSEN, fases) em **JAX**:
- dá resposta exata, sem erro de emulador, em microssegundos;
- dispensa o treino de milhões de safras;
- tem gradientes automáticos, o que permite HMC/NUTS no lugar do MCMC atual.

A comparação emular × reimplementar diferenciável entra no benchmark junto do diffWOFOST. Validação obrigatória contra o executável do DSSAT.

## 4. Biblioteca

**Linguagem: Python.** Rust foi descartado por enquanto: o tempo está nos executáveis dos modelos (Fortran, .NET) e nas bibliotecas de ML, que já rodam em C/C++. A comunidade usa Python e R, e Earth Engine, PyTorch e os normalizing flows não têm equivalente em Rust. Rust/PyO3 só entraria num gargalo específico que apareça depois.

Nome provisório: a definir. Antes de escolher, conferir no PyPI se não colide com pyDSSAT, PCSE etc.

### 4.1 Estrutura

```
<pacote>/
  models/         adaptadores: dssat.py, wofost.py, aquacrop.py, apsim.py
                  (interface comum: preparar entradas, simular em lote, ler saídas padronizadas)
  inputs/         clima (Xavier e genérico), solos (conversão entre formatos), manejo
  design/         hipercubo latino, divisões espaciais/temporais, desenhos locais × amostras
  features/       representações: janelas físicas, fotoperíodo, séries brutas
  emulators/      gb, mlp, gp, rf, ridge, ensembles; interface fit/predict/predict_interval
  evaluate/       validação agrupada, curvas de aprendizado, custo, relatórios
  calibrate/      verossimilhança hierárquica, MCMC, GLUE, NPE (do MLCSE)
  differentiable/ fenologia CROPGRO em JAX (fase posterior)
  benchmark/      configuração dos experimentos do artigo, scripts reprodutíveis
```

### 4.2 API mínima (esboço)

```python
import <pacote> as ce

modelo = ce.models.DSSAT(cultura="soja", executavel=...)
desenho = ce.design.latin_hypercube(parametros, locais, n_por_local=..., semeaduras=...)
sims = modelo.simulate(desenho, clima=ce.inputs.xavier(...), solos=..., n_jobs=8)   # tabela padronizada
X = ce.features.janelas_fisicas(sims, janelas=[(0, 30), (30, 60), (60, 90), (90, 130)])
emu = ce.emulators.MLP().fit(X, sims[["r1", "r7", "produtividade"]])
rel = ce.evaluate.espacial(emu, X, sims, grupos="local", folds=5)
post = ce.calibrate.mcmc(emu, observacoes, priors, ...)
```

### 4.3 Requisitos de qualidade (GMD/JOSS exigem)

- Código aberto (GitHub + DOI no Zenodo), licença compatível com as dos modelos (MIT ou Apache-2.0 para o pacote).
- Testes automáticos, com regressão contra saídas de referência de cada modelo; CI.
- Documentação com tutoriais (um por modelo) e exemplo completo de ponta a ponta.
- Conjunto de simulações do benchmark publicado no Zenodo: é um produto citável por si só.
- Não embutir caminhos fixos nem variáveis de ambiente de pesquisa (como `DELTA8_FIXO`, `PRIOR_LIT`) no código do pacote.

## 5. Produtos e revistas

| Produto | Revista-alvo | Observação |
|---|---|---|
| Artigo principal: biblioteca + benchmark multi-modelo | *Geoscientific Model Development* (modelo/biblioteca + avaliação, código aberto obrigatório) ou *Environmental Modelling & Software* | Pergunta científica (H1–H5), não só engenharia |
| Versão de ML | NeurIPS, trilha *Datasets & Benchmarks* (ambicioso) | Exige conjunto de dados grande e bem documentado |
| Nota de software | *JOSS* ou *SoftwareX* | Rápida; depois da biblioteca estável |
| Fenologia diferenciável + HMC | *EMS*, *Agricultural and Forest Meteorology* ou *GMD* | Possível artigo separado |

**Para não fatiar o mesmo trabalho:** o MLCSE já publica o emulador do DSSAT (treino, validação por local, GB × MLP × ridge, sensibilidade da posterior). O novo artigo **cita** o MLCSE e traz o que é novo: vários modelos, protocolo comum, desenho amostral, representações, avaliação pela tarefa. **Submeter o MLCSE primeiro.**

## 6. Fases

| Fase | Conteúdo | Saída | Critério para seguir |
|---|---|---|---|
| 0 | Esqueleto do pacote; adaptar `dssat_direto.py` e o emulador atual à API; testes de regressão | pacote instalável com DSSAT | DSSAT idêntico ao DSSATTools; emulador reproduz o MLCSE |
| 1 | Adaptador WOFOST (PCSE), harmonização de clima/solo/manejo, soja parametrizada | DSSAT + WOFOST no mesmo protocolo | Simulações coerentes nos 73 locais |
| 2 | Benchmark com 2 modelos: algoritmos × representações × desenho × validação | resultados preliminares de H1–H3 | A pergunta se sustenta (diferenças claras entre fatores) |
| 3 | Avaliação pela tarefa (H4): calibração sintética com simulador × emuladores | resultado de H4 | — |
| 4 | AquaCrop-OSPy | 3 modelos | — |
| 5 | APSIM NG (apsimNGpy), depois de resolver licença e custo computacional | 4 modelos | — |
| 6 | Fenologia CROPGRO em JAX + HMC (opcional) | comparação emular × reimplementar | — |
| 7 | Redação, dados no Zenodo, documentação, submissão | artigo + pacote | — |

## 7. Riscos

- **Escopo:** é um projeto de meses. As fases 0–2 já dizem se vale continuar.
- **Custo do APSIM:** .NET e segundos por safra; milhões de simulações podem levar semanas. Mitigar com menos amostras ou cluster, ou deixá-lo como estudo de caso menor.
- **Harmonização:** cada modelo com parametrização razoável da soja brasileira; documentar e assumir que o foco é o emulador.
- **Licenças:** checar se as simulações do APSIM podem ser redistribuídas.
- **Concorrência:** grupos de Wageningen (diffWOFOST, DeepCGM) e IIASA (CROMES) estão próximos do tema; acompanhar e posicionar.
- **Vazamento de dados no benchmark:** foi a crítica ao CROMES. As divisões precisam separar locais e anos de verdade, inclusive na engenharia de entradas (normalizações ajustadas só no treino).

## 8. Referências e links

- Folberth et al. 2025. CROMES v1.0: a flexible CROp Model Emulator Suite for climate impact assessment. *GMD* 18, 5759. https://gmd.copernicus.org/articles/18/5759/2025/
- Johnston et al. 2023. Comparison of machine learning methods emulating process driven crop models. *Environmental Modelling & Software*. https://research.usq.edu.au/item/y9yy5/comparison-of-machine-learning-methods-emulating-process-driven-crop-models
- Gunarathna et al. 2023 (GP emulando APSIM-Sugar) e Dokoohaki et al. 2022 (APSIM + otimização bayesiana com IAF): já em `_nao_sobe/artigo/referencias_comuns.bib`.
- apsimNGpy: https://www.researchgate.net/publication/400253866_apsimNGpy_A_comprehensive_Python_framework_for_interactive_reproducible_and_scalable_simulations_of_the_APSIM_Next_Generation_model
- WOFOSTGym: https://arxiv.org/html/2502.19308v1
- Lista de modelos de cultura abertos: https://github.com/EDSEL-skoltech/awesome_crop_models
- WUR-AI/diffWOFOST e WUR-AI/DeepCGM (GitHub).
- Rascunho do MLCSE: `_nao_sobe/artigo/mlcse_computacao/main.tex` (seções `sec:emulator` e `sec:res_emu`).
