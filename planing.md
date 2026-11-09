# Emuladores de modelos de cultura: biblioteca e benchmark multi-modelo

Planejamento da pesquisa. Versão inicial em 30/10/2026; revisada em 08/11/2026.

Nasceu da experiência com o CROPGRO-Soybean no projeto `calibracao_mg` (artigos ainda não publicados) e da ideia de transformar o emulador em produto próprio.

## 0. Princípios

1. **Nenhum resultado de outro repositório entra aqui.** Os trabalhos anteriores (`calibracao_mg`, `dssat_zone`) não estão publicados. Daqui só vem **código**, portado e testado neste repositório. Todos os números (simulações, métricas, modelos treinados) são regerados aqui, com scripts reprodutíveis.
2. **Para cada modelo de cultura, achar o melhor caminho de emulação e entregar emuladores consolidados.** O melhor caminho combina algoritmo, representação das entradas e desenho amostral. O benchmark serve para escolher. O produto final é um conjunto de emuladores pré-treinados e validados por modelo.
3. **Todas as saídas que o programa do modelo fornece devem estar disponíveis**, tanto na simulação (adaptadores) quanto, na medida do possível, na emulação. Ver seção 3.
4. **Cobertura global.** Locais, clima e solos cobrem todos os ambientes onde a soja é (ou pode ser) cultivada no mundo, não só o Brasil. Os dados de entrada são globais e abertos. Ver seção 4.2.
5. **O produto final é uma biblioteca Python** construída com os emuladores vencedores. Ela é leve: o usuário prevê com o emulador sem instalar os modelos de cultura. O benchmark é o meio para chegar a ela. Ver seção 5.
6. **Entradas padronizadas de bases globais; dados locais só na validação** (decisão de 08/11/2026).
   - **Treino e benchmark** usam, em **todos** os pontos (inclusive nos sítios experimentais), as mesmas bases globais: clima do NASA POWER, solo do SoilGrids, calendário de semeadura do GGCMI e parâmetros de cultivar da revisão. Não entram solo medido, clima de estação nem manejo local.
   - **Por quê:** a comparação entre modelos, locais e emuladores precisa usar a mesma fonte e o mesmo tratamento em todo o globo. A biblioteca também vai usar essas bases, então o emulador aprende a resposta do modelo às entradas que o usuário de fato terá. Vieses das bases (ex.: o SoilGrids pode subestimar a retenção de água em solos tropicais muito argilosos) são iguais em todo lugar e não afetam a comparação.
   - **Ordem do projeto:** primeiro os emuladores (benchmark e consolidação), depois a biblioteca. **A validação local com valores reais vem depois**, numa fase própria. Ela compara as previsões feitas com entradas globais com observações dos sítios experimentais e mede quanto se ganha trocando as entradas globais por dados locais (solo medido, estação meteorológica).

## 1. Ponto de partida

### 1.1 Experiência prévia (só motivação, não citável)

O trabalho anterior emulou a fenologia (emergência, R1, R5 e R7) do CROPGRO-Soybean a partir de:
- coeficientes da cultivar;
- GMR;
- local e data de semeadura;
- clima resumido em janelas fixas após a semeadura.

As lições abaixo viram **hipóteses a retestar aqui**, não resultados:
- Entradas físicas em janelas fixas pareceram generalizar para locais fora do treino (→ H1).
- Mais locais pareceram valer mais que mais amostras por local (→ H2).
- A **rede neural (MLP) saiu mais exata e mais rápida na predição** que o gradient boosting; o ridge ficou muito atrás (→ H3).
- Trocar de emulador mudou a posterior da calibração mais do que o RMSE sugeria (→ H4).
  - **Cuidado:** a comparação foi feita reavaliando, com a MLP, uma posterior obtida com o GB. Isso favorece o GB, porque as amostras exploram os vieses dele. Aqui, cada emulador calibra do zero.

Código a portar (somente código, revisado e com testes):
- `dssat_zone/src/dssat_direto.py`: execução direta do DSSAT (FileX com vários tratamentos, paralelismo, leitura de saídas). Base do adaptador DSSAT.
- `calibracao_mg/src/emulador_fenologia.py` e `treino_fenologia.py`: engenharia de entradas (fotoperíodo e janelas de temperatura). Base de `features/`.
- Verossimilhança hierárquica e MCMC do MLCSE: base de `calibrate/`.
- Clima: no outro projeto era o Xavier (só Brasil). Aqui ele é substituído por bases globais (4.2), baixadas por script deste repositório.

**Parametrização da soja no DSSAT:** não usar a cultivar calibrada (v13) do outro projeto, que é resultado não publicado. Usar as cultivares padrão do `SBGRO048.CUL` (ou da versão vigente) e amostrar os coeficientes em faixas documentadas.

### 1.2 O que existe fora (busca de 30/10/2026, a ampliar)

- **Interfaces Python por modelo:** PCSE (WOFOST), AquaCrop-OSPy, apsimNGpy (APSIM NG), pyDSSAT e DSSATTools. Cada uma roda o seu modelo, mas nenhuma treina emuladores nem compara modelos.
- **Emuladores de vários modelos globais (a citar e diferenciar):**
  - Blanc & Sultan 2015 e Blanc 2017 (*AFM*): emuladores estatísticos de produtividade de vários modelos globais em grade, inclusive para soja.
  - Franke et al. 2020 (*GMD*): emuladores do GGCMI Phase 2, superfícies de resposta a CO₂, temperatura, água e N.
  - Esses trabalhos emulam a resposta da **produtividade** em grade global. Não avaliam locais fora do treino, desenho amostral, impacto na calibração nem as saídas completas.
