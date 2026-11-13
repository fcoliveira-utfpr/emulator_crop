# Plano da aplicação web do cropemu

## Objetivo

Criar uma página para executar os emuladores de soja do `cropemu` no navegador, sem exigir instalação de DSSAT ou AquaCrop e sem depender de um servidor próprio para a inferência. A aplicação deve aceitar dados informados ou enviados pelo usuário e buscar automaticamente os dados que estiverem ausentes, preservando os valores fornecidos.

## Direção técnica

- Aplicação estática hospedável no GitHub Pages ou na Vercel.
- Interface e lógica de integração em TypeScript/JavaScript.
- Inferência no navegador com ONNX Runtime Web, usando os modelos ONNX distribuídos pelo pacote `cropemu`.
- Portar para JavaScript as transformações e validações de entrada necessárias à previsão; não tentar executar o pacote Python diretamente no navegador.
- Manter os dados e a previsão no dispositivo sempre que possível.
- Consultar NASA POWER e SoilGrids no navegador quando os endpoints permitirem chamadas cross-origin (CORS). Caso algum serviço bloqueie esse acesso, avaliar um proxy mínimo/serverless apenas para essa consulta, mantendo a inferência no navegador.

## Fluxo principal

1. Usuário escolhe o emulador e informa a localização e o período da safra.
2. Usuário pode inserir dados manualmente, importar planilha ou deixar campos em branco.
3. Aplicação valida os dados fornecidos e identifica os campos obrigatórios ausentes.
4. Com consentimento/ação clara, busca clima e/ou solo para a localização e período informados.
5. Mescla os resultados: valores enviados pelo usuário têm precedência; a busca preenche somente lacunas. Não substituir silenciosamente valores fornecidos.
6. Mostra uma revisão com origem, unidades e cobertura de cada dado; permite corrigir os valores antes de executar.
7. Executa a previsão localmente e apresenta resultados, gráficos e avisos de domínio/qualidade.
8. Permite baixar os dados usados e os resultados.

## Dados e resolução de lacunas

- **Localização:** coordenadas ou município/localidade georreferenciada; latitude e elevação alimentam a consulta climática e os recursos que dependem de localização.
- **Clima:** aceitar séries fornecidas (arquivo ou formulário) e buscar a série ausente para o período da safra. Definir explicitamente resolução temporal, variáveis, unidades, calendário e tratamento de dias faltantes conforme o contrato de entrada do `cropemu`.
- **Solo:** aceitar parâmetros medidos/importados e buscar no SoilGrids os parâmetros que faltarem. Aplicar a pedotransferência já existente no `cropemu` quando apropriado. Distinguir valor medido de estimado.
- **Cultivar e manejo:** permitir escolher/preencher os parâmetros de cultivar e semeadura necessários ao emulador; oferecer valores padrão apenas quando tecnicamente justificados e identificá-los como padrão.
- **Proveniência:** guardar por campo o valor, unidade, fonte, momento da consulta e se foi informado, derivado ou estimado.
- Não iniciar a inferência enquanto faltar uma entrada obrigatória; apresentar ao usuário exatamente o que falta.

## Organização inicial proposta

```text
web/
  plano.md
  README.md
  package.json
  index.html
  src/
    app/             # páginas, componentes e estado do formulário
    data/            # importação, validação, mesclagem e proveniência
    providers/        # clientes de clima e solo
    emulator/        # sessão ONNX, adaptação de features e pós-processamento
    charts/           # gráficos dos resultados
  public/
    models/           # modelos ONNX e metadados/licenças necessários
```

A organização pode ser ajustada ao escolher a biblioteca de interface. Manter os ativos ONNX separados do código e conferir tamanho, licenças e caminhos de publicação antes de copiá-los.

## Etapas

1. **Mapear contratos:** identificar nos notebooks e em `packages/cropemu` as entradas obrigatórias, unidades, transformações, saídas e validações dos dois emuladores; localizar modelos e metadados distribuíveis. **Em andamento; achados iniciais abaixo.**
2. **Prova de inferência no browser:** carregar um modelo ONNX com ONNX Runtime Web e comparar entradas/saídas de referência com `cropemu` para um caso conhecido.
3. **MVP manual/importado:** formulário para uma localidade/safra, entrada manual e importação de clima/solo, revisão e previsão local.
4. **Complementação automática:** integrar primeiro NASA POWER e depois SoilGrids; implementar mesclagem por campo, cache e estados de erro/ausência.
5. **Resultados:** gráficos de saídas, avisos, proveniência e exportação dos dados/resultados.
6. **Abas de análise:** ampliar para séries de anos, janela de semeadura, cultivares, sensibilidade, cenários climáticos e mapa regional, inspirando-se nos notebooks `dssat_soybean.ipynb` e `aquacrop_soybean.ipynb`.
7. **Publicação:** configurar build estático e caminhos compatíveis com GitHub Pages/Vercel; documentar atualização dos modelos e limites conhecidos.

