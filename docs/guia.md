# Guia do CropEmu para interpretar cada aba

O [CropEmu](https://fcoliveira-utfpr.github.io/emulator_crop/) simula safras de soja com emuladores de dois modelos de cultura, o DSSAT CROPGRO-Soybean e o FAO AquaCrop 7.3. Este guia explica, aba por aba, o que cada gráfico e cada número mostra, como lê-los e quais cuidados tomar.

Uma regra vale para todas as abas: **o resultado é o que o modelo de cultura simularia para aquele clima, solo e cultivar, não uma medida da lavoura**. Pragas, doenças, plantas daninhas, nitrogênio e o manejo real ficam de fora. Use o CropEmu para comparar opções (datas, cultivares, anos, cenários) e entender riscos, não para prever a produtividade exata de um talhão.

[English version](guide.md)

**Conteúdo**

- [Primeiros passos](#inicio)
- [Uma safra](#safra)
- [Monitoramento da cultura](#monitor)
- [Série de anos](#anos)
- [Janela de semeadura](#janela)
- [Cultivares](#cultivares)
- [Cenários climáticos](#cenarios)
- [Local](#local)
- [Sobre o modelo](#modelo)
- [Termos usados no app](#termos)
- [Perguntas frequentes](#faq)

<a id="inicio"></a>

## Primeiros passos

A barra lateral define a safra; as abas mostram análises diferentes da mesma configuração.

1. **Modelo.** DSSAT ou AquaCrop. Os dois simulam a soja de formas diferentes:
   - o DSSAT simula a fotossíntese, o fotoperíodo e os grupos de maturidade;
   - o AquaCrop é guiado pela transpiração e pela cobertura do dossel, com o ciclo em graus-dia.

   A diferença entre eles é uma medida da incerteza dos próprios modelos de cultura. Quando os dois concordam, a conclusão é mais robusta.
2. **Local e dados.**
   - **Onde escolher o local:** um local de exemplo, um ponto no mapa, as coordenadas ou a sua localização.
   - **Origem padrão dos dados:** o clima diário vem da NASA POWER (desde 1984) e o solo do SoilGrids 2.0, as mesmas fontes do treino.
   - **Seus dados:** em *Usar meus dados*, você pode enviar uma planilha de clima diário e um perfil de solo. Os seus valores têm prioridade, e a NASA POWER só completa dias e colunas que faltam.
3. **Semeadura e período.** Dia e mês da semeadura, o ano da safra (aba *Uma safra*) e o período de anos (abas *Série de anos*, *Janela*, *Cultivares* e *Cenários*).
4. **Cultivar.** O padrão é a cultivar típica da latitude (grupo de maturidade no DSSAT, duração do ciclo no AquaCrop). Em *Todos os parâmetros da cultivar*, cada coeficiente pode ser alterado dentro da faixa do treino.
5. **Manejo e cenário.**
   - **Água:** *Sequeiro* (só chuva) ou *Sem estresse hídrico* (água à vontade, equivalente a uma irrigação perfeita).
   - **CO₂:** em branco, usa o valor observado em Mauna Loa no ano.
   - **ΔT:** soma graus às temperaturas máxima e mínima.
   - **Chuva ×:** multiplica a chuva.
   - **População de plantas:** plantas por m², de 15 a 50 (a faixa do treino); em branco usa 30. Nos dois modelos, mais plantas aumentam um pouco a produtividade (no DSSAT, cerca de +60 kg/ha a cada 10 plantas/m² no sequeiro e +125 kg/ha sem estresse hídrico).

**Faixas do treino:** ΔT de −1 a +4 °C, chuva de ×0,7 a ×1,3 e CO₂ de 350 a 800 ppm. Fora delas, o emulador extrapola.

**Para todas as abas:**
- **Baixar CSV** exporta os números da aba.
- Passar o mouse sobre um gráfico mostra os valores de cada ponto.
- O botão **Como ler esta aba** abre a seção correspondente deste guia.

<a id="safra"></a>

## Uma safra

Todas as saídas de uma única safra: o ano escolhido em *Ano da safra*, semeada no dia e mês da barra lateral.

**Quadros do topo**
- **Produtividade de grãos:** grãos secos no fim do ciclo. Com *Sem estresse hídrico*, o texto embaixo traz a produtividade de sequeiro para comparação, e vice-versa. A diferença entre os dois é o *yield gap* hídrico da safra (veja [Termos](#termos)).
- **Floração e Maturidade:** data prevista e dias após a semeadura.
- **Biomassa aérea:** matéria seca total da parte aérea na maturidade (folhas, hastes, vagens e grãos).
- **Chuva no ciclo e Evapotranspiração:** água recebida e água usada pela cultura (transpiração mais evaporação do solo) da semeadura à maturidade. Uma evapotranspiração bem menor que a demanda indica falta de água.

**Confiabilidade.** Diz se alguma entrada da safra (clima, solo, cultivar) está fora da faixa do treino ou entre os 0,5 % mais extremos dela. Fora do domínio, o resultado é uma extrapolação e não deve ser usado; entradas raras pedem mais cautela.

**Biomassa aérea e grãos ao longo do ciclo.**
- **Linhas:** as curvas diárias previstas pelo emulador. Uma segunda rede prevê a forma de cada curva no tempo fenológico (semeadura, emergência, floração, maturidade), escalada pelos valores da safra; na validação por blocos, as formas chegam a R² 0,95–0,99 para biomassa e grãos.
- **Pontos:** os valores da safra (biomassa e grãos na maturidade). A linha tracejada cinza é a biomassa sem estresse hídrico.
- **Como ler:** compare a altura final de sequeiro com a sem estresse para ver quanto a água limitou.

**Índice de área foliar (DSSAT) ou Cobertura do dossel (AquaCrop) ao longo do ciclo.**
- **Linha:** o índice de área foliar ou a cobertura do dossel diários previstos pelo emulador. **Ponto:** o máximo previsto.
- **Referências:** um IAF máximo acima de 3–4 indica dossel fechado; valores baixos indicam estresse ou ciclo curto.

**Estresse hídrico ao longo do ciclo.**
- **O que mostra:** o estresse hídrico emulado, de 0 (nenhum) a 1 (total): estresse na fotossíntese (WSPD) no DSSAT, estresse estomático (StSto) no AquaCrop, como a média de cada trecho do ciclo.
- **Como ler:** o estresse perto da floração e do enchimento de grãos é o que mais tira produtividade. O R² na validação é 0,80 (DSSAT) e 0,66 (AquaCrop): confie no padrão, não nos dias exatos.

**A planta ao longo da safra.** Um desenho ilustrativo movido pelas curvas emuladas: a altura acompanha a biomassa, as folhas acompanham a área foliar ou a cobertura do dossel, as flores aparecem na floração, as vagens enchem com os grãos, e as folhas murcham e amarelam com o estresse hídrico e caem na senescência. Mova o controle deslizante ou aperte *Animar* para seguir o ciclo dia a dia; o painel ao lado traz o estádio e os valores emulados do dia.

**Clima do ciclo.** São os dados que entraram no cálculo, do 30º dia antes da semeadura até depois da maturidade:
- **Temperatura diária (Tmax, Tmin):** dias acima de 35 °C na floração e no enchimento de grãos reduzem a produtividade.
- **Chuva diária:** veja se houve períodos secos longos, principalmente perto da floração.
- **Chuva e demanda acumuladas:**
  - o que mostra: a chuva acumulada (azul) contra a evapotranspiração de referência acumulada (ETo, verde), que é a demanda de água da atmosfera;
  - como ler: quando a linha da ETo sobe muito acima da chuva, a cultura depende da água guardada no solo; se isso dura semanas, há déficit hídrico.
- **Radiação solar, Déficit de pressão de vapor e Graus-dia:**
  - radiação alta favorece a fotossíntese;
  - um VPD alto (ar seco) aumenta a demanda de água;
  - os graus-dia (base 5 °C, teto 30 °C) mostram a velocidade com que o ciclo avança.

**Todas as saídas do modelo.** É a tabela com todas as saídas (42 no DSSAT, 44 no AquaCrop). Para cada saída mostra:
- o valor e a unidade;
- o **nível de aceitação** e o erro da validação.

Use primeiro as *recomendadas*; as *com cautela* servem para comparar e agregar; ignore as *não recomendadas*.

**As entradas calculadas para a rede.** Lista os números que o emulador recebeu: resumos do clima em janelas, água do solo, cultivar, CO₂. Junto de cada um aparece a faixa do treino, o que ajuda a entender um alerta de domínio.

<a id="monitor"></a>

## Monitoramento da cultura

Acompanha a **safra em andamento**, semeada no ano atual. O clima é conhecido só até hoje, então o resto do ciclo é preenchido por cenários:

- **Clima observado:** NASA POWER até o último dia disponível (3 a 5 dias atrás) e Open-Meteo nos dias mais recentes.
- **Previsão do tempo:** os próximos 16 dias (Open-Meteo).
- **Resto do ciclo:** o clima de **cada ano passado** nas mesmas datas, o que gera um cenário por ano.
- **Resto do ciclo** (seletor no topo):
  - *Previsão sazonal (ECMWF)*: os anos passados são deslocados mês a mês pelas anomalias da previsão sazonal (mais quente, mais chuvoso etc.);
  - *Anos passados*: usa os anos como foram.

Solo e cultivar ficam fixos; só o clima muda entre cenários. A safra é refeita **a cada 7 dias** desde a semeadura, cada vez com o clima conhecido até aquela data. Por isso dá para ver como a expectativa mudou ao longo da safra.

**Quadros do topo**
- **Produtividade esperada:** a mediana dos cenários, em sequeiro. O texto embaixo traz a faixa em que caem 80 % dos cenários; quanto mais estreita, menos o resultado depende do clima que ainda vai acontecer.
- **Ano mais parecido até agora:** o ano passado cujo clima, de 30 dias antes da semeadura até o último dia observado, mais se pareceu com o desta safra. A comparação é semana a semana: chuva da semana, chuva acumulada e Tmax e Tmin médias, cada uma medida em relação à variação entre os anos, com mais peso nas semanas recentes. O texto traz a produtividade do cenário em que o resto do ciclo segue esse ano, em t/ha e em % do potencial (sem estresse hídrico), e os dois anos seguintes do ranking. É o **cenário mais provável** só no sentido de "a safra vem parecida com aquele ano até aqui"; o futuro ainda pode seguir outro caminho, por isso a faixa de 80 % continua sendo a referência.
- **Variação desde a semeadura:** quanto a expectativa subiu ou caiu em relação à da data da semeadura. Uma queda indica que o clima até agora foi pior que o dos anos passados naquelas semanas.
- **Yield gap (água):** a mediana, entre os cenários, da diferença *sem estresse hídrico − sequeiro*. É a produtividade que o modelo atribui à falta de água. Perto de zero, a água não está limitando.
- **Fase da cultura:** dias após a semeadura e a fase esperada (vegetativa, reprodutiva, maturidade), com a média dos cenários.

**Produtividade esperada ao longo da safra.**
- **Eixo horizontal:** a data em que a safra foi refeita.
- **Linha azul:** a mediana de sequeiro.
- **Faixa azul:** 80 % dos cenários. Ela se estreita conforme a safra avança, porque cada vez mais dias são conhecidos.
- **Linha tracejada cinza:** a produtividade sem estresse hídrico.
- **Área vermelha:** o yield gap.
- **Trecho tracejado:** a estimativa que já usa a previsão de 16 dias.
- **Losango roxo com barra:** a estimativa com a previsão sazonal e a sua faixa de 80 %.
- **Projeção até a maturidade (depois de hoje):** cada ano passado, um de cada vez, é tomado como o clima que vai acontecer (um "caminho"); a cada 2 semanas, a safra é refeita com o clima que seria conhecido naquela data e os outros anos para o resto. **Linha azul tracejada:** a mediana dos caminhos; **faixa clara:** 80 % dos caminhos, que abre até a maturidade, onde mostra as produtividades finais; **linha laranja tracejada:** o caminho do ano mais parecido, que termina na produtividade final daquele ano. A projeção usa os anos passados como foram (sem a previsão sazonal) e é calculada depois do resto da aba (alguns segundos).
- **Linha vertical:** hoje.

Como ler: uma linha que desce semana após semana indica que o clima está piorando a safra. Um losango abaixo da linha indica que a previsão sazonal é menos favorável que a média dos anos passados.

**Yield gap ao longo da safra.** O yield gap em cada data. Um aumento mostra quando a falta de água começou a pesar.

**Produtividade final em cada cenário.**
- **Pontos azuis:** sequeiro, um por ano passado ("o resto do ciclo como no ano X").
- **Círculos cinza:** sem estresse hídrico.
- **Círculo laranja:** o ano mais parecido.
- **Como ler:** a distância entre os dois é o yield gap daquele cenário. Anos com valores bem abaixo dos demais mostram o risco de o resto da safra ser seco ou quente.

**Chuva acumulada desde a semeadura.**
- **Linha azul:** esta safra (tracejada, a previsão).
- **Linha tracejada cinza e faixa:** mediana e 80 % dos anos passados nos mesmos dias.
- **Linha roxa:** chuva esperada até a maturidade no modo escolhido.
- **Linha laranja fina:** a chuva do ano mais parecido, da semeadura até hoje (para comparar com a desta safra).
- **Linha laranja tracejada:** esta safra completada com a chuva do ano mais parecido.
- **Linhas verticais:** floração e maturidade esperadas.

Como ler: abaixo da faixa cinza, a safra está mais seca que quase todos os anos.

**Produtividade formada ao longo do ciclo, % do potencial.** O grão acumulado dia a dia em cada cenário (as curvas diárias do emulador), em % da produtividade sem estresse hídrico do mesmo cenário.
- **Linha tracejada cinza:** sem estresse hídrico, chega a 100 % na maturidade.
- **Linha azul e faixa:** sequeiro, mediana e 80 % dos cenários. Na maturidade, o valor é a produtividade relativa (sequeiro ÷ potencial).
- **Linha laranja:** o ano mais parecido.
- O grão começa a crescer perto do enchimento de grãos (depois da floração); antes disso as curvas ficam em zero.

**Yield gap ao longo do ciclo, % do potencial.** O grão perdido por falta de água até cada dia (sem estresse hídrico − sequeiro), em % do potencial; na maturidade é o yield gap final de cada cenário. Mesma leitura: mediana, faixa de 80 % e ano mais parecido. As duas curvas são comparadas na mesma fase da cultura (a seca encurta o ciclo de sequeiro em alguns dias).

**Temperatura diária.**
- **Tmax e Tmin:** desta safra; esmaecidas, os dias de previsão.
- **Linha cinza:** a Tmax mediana dos anos passados.
- **Linha roxa:** a Tmax esperada com a previsão sazonal.

**Previsão sazonal do ECMWF usada.** A tabela mostra, para cada mês:
- a anomalia de temperatura e de ponto de orvalho (somadas ao clima dos anos passados);
- a anomalia de chuva e de radiação (multiplicadas);
- a chuva prevista contra a normal do próprio modelo de previsão.

Cuidados com a previsão sazonal:
- ela diz se um mês tende a ser mais quente ou mais chuvoso que o normal, **não o tempo de cada dia**;
- a qualidade dela varia com a região e a época do ano, e ainda não foi avaliada para este uso.

**A safra até agora.**
- **Chuva desde a semeadura:** comparada com os anos passados.
- **Dias com Tmax ≥ 35 °C:** contados desde a semeadura.
- **Estresse hídrico dos últimos 14 dias:** um índice simples do balde de água do solo, de 0 (sem estresse) a 1 (severo).
- **Chuva prevista para os próximos 15 dias.**

**Cuidados**
- No começo do ciclo, a faixa é larga e o resultado diz mais sobre o clima típico do local que sobre esta safra.
- O yield gap é só o efeito da água. Pragas, doenças e nutrição não entram.
- A previsão de 16 dias e a sazonal podem errar. Compare o modo *Previsão sazonal* com o modo *Anos passados* para ver quanto a conclusão depende dela.

<a id="anos"></a>

## Série de anos

A mesma safra (mesmo dia e mês de semeadura, mesma cultivar e manejo) repetida em **cada ano do período** escolhido. Mostra a variabilidade causada só pelo clima.

**Variável.** O seletor no topo escolhe a saída mostrada nos gráficos (produtividade, biomassa, evapotranspiração, datas etc.).

**Quadros do topo**
- **Média, sequeiro:** a média e a mediana entre os anos.
- **Variabilidade entre anos:**
  - o que mostra: o coeficiente de variação (CV, desvio-padrão em % da média);
  - como ler: um CV acima de 20–25 % na produtividade indica uma safra de alto risco climático.
- **Anos ruins / bons:** o valor abaixo do qual ficam 10 % dos anos e o valor acima do qual ficam 10 %.
- **Sem estresse hídrico:** a média com água à vontade e a diferença média em relação ao sequeiro.

**Variável por ano.**
- **Pontos e linha:** sequeiro.
- **Linha cinza:** sem estresse hídrico.
- **Área vermelha:** a diferença atribuída à falta de água.
- **Anéis vermelhos:** safras com entradas fora do domínio do treino; desconsidere-as.

**Chuva e evapotranspiração no ciclo.** Barras de chuva e linha de evapotranspiração, da semeadura à maturidade, em sequeiro. Anos com pouca chuva e evapotranspiração baixa costumam ser os de menor produtividade.

**Fenologia.** Dias até a floração e até a maturidade em cada ano. A variação vem da temperatura e, no DSSAT, também do fotoperíodo.

**Variável × chuva no ciclo e Variável × evapotranspiração.** Cada ponto é um ano.
- Uma relação forte e crescente indica que a água é o principal fator da variação entre anos no local.
- Pontos fora da tendência indicam que outro fator pesou, como calor ou a distribuição da chuva.

**Distribuição entre os anos.**
- **Eixo vertical:** a probabilidade de um valor menor ou igual ao do eixo horizontal.
- **Como ler:** no ponto 0,2, por exemplo, está a produtividade que não é alcançada em 20 % dos anos. É a curva para pensar em risco e em seguro.

**Resumo entre os anos.** Mínimo, percentis 10, 50 e 90 e máximo de cada saída.

<a id="janela"></a>

## Janela de semeadura

Simula **muitas datas de semeadura em todos os anos** do período. Responde quando semear para ter maior produtividade e menor risco.

**Controles.** Início e fim da janela, intervalo entre datas (em dias), a variável e o limite de risco (um valor fixo ou um percentil, que por padrão é o de 20 % de todas as safras).

**Quadros do topo**
- **Melhor mediana:** a data com a maior mediana entre os anos e a faixa de 10 a 90 %.
- **Menor risco:** a data com a menor fração de anos abaixo do limite.
- **Maturidade na melhor data:** a duração do ciclo e a data aproximada da colheita.

**Variável por ano e data de semeadura** (mapa de cores).
- **Linhas e colunas:** cada linha é um ano e cada coluna uma data de semeadura; cada célula é uma safra.
- **Como ler:** faixas horizontais escuras ou claras são anos bons ou ruins para qualquer data; faixas verticais mostram datas consistentemente melhores ou piores.
- **Pontos:** entradas fora do domínio.

**Mediana e faixas entre os anos.**
- **Linha:** a mediana por data.
- **Faixas:** 25–75 % e 10–90 % dos anos.
- **Linha tracejada:** a melhor mediana.
- **Como ler:** prefira datas com mediana alta **e** faixa estreita. Uma data com mediana um pouco menor e faixa bem mais estreita pode ser a escolha mais segura.

**Risco.** Fração dos anos com a variável abaixo do limite, por data. Quanto menor, mais segura a data.

**Duração do ciclo.** Mediana dos dias da semeadura à maturidade por data. Semeaduras tardias costumam encurtar o ciclo, por causa da temperatura e, no DSSAT, do fotoperíodo, o que afeta o planejamento da safra seguinte.

**Tabela por data de semeadura.** Os números de todos os gráficos.

<a id="cultivares"></a>

## Cultivares

Compara cultivares semeadas na mesma data em todos os anos do período, e mostra a sensibilidade a cada parâmetro da cultivar.

**Variantes.**
- **No DSSAT:** grupos de maturidade (GM). GMs maiores florescem e amadurecem mais tarde porque respondem ao fotoperíodo.
- **No AquaCrop:** fatores de ciclo, sobre os graus-dia até a maturidade, de 0,75 (mais curto) a 1,25 (mais longo).

**Gráficos de caixa** (variável, floração e maturidade por variante).
- **Caixa:** de 25 a 75 % dos anos.
- **Linha interna:** a mediana.
- **Hastes e pontos:** os anos extremos.
- **Como ler:** compare a posição das caixas (qual produz mais) e a altura (qual varia mais entre anos).

**Resumo por cultivar.** Mediana da floração e da maturidade, percentis 10, 50 e 90 da variável e número de safras fora do domínio.

**Sensibilidade a cada parâmetro.**
- **O que faz:** varia um parâmetro de cada vez, dentro da faixa do treino, com os outros fixos.
- **Linha:** a mediana entre os anos.
- **Faixa:** 25–75 %.
- **Linha tracejada:** o valor atual da cultivar.
- **Como ler:** curvas íngremes indicam parâmetros importantes, que valem a pena calibrar com dados de campo; curvas planas indicam parâmetros que pouco mudam o resultado no local.

<a id="cenarios"></a>

## Cenários climáticos

Aplica ao clima observado as mesmas perturbações usadas no treino e mostra a **variação da média** entre os anos em relação ao clima observado. As perturbações são:
- **ΔT:** graus somados às temperaturas máxima e mínima;
- **Chuva:** multiplicada por um fator;
- **CO₂:** fixado num valor.

Os campos ΔT, chuva e CO₂ da barra lateral não se aplicam a esta aba; os valores testados são definidos nos campos do topo.

**Média com o clima observado.** A referência das comparações.

**Variável: aquecimento × CO₂** (mapa de cores).
- **Cor de cada célula:** a variação para uma combinação de ΔT e CO₂.
- **Como ler:** o aquecimento costuma reduzir a produtividade e o CO₂ costuma aumentá-la (efeito de fertilização). O mapa mostra quanto CO₂ compensa cada grau de aquecimento.
- **Células com borda:** estão fora da faixa do treino.

**Aquecimento com o CO₂ observado.** Variação para cada ΔT sem mudar o CO₂. Mostra o efeito do aquecimento sozinho.

**Chuva.** Variação para cada fator de chuva (treino: ×0,7 a ×1,3). Em sequeiro, mostra a dependência da chuva; sem estresse hídrico, deve ser pequena.

**Cuidados.** Os cenários mudam todos os dias por igual. Eles não mudam a frequência de secas nem de ondas de calor, como fariam as projeções de modelos climáticos.

<a id="local"></a>

## Local

O clima e o solo do local, para entender os resultados das outras abas.

**Quadros do topo**
- **Chuva anual média.**
- **Água disponível do solo:**
  - o que mostra: a água que o perfil guarda entre a capacidade de campo e o ponto de murcha, até 2 m e nos 30 cm superiores;
  - como ler: valores baixos (abaixo de 100 mm) deixam a cultura mais sensível a períodos sem chuva.
- **Textura e carbono orgânico nos 30 cm superiores.**

**Chuva mensal média e Temperatura mensal média.** A climatologia do local, que mostra a estação chuvosa e a época mais quente.

**Chuva anual.** Total de cada ano completo; anos muito secos ou chuvosos aparecem aqui.

**Retenção de água do perfil.**
- **O que mostra:** a umidade na saturação, na capacidade de campo e no ponto de murcha, por camada.
- **Como ler:** o espaço entre a capacidade de campo e o ponto de murcha é a água disponível para a planta.
- **Valores estimados:** vêm de funções de pedotransferência a partir da textura, do carbono e da densidade, iguais às do treino. Quando o seu perfil traz esses valores medidos, eles são usados como estão.

**Perfil de solo.** A tabela das camadas. Perfis com mais de 2 m são cortados em 2 m, como todos os do treino.

**Origem dos dados de clima.**
- **O que mostra:** quantos dias de cada variável vieram da sua planilha, da NASA POWER ou foram preenchidos.
- **Preenchimento de falhas:** falhas de até 5 dias são interpoladas, com chuva zero nesses dias.
- **Sem umidade:** usa-se o ponto de orvalho igual à Tmin.
- **Sem vento:** usa-se 2 m/s.

<a id="modelo"></a>

## Sobre o modelo

**Qualidade de cada saída na validação espacial.**
- **O que mostra:** o R² de cada saída quando o emulador foi testado em blocos de 5° × 5° que ele não viu no treino.
- **Cor:** o nível de aceitação.
- **Como ler:** quanto mais perto de 1, mais o emulador reproduz o modelo de cultura em regiões novas.

**Saídas, unidades e erro de validação.**
- **O que mostra:** a lista de saídas com a unidade, o erro (RMSE) e o nível.
- **Referência:** o erro de produtividade do DSSAT v3 é de cerca de 343 kg/ha e o do AquaCrop v3 de 0,51 t/ha (um pouco acima do v2, 335 kg/ha e 0,50 t/ha, porque o v3 também aprende a população de plantas).

**Onde a sua safra está no domínio de treino.** Cada entrada da última safra calculada aparece sobre a faixa do treino. Entradas perto das bordas ou fora delas explicam alertas e pedem cautela.

**O que o emulador não sabe.** Os limites do método: o que foi fixo no treino e o que fica de fora.

A aba **Sobre o CropEmu** traz a finalidade da ferramenta, o resumo da metodologia, as fontes de dados e o link para o código.

<a id="termos"></a>

## Termos usados no app

- **Emulador:** uma rede neural treinada para reproduzir os resultados de um modelo de cultura. Calcula uma safra em menos de um milissegundo, contra até um segundo do modelo original.
- **Sequeiro:** a cultura recebe só a chuva.
- **Sem estresse hídrico:** a cultura tem toda a água de que precisa, como numa irrigação perfeita. Mostra o potencial do clima, do solo e da cultivar.
- **Yield gap (hídrico):** produtividade sem estresse hídrico menos a de sequeiro. É a perda que o modelo atribui à falta de água. Não inclui perdas por pragas, doenças, nutrição ou manejo.
- **Nível de aceitação:** a classificação de cada saída na validação espacial.
  - *recomendada*: datas com erro de até 5 dias; demais saídas com erro menor que 25 % da variação entre anos no local;
  - *com cautela*: erro menor que 50 % dessa variação;
  - *não recomendada*: o restante.
- **Fora do domínio:** uma entrada fora da faixa vista no treino. O resultado é uma extrapolação e não é confiável.
- **Entrada rara:** dentro da faixa, mas entre os 0,5 % mais extremos do treino. O resultado merece mais cautela.
- **Faixa de 80 % e percentis:**
  - a faixa de 80 % vai do percentil 10 ao 90: deixa de fora os 10 % menores e os 10 % maiores valores;
  - a mediana é o percentil 50.
- **Dias após a semeadura (DAS):** a forma como o app conta as datas do ciclo.
- **ETo:** a evapotranspiração de referência, que é a demanda de água da atmosfera, calculada pelo método FAO-56 Penman-Monteith.
- **VPD:** o déficit de pressão de vapor, que mostra o quanto o ar está seco.
- **Graus-dia:** a soma diária da temperatura média acima de 5 °C (com teto de 30 °C). Mede o avanço do ciclo pelo calor.
- **Grupo de maturidade (GM):** a classe da cultivar de soja pela duração do ciclo e a resposta ao fotoperíodo; GMs maiores são mais tardios.
- **Previsão sazonal:** a previsão de anomalias mensais (mais quente, mais chuvoso) para os próximos meses. Não prevê o tempo de cada dia.

<a id="faq"></a>

## Perguntas frequentes

**A produtividade do app é muito diferente da minha lavoura. Está errado?**
Não necessariamente. O app mostra o que o DSSAT ou o AquaCrop simulariam com a cultivar e o solo informados, sem pragas, doenças nem limitação de nitrogênio, e sem calibração para o seu talhão. Use-o para comparar opções. Para aproximar do campo, envie o seu clima e o seu solo e ajuste a cultivar.

**DSSAT ou AquaCrop: qual usar?**
- O DSSAT representa melhor o grupo de maturidade e o fotoperíodo.
- O AquaCrop é mais simples e focado na água.
- Rodar os dois e comparar é a melhor prática. Se a conclusão é a mesma nos dois, ela é mais confiável.

**Por que algumas safras aparecem marcadas ou somem dos gráficos?**
- **Marcadas:** têm alguma entrada fora do domínio do treino.
- **Somem:** o clima do período estava incompleto. Nos dois casos, a aba *Local* mostra a origem dos dados.

**Os meus dados vão para algum servidor?**
Não. Tudo é calculado no seu navegador. Só as coordenadas do local vão aos serviços públicos de clima, solo, previsão e mapa.

**Por que a previsão sazonal mudou de um mês para o outro?**
O ECMWF atualiza a previsão sazonal todo mês (por volta do dia 5). O monitoramento usa sempre a mais recente.

**Como cito o CropEmu?**
Cite o repositório (<https://github.com/fcoliveira-utfpr/emulator_crop>) e a versão da biblioteca `cropemu`. Um artigo está em preparação.