- **CROMES v1.0** (Folberth et al., *GMD* 2025): pipeline de emuladores de **um** modelo (EPIC-IIASA), com foco em produtividade. Os revisores apontaram possível vazamento treino/teste.
- **Johnston et al. 2023** (*EMS*): ANN, MARS e random forest emulando o APSIM-NG (grão-de-bico). Desempenho ruim em locais não vistos.
- **Gunarathna et al. 2023:** processos gaussianos emulando o APSIM-Sugar. Perdem acurácia quando os parâmetros passam de 6 para 26.
- **Dokoohaki et al. 2022:** emulador com otimização bayesiana para calibrar o APSIM contra IAF.
- **Implementações diferenciáveis ou aprendidas:** WUR-AI/diffWOFOST e WUR-AI/DeepCGM. O DeepCGM aprende trajetórias diárias, o mais perto da ideia de saídas completas; conferir quantas variáveis cobre.
- **WOFOSTGym** (RLC 2025): simulador para aprendizado por reforço, não emulador.
- **A verificar:** se existe emulador de **todas** as saídas de um modelo de cultura (resumo da safra e séries diárias). Pelo que se viu até agora, os trabalhos emulam de 1 a 5 alvos. Fazer busca dirigida (surrogates multi-saída, emulação funcional de séries temporais, emuladores de modelos de superfície terrestre como possível análogo).

**Posicionamento em relação ao GGCMI:** com a escala global, o GGCMI (e os emuladores de Blanc e de Franke) passa a ser o vizinho mais próximo. A diferença precisa ficar clara:
- o GGCMI ajusta, em cada célula da grade, uma superfície de resposta a perturbações do clima, com a cultivar e o manejo fixos por célula;
- aqui, um **único** emulador global recebe clima diário resumido, solo, manejo e **parâmetros da cultivar**. Ele vale para qualquer ponto, inclusive fora do treino, e pode ser usado na calibração.

**Lacuna:** não há biblioteca nem benchmark que, com o **mesmo protocolo** para **vários** modelos de cultura, em **escala global** e na resolução de campo e cultivar:
1. emule **todas as saídas** de cada modelo;
2. avalie a generalização com locais e anos realmente fora do treino;
3. avalie a eficiência amostral e o custo;
4. meça o impacto na tarefa final (calibração);
5. entregue emuladores consolidados prontos para uso.

## 2. Pergunta e hipóteses

**Pergunta central:** para cada modelo de cultura, qual é o melhor caminho de emulação, e os emuladores generalizam no espaço e no tempo para todas as saídas?

- **H1 (representação).** Entradas físicas resumidas em janelas generalizam para locais não vistos; o identificador do local não generaliza. Testar dentro do mesmo modelo e da mesma saída, para não confundir com efeito de modelo ou de cultura. Comparar três tipos de janela:
  - janelas fixas em dias após a semeadura;
  - janelas **ancoradas na fenologia** (ex.: R1 ± n dias, com emulador em dois estágios);
  - séries diárias com rede sequencial.

  Hipótese adicional: para a produtividade em sequeiro, as janelas ancoradas na fenologia superam as fixas.
- **H2 (desenho).** Com o total de simulações fixo, mais locais com menos amostras por local generalizam melhor. Locais e anos de clima são eixos separados. O teste sempre usa os mesmos locais e anos reservados.
- **H3 (algoritmo).** Com muitos dados, a MLP supera o GB em acurácia e velocidade. O GB é mais robusto com poucos dados. A família vencedora pode mudar entre modelos e saídas, e é isso que a seleção por modelo (3.4) decide.
- **H4 (tarefa).** O RMSE do emulador não prevê bem o erro na calibração. Os termos da verossimilhança com menor escala de erro são os mais sensíveis a vieses sistemáticos.
- **H5 (modelo e saída).** A dificuldade de emulação difere entre modelos e saídas: fenologia é mais fácil que produtividade com estresse hídrico, e escalares da safra são mais fáceis que trajetórias diárias. Parte da diferença vem da estrutura do modelo (o AquaCrop, por exemplo, não tem fotoperíodo). Isso precisa ser assumido no texto.
- **H6 (multi-saída).** Um único emulador multi-saída (rede com todas as saídas) perde pouca acurácia em relação a emuladores dedicados por saída e é muito mais barato de treinar, guardar e usar. Também preserva melhor a coerência entre saídas (ex.: R1 < R5 < R7, grãos ≤ biomassa).

## 3. Saídas completas

### 3.1 O que cada modelo fornece

| Modelo | Resumo da safra | Séries diárias |
|---|---|---|
| DSSAT | `Summary.OUT` (dezenas de variáveis: datas de fases, produtividade, biomassa, N, água, etc.), `OVERVIEW.OUT` (estresse por fase) | `PlantGro`, `SoilWat`, `ET`, `PlantN`, `SoilNi`, `Weather` e outros, conforme as opções do FileX |
| AquaCrop | estatísticas finais (produtividade, biomassa, ET, água usada, datas das fases) | fluxos de água, crescimento da cultura (cobertura do dossel, biomassa) e balanço diário |

### 3.2 Nos adaptadores (simulação)

- O adaptador lê **todas** as saídas que o modelo gera, com os nomes nativos (`DSSAT.HWAM`, `AQUACROP.DryYield`, etc.).
- Uma camada separada mapeia um **subconjunto harmonizado** entre modelos (floração, maturidade, produtividade, biomassa, ET, índice de estresse) para o benchmark comparativo.
- A configuração diz quais arquivos e variáveis guardar, com o padrão "tudo".
- **Armazenamento:** milhões de safras × ~150 dias × centenas de variáveis vão a centenas de GB. Estratégia:
  - escalares da safra para todas as simulações;
  - séries diárias completas para uma subamostra;
  - Parquet particionado por modelo e local, com compressão.