## Fora do primeiro MVP

- Executar os binários DSSAT/AquaCrop; comparar o emulador com os simuladores exigiria esses executáveis e fica fora da página estática.
- Comparação das estimativas com safras observadas, calibração de parâmetros e análise de desempenho/validação para o usuário; a página terá como finalidade determinar resultados com o emulador.
- Reescrever toda a funcionalidade dos notebooks de uma vez.

## Critérios de pronto do MVP

- A página estática abre e carrega o modelo no navegador.
- Uma previsão de referência coincide com `cropemu` dentro de tolerância definida.
- Dados parciais do usuário são preservados e apenas lacunas são completadas.
- A tela de revisão informa a origem e unidade de cada entrada e bloqueia campos obrigatórios ainda ausentes.
- Erros de rede, CORS, arquivo inválido e dados incompletos são comunicados sem perder os dados já digitados.


## Etapa 1 — contrato de dados (achados iniciais)

Fontes de referência: `packages/cropemu/src/cropemu/emulator.py`, `features.py`, `units.py`, `weather/eto.py`, `weather/qc.py`, `soil/ptf.py`, `weather/nasa_power.py`, `soil/soilgrids.py` e os arquivos `card.json` em `zoo/`.

### Contrato comum de previsão

- Cada previsão é para uma data de semeadura e requer clima diário contínuo de **30 dias antes até 130 dias depois** (janelas inclusivas no início e exclusivas no fim: `[-30,0)`, `[0,30)`, `[30,60)`, `[60,90)`, `[90,130)`). Para análise de várias datas, obter a união desses períodos.
- Campos meteorológicos mínimos: `tmax`, `tmin`, `srad`, `rain`; `dewp` ou `rhum` são opcionais para estimar pressão real de vapor. Sem ambos, o código assume ponto de orvalho igual a `tmin`. `wind` também é opcional e assume 2 m/s no cálculo de ETo. Calcular VPD e ETo segundo as rotinas existentes, além de fotoperíodo por latitude.
- Datas diárias ausentes não podem ser ignoradas: o Python interpola lacunas curtas de clima (até 5 dias; chuva vira zero) e deixa lacunas longas inválidas. Na página, oferecer preenchimento só para lacunas, preservando observações, com fonte por valor e indicação de conflitos entre fontes.
- Local exige latitude; longitude é necessária para consultas externas. Elevação é opcional no cálculo (padrão 0 m na série), mas uma elevação fornecida/obtida é usada na ETo.
- Solo de entrada não é apenas uma lista de propriedades agregadas: o caminho normal recebe perfil por camadas (`top`, `bottom`, `clay`, `sand`, `soc`, `bdod`; silt/água retida quando disponível), calcula hidráulica e deriva `paw_mm`, `paw30_mm`, textura e médias de 0–30 cm. Perfil hidráulico medido (`ll`, `dul`) tem precedência; senão usa a PTF indicada no cartão, aqui `hybrid`, e as entradas fixas do treino. O corte/limite de 2 m é relevante.
- Entrada ONNX final é uma matriz `float32` com colunas exatamente na ordem `card.json["inputs"]`. Aplicar os campos fixos do cartão, verificar não finitos e calcular saídas derivadas conforme `card.json["derived"]`.
- Cada cartão contém faixa de domínio (`min`/`max`) e faixa de ocorrência comum (`q005`/`q995`): fora da faixa de domínio sinalizar com destaque; fora dos quantis sinalizar como entrada rara. Não bloquear automaticamente uma previsão fora do domínio.
- CO₂ padrão vem da série mensal Mauna Loa interpolada na data de semeadura + 60 dias. Irrigação é booleana convertida para `water=0` (irrigado, sem estresse hídrico) ou `1` (sequeiro). Clima padrão usa `dt=0` e `rain_factor=1`.

### Diferenças entre emuladores