### 3.3 Na emulação

- **Nível 1, escalares da safra:** todas as variáveis numéricas do resumo. Rede multi-saída como candidata principal (H6); GB por saída como referência.
- **Nível 2, trajetórias diárias:** emulação funcional. Candidatas:
  - redução de dimensão (PCA ou autoencoder) da curva e emulação dos coeficientes;
  - rede sequencial (LSTM, CNN 1D ou transformer) do clima diário para as variáveis diárias.
- **Saídas especiais, com tratamento explícito:**
  - datas não atingidas (cultura que não matura): emulador de classificação e emulador condicional;
  - variáveis constantes ou quase constantes: detectar e reportar, sem emular;
  - códigos e categorias: classificação;
  - variáveis acumuladas: prever incrementos ou impor monotonicidade.
- **Cobertura:** para cada saída, reportar a acurácia em locais fora do treino. Saídas que não se emulam bem são marcadas como "não recomendadas", não escondidas.

## 4. Desenho experimental

### 4.1 Modelos e cultura

Cultura comum: **soja**.

| Modelo | Interface Python | Núcleo | Licença | Custo por safra (a medir) | Prioridade |
|---|---|---|---|---|---|
| DSSAT CROPGRO-Soybean | adaptador próprio (portado de `dssat_direto.py`), DSSATTools como referência | Fortran | BSD-3 | ~35 ms esperado | 1 |
| AquaCrop | adaptador próprio sobre o **executável oficial AquaCrop v7** (modo de projeto em lote, leitura de todas as saídas) | Fortran | a verificar | — | 2 |

**WOFOST e APSIM ficaram fora** (decisão de 08/11/2026). Com dois modelos, o contraste fica bem definido:
- **DSSAT:** modelo de processos, com balanço de carbono, fotoperíodo e grupos de maturidade;
- **AquaCrop:** modelo guiado pela água (produtividade da água, cobertura do dossel), com fenologia por graus-dia e sem fotoperíodo.

A biblioteca é desenhada para receber outros modelos depois.

**AquaCrop: executável oficial v7** (decisão de 08/11/2026). Como o DSSAT, ele roda por arquivos de entrada e saída, então o adaptador segue o mesmo padrão do `dssat_direto.py`: gerar os arquivos de projeto em lote, rodar em paralelo e ler todas as saídas. O AquaCrop-OSPy fica só como referência para conferir resultados.

**Versões fixas:** DSSAT 4.8.x e a versão do AquaCrop registradas no pacote e nos metadados de cada simulação.

### 4.1.1 Parâmetros da cultivar a partir da literatura

Os parâmetros não vêm de calibração própria (princípio 1). Vêm de duas fontes:
1. **Do próprio programa:** as cultivares padrão do `SBGRO048.CUL` e do ecótipo do DSSAT; a cultura padrão de soja do AquaCrop.
2. **De artigos que calibraram os modelos para soja**, em várias regiões e grupos de maturidade.

Protocolo:
- **Revisão sistemática:** busca em Scopus, Web of Science e Google Scholar por "CROPGRO-Soybean" + calibração e "AquaCrop" + soja; triagem com critérios explícitos.
- **Base de coeficientes:** de cada artigo, extrair coeficientes, região, latitude, grupo de maturidade, versão do modelo e tipo de dado usado na calibração.
- **Distribuições de amostragem:** a base define as faixas e, quando possível, a **distribuição conjunta**. Coeficientes correlacionados (ex.: CSDL e PPSEN) não são amostrados de forma independente, para não gerar cultivares sem sentido.
- **Produto próprio:** a base de coeficientes publicados é publicável e citável por si só, como conjunto de dados no Zenodo ou anexo do artigo.

### 4.1.2 Checagem de plausibilidade

As simulações não são calibradas, mas precisam ser plausíveis. Por região, comparar a distribuição da produtividade simulada (potencial e sequeiro) com produtividades observadas:
- FAOSTAT, por país;
- GDHY (Iizumi), em grade;
- estatísticas nacionais (ex.: IBGE, USDA).

O objetivo é só garantir ordens de grandeza, não ajustar o modelo. Combinações implausíveis são reportadas e, se for o caso, as faixas são revistas.

### 4.1.3 Detalhes de manejo e condições iniciais

- **Água inicial do solo:** aquecimento de 1 ano antes da safra ou fração fixa da capacidade de campo. Pesa muito na produtividade de sequeiro, então precisa ser decidido e documentado.
- **Nitrogênio:** fixação biológica ligada no DSSAT ou balanço de N desligado. A escolha precisa ser coerente com o AquaCrop, que não simula N do mesmo jeito.
- **Densidade e espaçamento** de semeadura: fixos ou por hipercubo latino, dentro de faixas da literatura.
- **Irrigação no potencial:** automática, com o mesmo critério nos dois modelos.

**Implementado na versão provisória do desenho** (`cropemu_bench.design`, 08/11/2026). Tudo o que o usuário da biblioteca não saberia informar fica fixo:
- água inicial a 50% da água disponível, 30 dias antes da semeadura (esses 30 dias funcionam como aquecimento curto);
- balanço de N desligado (sem estresse de N);
- 30 plantas/m², 50 cm entre linhas;
- potencial = balanço hídrico desligado; evapotranspiração por Priestley-Taylor (padrão do DSSAT).

### 4.1.4 Desenho das safras (provisório)

Um hipercubo latino por ponto. Padrão: 20 safras por ponto e semente fixa. Cada safra tem:
- **Ano:** 1985–2024. O de 1984 fica fora para sobrar margem antes do início.
- **Semeadura:** dia do GGCMI ± 30 dias.
- **Grupo de maturidade (GM) contínuo:** GM típico da latitude ± 2.
  - Regra provisória do GM típico por latitude: trópicos ~9, 23° ~6,5, 40° ~3, 50° ~000.
  - Escala: 000 = −2, 00 = −1, 0 = 0, depois 1 a 10.
- **Coeficientes da cultivar:**
  - **Base:** as cultivares padrão do próprio DSSAT, uma por grupo de maturidade no `SBGRO048.CUL`, interpoladas linearmente no GM.
  - **Perturbações independentes** em 13 coeficientes: CSDL ± 0,3 h; PPSEN ×0,8–1,2; EM-FL, FL-SH, FL-SD, SD-PM, FL-LF, LFMAX, SLAVR, SIZLF, WTPSD, SFDUR e SDPDV ×0,85–1,15. Cada um é recortado às linhas MINIMA/MAXIMA do `.CUL`.
  - O ecótipo é o do GM inteiro mais próximo.
  - **Será trocado** pelas distribuições da revisão sistemática (4.1.1) quando ela estiver pronta.
- **Regime:** 20% potencial e 80% sequeiro.
- **Clima perturbado em 30% das safras:** ΔT de −1 a +4 °C (máxima e mínima), chuva ×0,7–1,3, CO₂ de 350 a 800 ppm. Nas demais, o CO₂ segue a série observada (Mauna Loa).

**Teste de ponta a ponta** (`cropemu_bench.pipeline`): 30 pontos globais × 10 safras, todos os pontos com clima e solo válidos.
- **DSSAT:** com um arquivo de clima curto por safra (do dia anterior ao início até +450 dias, com o TAV/AMP da série completa), ~40 ms por safra com 8 processos nesta máquina de 4 núcleos, com resultados idênticos aos da série de 42 anos. Com a série inteira, eram ~125 ms.
- **Solo:** ~1,3 s por leitura remota, por causa da latência. As leituras foram paralelizadas em 32 threads.

### 4.2 Locais, clima, solo e manejo (global)

**Locais: núcleo em sítios com dados de experimentos** (decisão de 08/11/2026)

Dois grupos de pontos:

1. **Sítios experimentais (núcleo).** Locais onde houve experimentos de campo com soja publicados, com coordenadas.
   - **Fontes:**
     - os próprios artigos da revisão sistemática (fase 0a): quem calibrou o DSSAT ou o AquaCrop informa o local do experimento. A mesma triagem rende coeficientes e sítios;
     - redes públicas de ensaios de cultivares, a verificar acesso e coordenadas: USDA Uniform Soybean Tests (EUA e Canadá), RECSO/INTA (Argentina), ensaios VCU e redes estaduais no Brasil, ensaios na China e na Índia;
     - bases de referência agronômica (ex.: estações do Global Yield Gap Atlas para soja), como complemento.
   - **Base de sítios** (`sites.csv`): id, lat, lon, país, fonte (DOI ou relatório), anos, tipo de dado observado (fenologia, produtividade, biomassa, água no solo) e se os dados são públicos.
   - **Nas simulações, os sítios usam só as entradas globais** (princípio 6). Deles vêm apenas as coordenadas, e as observações ficam guardadas para a validação local.
   - **Ganhos:**
     - o emulador fica mais exato justamente onde há dados para usá-lo;
     - na fase de validação local, H4 pode ser testada também com **observações reais**, e não só com cultivares sintéticas;
     - a mesma fase mede o ganho de trocar as entradas globais por dados locais.
2. **Pontos de preenchimento.** Os sítios experimentais se concentram nos EUA, no Brasil, na Argentina e na China, e quase faltam na África, no Sul da Ásia e em partes da Europa. Só com eles, o emulador não generaliza para o resto do globo. Por isso entram pontos complementares:
   - amostragem estratificada por zona climática de Köppen-Geiger × faixa de latitude de 10° (o sinal da latitude separa os hemisférios);
   - prioridade para estratos sem sítio experimental (preencher o espaço de clima, não repetir o que já está coberto);
   - dentro de áreas com soja e uma parte em terras agrícolas sem soja hoje (áreas de expansão).

**Implementação** (`cropemu_bench.inputs.points`; bases abertas e sem cadastro):
- **Grade:** 0,5°, a mesma do NASA POWER e do GGCMI. Um ponto de preenchimento é o centro de uma célula.
- **Área de soja:** GAEZ+ 2015 (Grogan et al. 2022, Harvard Dataverse 10.7910/DVN/KAGRFI, CC0), 5' somado para 0,5°. A soma global dá 119,8 Mha, o que bate com a área colhida de 2015. O SPAM 2020 foi descartado porque exige formulário de cadastro (guestbook) para baixar.
- **Áreas de expansão:** células com ≥ 5.000 ha de outras culturas de campo (milho, trigo, sorgo, milheto, algodão, amendoim, leguminosas, girassol) e < 500 ha de soja.
- **Köppen-Geiger:** Beck et al. 2023 (figshare 10.6084/m9.figshare.21789074, CC BY 4.0), período 1991–2020, mapa de 0,5°. Classes polares (ET, EF) ficam fora.
- **Alocação:**
  - por estrato, peso √(área de soja): fica entre o proporcional, que concentraria tudo nos EUA, no Brasil e na Argentina, e o uniforme;
  - mínimo de 2 pontos por estrato, reduzido automaticamente quando não cabe;
  - os sítios contam na alocação: cada novo ponto vai ao estrato mais abaixo da sua parte, então estratos já cobertos por sítios recebem menos;
  - dentro do estrato, sorteio ∝ área de soja (ou de outras culturas, na expansão);
  - 15% de expansão; semente fixa, para ser reprodutível.