| Item | DSSAT CROPGRO Soybean | AquaCrop Soybean |
|---|---|---|
| Cartão/modelo | `dssat-soybean-v1` / ONNX | `aquacrop-soybean-v1` / ONNX |
| Cultivar do cartão | `mg`, `CSDL`, `PPSEN`, `EM-FL`, `FL-SH`, `FL-SD`, `SD-PM`, `FL-LF`, `LFMAX`, `SLAVR`, `SIZLF`, `WTPSD`, `SFDUR`, `SDPDV` | `cycle_factor`, `gdd_maturity`, `ccx`, `cgc_gdd`, `cdc_gdd`, `wp`, `hio`, `zmax`, `kctr`, `p_exp_upper`, `p_exp_lower`, `p_sto`, `p_sen` |
| Parâmetros prontos | Cartão fornece valores típicos por grupo de maturidade (MG); permite sobrescrever cultivar. | Cartão fornece valores médios dos parâmetros; `gdd_maturity` exige informação de ciclo ou cálculo de GDD da série climática. |
| Sinalizador de água | `water` e saídas CROPGRO | `water` e saídas AquaCrop |
| Saídas principais candidatas à interface | `HWAM`/`HWAH` (grão seco, kg/ha), datas fenológicas em dias após semeadura, biomassa e água | `Y(dry)` (t/ha), `BioMass`, datas fenológicas, água/estresse |
| Entradas do modelo | 79 | 82 |
| Saídas brutas | 39 | 44 |

### Artefatos e implicações para o MVP

- Há um `model.onnx` e `card.json` para cada emulador dentro do pacote. O cartão define nomes/ordem das entradas, cultivar, domínio, saída ONNX, níveis de aceitação e demais metadados; deve ser consumido como fonte de verdade, sem duplicar manualmente suas faixas.
- A adaptação não é só uma chamada ONNX: o trabalho principal do browser é reproduzir `WeatherSeries`, ETo/VPD, features temporais e do perfil de solo, PTF hidráulica e composição das entradas exatamente como o Python.
- Recomendação de sequência para reduzir risco: provar inferência ONNX com uma matriz de features já preparada; em paralelo congelar vetores de referência gerados pelo Python; depois portar e comparar a preparação diária/clima; por fim portar solo/PTF. Não construir tela completa antes de validar essa equivalência.
- **Pendente de fechar nesta etapa:** gerar fixtures de referência para ambos os cartões (vetores `inputs` + saídas `cropemu`), definir esquema/formato de planilha aceito e confirmar CORS/comportamento atual dos endpoints de NASA POWER e SoilGrids em navegador. CORS ainda não está confirmado.



## Delimitação funcional

A aplicação é uma ferramenta de **determinação/estimativa**: recebe ou completa os dados da localização, clima, solo, semeadura, cultivar e manejo, executa o emulador e apresenta as saídas da safra. Não incluir comparação com produtividade ou fenologia observada, calibração do cultivar com dados medidos, métricas de erro, nem comparação com os simuladores DSSAT/AquaCrop como funcionalidades para o usuário. Os vetores de referência mencionados na etapa 1 servem somente para verificar internamente que a implementação JavaScript reproduz as previsões de `cropemu`; não são uma funcionalidade da página.

## Progresso de desenvolvimento

- **Iniciado:** criado o esqueleto Vite em `web/`, com formulário inicial, seleção DSSAT/AquaCrop, carregamento dos dois cartões e sessões ONNX Runtime Web no navegador. Modelos copiados para `web/public/models/` (hashes conferidos contra os arquivos do pacote).
- **Limite atual:** ainda não gera estimativa; o envio do formulário carrega o modelo e exibe seus metadados. Importação dos CSVs, obtenção automática, mesclagem dos dados, preparo das features e inferência com entradas de safra ainda precisam ser implementados.
- **Próxima tarefa:** fechar os contratos e fixtures de referência e então implementar os módulos de entrada climática/perfil de solo, com validação da equivalência numérica antes de habilitar o botão de estimativa.

### Continuação — ingestão inicial

- Implementado em `web/src/data.js`: leitura de CSVs com cabeçalhos PT/EN para clima e camadas de solo, normalização básica de datas/unidades, cobertura diária do ciclo, mesclagem campo a campo com precedência do valor do usuário e checagem das variáveis meteorológicas obrigatórias.
- O formulário agora pede data e coordenadas, tenta completar clima incompleto via NASA POWER e mostra a origem/resumo dos valores antes de carregar o modelo. A chamada usa o endpoint diário e as variáveis já usadas por `cropemu`.
- A integração **ainda não calcula estimativa**: os valores de clima validados ainda não foram transformados nas features ONNX; o perfil de solo é apenas lido/validado e ainda não é completado remotamente.
- **Bloqueio de fonte de solo para investigação:** a página oficial do SoilGrids informa que o REST API está temporariamente pausado. A documentação de entrada também pede limitar o uso a cinco chamadas por minuto. A rota REST simples não deve ser tratada como fonte garantida; investigar alternativa compatível com browser antes de implementar a complementação automática de solo.
- Ambiente atual não tem Node.js/npm disponível, portanto ainda não foi possível instalar dependências nem abrir o Vite localmente.