- **Resultado com 2.000 pontos:** 1.700 de soja e 300 de expansão em 117 estratos e 290 blocos de 5° × 5°. Por região: América do Sul 714, Ásia e Oceania 570, América do Norte 381, África e Oriente Médio 190, Europa 143. Com 1.000 pontos, 117 estratos; com 5.000, 117 estratos e 377 blocos.
- **Blocos espaciais** de 5° × 5° em cada ponto, para a validação com blocos fora (4.3).

- Meta: de 1.000 a 5.000 pontos no total.
- Altitude: a do NASA POWER (por célula) ou de MDE global (Copernicus DEM ou SRTM) para o ponto exato.
- **Validação:** os sítios experimentais vêm em aglomerados (várias estações de uma mesma rede). Os blocos espaciais de 4.3 precisam separar os aglomerados inteiros, para não vazar informação entre treino e teste.
- **Comparação extra:** treinar só com sítios experimentais contra treinar com sítios + preenchimento, testando em blocos fora. Isso responde se um emulador treinado onde há dados basta para o mundo (liga com H2).

**Clima (diário)**
- **Base única: NASA POWER** (meteorologia a 0,5° do MERRA-2, radiação a 1°). **Período útil: de 1984 em diante.** A meteorologia começa em 1981, mas a radiação solar só existe a partir de 1984-01-01 (conferido na API v2.10.3). É gratuita, tem API aberta, é já usada pela comunidade DSSAT e traz Tmax, Tmin, chuva, radiação, umidade e vento.
- **Treino e biblioteca usam a mesma fonte.** Isso elimina a diferença entre o clima do treino e o do uso.
- **Os vieses do POWER não são problema para o emulador.** Ele aprende a resposta do modelo a qualquer clima; o que importa é cobrir a faixa de climas reais.
- **Reprodutibilidade:** o POWER é revisado com o tempo. Guardar a versão e a data da baixa e publicar o recorte dos pontos usados no Zenodo.
- **Baixa:** milhares de pontos × 42 anos. Uma requisição traz 1984–2025 de um ponto em ~3 s (~1,8 MB de JSON). 5.000 pontos levam ~1 h com 4 requisições em paralelo. A API tem limite de taxa: paralelismo moderado, nova tentativa com espera e cache local (`cropemu.weather.fetch`).
- **Teste de robustez opcional:** prever com outra fonte de clima (AgERA5, ou Xavier no Brasil) para medir o erro de quem usar a biblioteca com clima próprio.
- **CO₂ e clima futuro:** incluir o CO₂ como entrada e amostrar perturbações de temperatura, chuva e CO₂ (ΔT, fator de chuva, 350–800 ppm). Sem isso, a biblioteca não serve para estudos de mudança climática com CMIP6, que é um uso óbvio.

**Solos**
- **SoilGrids 2.0, mapas agregados a 1 km** (ISRIC, CC-BY 4.0): 11 propriedades × 6 profundidades até 200 cm (argila, areia, silte, C orgânico, densidade, fragmentos grossos, N, pH, CTC, água a −33 e −1500 kPa).
  - **Como ler:** a API REST não serve (deu 504 depois de 3 min em 08/11/2026). Os GeoTIFFs de 1 km são lidos remotamente (rasterio/GDAL) só nos blocos em torno dos pontos (`cropemu.soil.soilgrids`). Cada arquivo tem ~190 MB e baixar tudo daria ~12,5 GB. 1 km basta, porque o clima é de 0,5°.
  - **Representatividade:** mediana numa janela de 3 × 3 km, para não cair num pixel de cidade ou de água. Pontos sem solo (oceano, cidade) voltam como NaN e são descartados ou deslocados.
- **Parâmetros hídricos:** LL e DUL dos mapas de retenção do próprio SoilGrids (wv1500, wv0033). A saturação vem da densidade e a Ksat de Saxton & Rawls (2006). Saxton & Rawls também é a alternativa para LL e DUL e a reserva das camadas sem dado.
- **A decidir:** parâmetros de superfície do DSSAT (albedo, SLU1, drenagem, curva-número) por textura e declividade. Hoje são constantes (0,13; 6 mm; 0,6/d; 73). Também falta a profundidade efetiva de raízes (hoje 200 cm, o limite do SoilGrids).
- Alternativa pronta para o DSSAT: base global de perfis a 10 km (Han et al. 2019) e os 27 perfis genéricos HC27.

**Manejo**
- **Calendário de semeadura: GGCMI Phase 3 v1.01** (Jägermeyr et al. 2021, Zenodo 10.5281/zenodo.5062513, CC-BY 4.0), soja de sequeiro (`rf`) e irrigada (`ir`), 0,5° (`cropemu_bench.inputs.calendar`).
  - A data de semeadura de cada safra é a do GGCMI deslocada de −30 a +30 dias, com o deslocamento sorteado por hipercubo latino. A janela padrão é ±30 dias e ainda pode mudar.
  - Ponto sem calendário na própria célula: usa a célula com dados mais próxima, até 2 células (1°) de distância.
  - **Atenção:** o GGCMI preencheu lacunas e tem calendário em quase toda terra, até no Saara. Ele não indica onde há soja; quem indica é a máscara do GAEZ+.
  - Conferido: Londrina 31/10 (CONAB), Iowa 3/5, Rosário 30/11, Harbin 2/5, Indore 1/7, Lusaka 1/12.
- **Cultivares:** grupos de maturidade de 000 a X (do Canadá e da China até os trópicos). O espaço de parâmetros de cada modelo é amostrado em faixas que cubram esses grupos.
- Sequeiro e potencial (irrigado).

### 4.3 Fatores do benchmark

1. **Algoritmo:** MLP (incluindo multi-saída), GB (HistGradientBoosting, LightGBM), random forest, GP esparso (só em baixa dimensão), ridge (referência), redes sequenciais para o nível 2.
2. **Representação:** janelas fixas; janelas ancoradas na fenologia; séries diárias; clima resumido + identificador do local (para mostrar o vazamento).
3. **Desenho amostral:** número de locais × anos × amostras, com o total fixo (10⁴, 10⁵, 10⁶) e o teste fixo.
4. **Validação:**
   - aleatória (referência otimista);
   - **blocos espaciais fora**, não pontos isolados: pontos vizinhos na grade têm clima e solo quase iguais, e tirar só o ponto vaza informação. Blocos de alguns graus, ou com raio definido pelo alcance da autocorrelação;
   - anos fora, com os mesmos anos tirados de todos os locais (por causa do ENSO);
   - blocos e anos fora;
   - solos fora;
   - **continente fora** (ex.: treina nas Américas, testa na Ásia);
   - **zona climática fora** (ex.: tira um tipo de Köppen inteiro);
   - clima perturbado fora (treina até +2 °C, testa em +4 °C).

   Normalizações e qualquer ajuste de entradas são feitos só no treino.

### 4.4 Seleção por modelo e emuladores consolidados

Para cada modelo de cultura:
1. Rodar o benchmark (4.3) e escolher, **por grupo de saídas**, a melhor combinação de algoritmo, representação e desenho. O critério é o erro em locais e anos fora, com desempate pela velocidade de predição e pela acurácia na tarefa (H4).
2. Fixar a configuração e treinar o **emulador consolidado** com todos os dados, deixando de fora só um conjunto final de teste nunca usado na seleção.
3. Publicar:
   - pesos e configuração;
   - ficha do emulador: faixas de validade das entradas, erro por saída e por região, saídas não recomendadas;
   - checagem de domínio: aviso quando a entrada sai da faixa de treino.
4. Carregamento simples: `cropemu.load("dssat-soja-v1")`.

### 4.5 Métricas

- **Acurácia:** RMSE, viés e R² por saída e por região; curvas de aprendizado.
- **Custo:** tempo de simulação, de treino e de predição; aceleração; ponto de equilíbrio (quantas avaliações pagam o custo de gerar o treino).
- **Tarefa:** calibrar **várias** cultivares sintéticas (parâmetros verdadeiros conhecidos) com o simulador verdadeiro e com cada emulador, **cada um do zero**. Comparar medianas, cobertura dos ICs (*simulation-based calibration*), log-posterior e predição final.
  - **Custo do simulador verdadeiro:** com cerca de 6 mil safras por avaliação e 35 ms por safra, são ~25 s por avaliação em 8 núcleos, o que inviabiliza um MCMC longo. Usar conjuntos sintéticos pequenos (centenas de safras) ou, para a fenologia, a reimplementação em JAX (4.6) como simulador verdadeiro.
- **Incerteza do emulador:** ensembles ou regressão quantílica; calibração dos intervalos; efeito de propagá-la na verossimilhança.

### 4.5.1 Critério de aceitação (quando um emulador é bom o bastante)

Definir **antes** de rodar o benchmark, para não escolher o limiar depois de ver o resultado:
- **Datas de fase:** RMSE em blocos espaciais fora menor que o erro típico de observação em campo (ordem de 3–5 d).
- **Produtividade e biomassa:** erro relativo menor que uma fração definida da variabilidade entre anos no mesmo local (ex.: < 25% do desvio-padrão interanual) ou do erro típico do próprio modelo contra observações, segundo a literatura.
- **Demais saídas:** R² e erro relativo reportados. Recebem o rótulo "recomendada" ou "não recomendada" pelo mesmo critério relativo.
- **Na tarefa (H4):** cobertura dos ICs de 90% entre 85% e 95% na calibração sintética.

### 4.6 Alternativa: reimplementar em vez de emular

Fenologia do CROPGRO (PHENOL) em **JAX**:
- exata, rápida e com gradientes (HMC/NUTS);
- validada contra o executável do DSSAT;
- serve também de simulador verdadeiro barato para H4.

A comparação entre emular e reimplementar entra junto do diffWOFOST.

## 5. Biblioteca

**Linguagem: Python.** O tempo de execução está nos executáveis dos modelos e nas bibliotecas de ML. Rust/PyO3 só entraria num gargalo específico.

**Nome: `cropemu`** (decisão de 08/11/2026). Livre no PyPI, no conda-forge e sem repositório homônimo no GitHub em 08/11/2026. Registrar o nome no PyPI cedo, com uma versão 0.0.1 vazia, para garantir.

### 5.0 Dois pacotes

Quem vai usar o emulador não quer instalar o DSSAT, o AquaCrop nem o PyTorch. Por isso são dois pacotes:

| Pacote | Para quem | Conteúdo | Dependências |
|---|---|---|---|
| `cropemu` (biblioteca final) | usuário final: agrônomos, modeladores, estudos de clima | emuladores consolidados, cálculo das entradas a partir do clima diário, baixa de clima (NASA POWER) e de solo (SoilGrids), predição, checagem de domínio, incerteza | leves: numpy, pandas, onnxruntime |
| `cropemu-bench` (pesquisa) | quem treina e estende | adaptadores dos modelos, desenho, simulação, treino, benchmark, calibração | pesadas: modelos de cultura, PyTorch, scikit-learn |

- O cálculo das entradas (`features/`) é **o mesmo código** nos dois pacotes. Se a biblioteca calcular as entradas de um jeito um pouco diferente do treino, o emulador erra sem avisar. Ele mora no pacote leve e o pacote de pesquisa depende dele.
- Os emuladores são exportados para **ONNX**: predição rápida, sem PyTorch e sem depender da versão do scikit-learn.
- Os pesos ficam no Zenodo (ou Hugging Face Hub), baixados sob demanda e versionados (`dssat-soja-v1`).

### 5.1 Estrutura do pacote de pesquisa

```
cropemu-bench/   (import cropemu_bench)
  models/         adaptadores: dssat.py, aquacrop.py (outros modelos depois)
                  (preparar entradas, simular em lote, ler TODAS as saídas,
                   nomes nativos + mapeamento harmonizado)
  inputs/         clima (NASA POWER; genérico), solos (SoilGrids → formato de cada modelo),
                  calendários de semeadura, máscaras de cultivo, amostragem global de pontos
  params/         base de coeficientes publicados (literatura) e distribuições de amostragem
  design/         hipercubo latino, divisões espaciais/temporais, desenhos locais × anos × amostras
  features/       janelas fixas, janelas ancoradas na fenologia, fotoperíodo, séries brutas
  emulators/      mlp (multi-saída), gb, rf, gp, ridge, sequenciais, funcionais;
                  fit/predict/predict_interval; save/load
  evaluate/       validação agrupada, curvas de aprendizado, custo, relatórios por saída
  calibrate/      verossimilhança hierárquica, MCMC, NPE
  zoo/            emuladores consolidados: fichas, download, checagem de domínio
  differentiable/ fenologia CROPGRO em JAX
  benchmark/      configuração dos experimentos, scripts reprodutíveis
```

### 5.2 API mínima (esboço)

```python
import cropemu_bench as ceb

modelo = ceb.models.DSSAT(cultura="soja", executavel=...)
desenho = ceb.design.latin_hypercube(parametros, locais, anos, n_por_local=...)
sims = modelo.simulate(desenho, clima=ceb.inputs.nasa_power(...), solos=ceb.inputs.soilgrids(...),
                       saidas="todas", diarias="subamostra", n_jobs=8)
sims.resumo          # todas as variáveis do resumo, nomes nativos
sims.diario          # séries diárias (subamostra)
sims.harmonizado     # subconjunto comum entre modelos

X = ceb.features.janelas_fisicas(sims, ancoragem="fenologia")
emu = ceb.emulators.MLP(multi_saida=True).fit(X, sims.resumo)
rel = ceb.evaluate.espacial(emu, X, sims, grupos="local", folds=5)

```

Uso na biblioteca final (pacote leve):

```python
import cropemu as ce

emu = ce.load("dssat-soja-v1")                   # baixa o ONNX + ficha
clima = ce.clima.nasa_power(lat=-24.0, lon=-52.4, inicio="2015-01-01", fim="2024-12-31")
solo = ce.solo.soilgrids(lat=-24.0, lon=-52.4)
res = emu.predict(clima=clima, solo=solo, semeadura="2023-10-15",
                  cultivar={"GM": 6.2, ...}, co2=420, saidas="todas")
res.avisos                                       # entradas fora do domínio de treino
res.intervalo(0.9)                               # incerteza do emulador
```

### 5.3 Requisitos de qualidade (GMD/JOSS)

- Código aberto (GitHub + DOI no Zenodo), licença MIT ou Apache-2.0.
- Testes automáticos, com regressão contra saídas de referência de cada modelo; CI.
- Documentação com um tutorial por modelo e um exemplo completo de ponta a ponta.
- Simulações do benchmark e emuladores consolidados publicados no Zenodo.
- Nenhum caminho fixo nem variável de ambiente de pesquisa no pacote.
- Adaptadores finos até a fase 2; a API só se consolida depois que a pergunta se sustentar.

## 6. Produtos e revistas

| Produto | Revista-alvo | Observação |
|---|---|---|
| Artigo principal: benchmark multi-modelo, saídas completas, emuladores consolidados | *GMD* ou *EMS* | Pergunta científica (H1–H6) |
| Conjunto de dados + emuladores | NeurIPS *Datasets & Benchmarks* (prazo ~maio/junho) | Ambicioso; exige dados bem documentados |
| Nota de software | *JOSS* ou *SoftwareX* | Depois da biblioteca estável |
| Fenologia diferenciável + HMC | *EMS*, *AFM* ou *GMD* | Possível artigo separado |

**Relação com o MLCSE (não publicado):** este projeto não usa os resultados dele. Se o MLCSE sair antes, é citado como trabalho prévio. O que é novo aqui: vários modelos, saídas completas, protocolo comum, desenho amostral, representações, avaliação pela tarefa e emuladores consolidados.

## 7. Fases

Versão mínima publicável: **DSSAT + AquaCrop**, saídas completas no nível 1 e harmonizadas, H1–H4 e H6 (fases 0–3).

| Fase | Conteúdo | Saída | Critério para seguir |
|---|---|---|---|
| Fase | Conteúdo | Saída | Critério para seguir |
|---|---|---|---|
| 0a | Revisão sistemática dos coeficientes publicados (DSSAT e AquaCrop, soja); base de coeficientes; distribuições de amostragem | `params/` + base de coeficientes | Cobertura de grupos de maturidade e regiões |
| 0b | Portar o código do DSSAT direto; ler todas as saídas; amostragem global de pontos; NASA POWER, SoilGrids e calendários por script; condições iniciais; testes de regressão | DSSAT simulando em qualquer ponto do globo | DSSAT direto idêntico ao DSSATTools; todas as saídas lidas; plausibilidade contra FAOSTAT/GDHY |
| 1 | Benchmark DSSAT: algoritmos × representações × desenho × validação; nível 1 (todas as saídas do resumo) | melhor caminho para o DSSAT; resultados preliminares de H1–H3 e H6 | Diferenças claras entre os fatores; critério de aceitação (4.5.1) atingido nas saídas principais |
| 2 | Adaptador AquaCrop (executável oficial v7); harmonização; mesmo benchmark | DSSAT + AquaCrop | Simulações plausíveis em todos os locais |
| 3 | Tarefa (H4): calibração sintética, simulador × emuladores | H4 | — |
| 4 | Emuladores consolidados v1 (DSSAT, AquaCrop) + fichas; exportação ONNX; **primeira versão da biblioteca leve** (NASA POWER, SoilGrids, predição, checagem de domínio) | `cropemu` 0.1 no PyPI | Predição pela biblioteca idêntica à do pacote de pesquisa |
| 4b | **Validação local com valores reais** (princípio 6): previsões com entradas globais contra observações dos sítios experimentais; ganho de trocar entradas globais por solo medido e clima de estação; H4 com observações reais | relatório de validação local; ficha do emulador atualizada | — |
| 5 | Nível 2 (trajetórias diárias) para o DSSAT e o AquaCrop | emuladores de séries | — |
| 6 | Fenologia CROPGRO em JAX + HMC (opcional) | emular × reimplementar | — |
| 7 | Redação, Zenodo, documentação, submissão | artigo + pacote | — |

Cronograma em meses: a definir.

## 8. Riscos

- **Escopo:** as fases 0–2 dizem se vale continuar. As fases 5 e 6 são cortáveis.
- **Literatura escassa:** algumas regiões ou grupos de maturidade podem ter poucos coeficientes publicados, sobretudo no AquaCrop. Nesses casos, ampliar as faixas em torno das cultivares padrão e marcar a região como de menor confiança.
- **NASA POWER:** resolução grosseira (0,5°) e revisões da base. Mitigar com o registro da versão e a publicação do recorte.
- **Saídas completas:** o volume de dados é grande, há saídas degeneradas ou censuradas, e emular trajetórias diárias é mais difícil. Mitigar com subamostragem das séries e reportando a cobertura por saída.
- **Volume global:** de 1.000 a 5.000 pontos × 40 anos de clima diário × várias variáveis cabe em disco. O que pesa é a simulação e as saídas diárias. No DSSAT, a ~35 ms por safra, 10⁷ safras dão ~100 h de CPU (algumas horas num servidor de 32 núcleos). O custo do AquaCrop ainda precisa ser medido.
- **Autocorrelação espacial:** validar com blocos espaciais, não com pontos isolados, para não reportar generalização otimista.
- **Domínio de validade da biblioteca:** o usuário vai pedir pontos e climas fora do treino. Checagem de domínio obrigatória e ficha clara.
- **Coerência das parametrizações no mundo:** grupos de maturidade e calendários variam muito entre regiões. Documentar as faixas amostradas.
- **Custo do simulador verdadeiro em H4:** conjuntos sintéticos pequenos e o JAX como simulador exato.
- **Harmonização:** DSSAT e AquaCrop têm estruturas muito diferentes (N, fotoperíodo, fenologia). As saídas harmonizadas são poucas e bem definidas; o foco é o emulador.
- **Licenças:** conferir a licença do executável oficial do AquaCrop v7 e das bases (NASA POWER, SoilGrids, GDHY, calendários) para redistribuir dados e emuladores.
- **Concorrência:** Wageningen (diffWOFOST, DeepCGM) e IIASA (CROMES).
- **Vazamento:** divisões de locais, anos e solos de verdade, inclusive nas normalizações.

## 9. Referências e links

- Blanc, É. & Sultan, B. 2015. Emulating maize yields from global gridded crop models using statistical estimates. *AFM*.
- Blanc, É. 2017. Statistical emulators of maize, rice, soybean and wheat yields from global gridded crop models. *AFM*.
- Franke, J. A. et al. 2020. The GGCMI Phase 2 emulators: global gridded crop model responses to changes in CO₂, temperature, water, and nitrogen. *GMD*.
- Folberth et al. 2025. CROMES v1.0. *GMD* 18, 5759. https://gmd.copernicus.org/articles/18/5759/2025/
- Johnston et al. 2023. Comparison of machine learning methods emulating process driven crop models. *EMS*. https://research.usq.edu.au/item/y9yy5/comparison-of-machine-learning-methods-emulating-process-driven-crop-models
- Gunarathna et al. 2023 (GP emulando APSIM-Sugar); Dokoohaki et al. 2022 (APSIM + otimização bayesiana com IAF).
- apsimNGpy: https://www.researchgate.net/publication/400253866_apsimNGpy_A_comprehensive_Python_framework_for_interactive_reproducible_and_scalable_simulations_of_the_APSIM_Next_Generation_model
- WOFOSTGym: https://arxiv.org/html/2502.19308v1
- Modelos de cultura abertos: https://github.com/EDSEL-skoltech/awesome_crop_models
- WUR-AI/diffWOFOST e WUR-AI/DeepCGM (GitHub).
- Dados globais:
  - AgERA5 (Copernicus Climate Data Store);
  - NASA POWER (power.larc.nasa.gov);
  - SoilGrids (ISRIC, soilgrids.org);
  - Han, Ines & Koo 2019, perfis de solo globais a 10 km para modelos de cultura (*EMS*);
  - Jägermeyr et al. 2021, calendário de cultivo do GGCMI Phase 3;
  - Sacks et al. 2010, calendários de cultivo;
  - SPAM / MIRCA2000 / EarthStat (máscaras de área cultivada);
  - mapa de Köppen-Geiger de Beck et al.
- Conferir os dados bibliográficos completos (volume, páginas, DOI) de Blanc, Franke, Han e Jägermeyr antes de citar, e as licenças de redistribuição das bases.
