# Protocolo da revisão sistemática: sítios experimentais e coeficientes de soja

Fase 0a do [planejamento](../planing.md). Uma única triagem de artigos rende duas bases:

1. **Sítios experimentais** ([sites_template.csv](sites_template.csv)): locais com experimentos de campo de soja e dados observados. Formam o núcleo dos pontos de simulação (seção 4.2 do plano).
2. **Coeficientes publicados** ([coef_dssat_template.csv](coef_dssat_template.csv), [coef_aquacrop_template.csv](coef_aquacrop_template.csv)): parâmetros de cultivar calibrados por outros autores. Definem as faixas de amostragem (seção 4.1.1).

## 1. Perguntas

- Onde (coordenadas) há experimentos de campo de soja com dados de fenologia, produtividade, biomassa ou água no solo?
- Que coeficientes do CROPGRO-Soybean (DSSAT) e do AquaCrop foram calibrados para soja, em que regiões e grupos de maturidade?

## 2. Bases e strings de busca

Buscar em **Scopus** e **Web of Science**. O **Google Scholar** entra como complemento, só com os 200 primeiros resultados por string. Período: de 1990 até a data da busca para o DSSAT, de 2009 até a data da busca para o AquaCrop. Registrar a data de cada busca.

**DSSAT (Scopus)**
```
TITLE-ABS-KEY ( ( "CROPGRO-Soybean" OR "CROPGRO Soybean" OR ( dssat AND ( soybean* OR soya OR "Glycine max" ) ) )
  AND ( calibrat* OR parameteri* OR "genetic coefficient*" OR "cultivar coefficient*" OR evaluat* OR validat* ) )
```

**AquaCrop (Scopus)**
```
TITLE-ABS-KEY ( aquacrop AND ( soybean* OR soya OR "Glycine max" ) AND ( calibrat* OR parameteri* OR evaluat* OR validat* ) )
```

**Web of Science:** as mesmas strings, trocando `TITLE-ABS-KEY ( ... )` por `TS=( ... )`.

**Redes de ensaios (fora da literatura indexada):** levantar relatórios e coordenadas das redes abaixo. Para cada uma, anotar se os dados são públicos.
- USDA Uniform Soybean Tests (Northern e Southern), EUA e Canadá;
- RECSO/INTA, Argentina;
- ensaios VCU e redes estaduais, Brasil (Embrapa, fundações, universidades);
- ensaios nacionais de cultivares da China e da Índia;
- estações de referência do Global Yield Gap Atlas para soja (complemento; não são experimentos).

## 3. Critérios

**Inclusão** (basta um dos dois para entrar em pelo menos uma base):
- **Base de sítios:** experimento de campo com soja, local identificável (coordenadas, ou município ou estação que possa ser geocodificado) e algum dado observado (fenologia, produtividade, biomassa, IAF, água ou N no solo).
- **Base de coeficientes:** CROPGRO-Soybean (DSSAT 3.5 ou posterior) ou AquaCrop calibrado para soja, **com os valores dos coeficientes informados** no texto, em tabela ou em material suplementar.

**Exclusão:**
- só casa de vegetação ou vasos;
- só simulação regional ou em grade, sem experimento de campo;
- revisões, resumos de congresso sem dados, teses já publicadas como artigo (ficar com o artigo);
- duplicatas (mesmo experimento em vários artigos: um registro de sítio, com todas as referências).

## 4. Triagem

1. Exportar os resultados (RIS ou CSV) e tirar duplicatas por DOI e depois por título.
2. Triar título e resumo. Na dúvida, o artigo passa para a leitura completa.
3. Ler o texto completo e aplicar os critérios. Registrar o motivo de cada exclusão.
4. **Concordância:** dois revisores triam a mesma amostra de 10% (mínimo de 30 artigos). Calcular o kappa de Cohen e discutir as divergências antes de seguir.
5. Contar os artigos em cada etapa para o fluxograma PRISMA.

Ferramenta sugerida: Rayyan (gratuito) ou uma planilha com uma coluna de decisão por etapa.

## 5. Extração

Para cada artigo incluído, preencher:
- **um registro por sítio** em `sites.csv`, com o mesmo `site_id` quando o sítio aparecer em vários artigos;
- **um registro por cultivar calibrada** em `coef_dssat.csv` ou `coef_aquacrop.csv`.

Cuidados:
- **Coordenadas:** se o artigo não traz coordenadas, geocodificar a estação ou o município e marcar `coord_precision = town`. Nunca deixar coordenadas inventadas ou arredondadas sem marcar.
- **Grupo de maturidade:** anotar como o artigo informa (ex.: "6.2", "VI", "late"). A conversão para número é feita depois, com uma regra documentada.
- **Versão do modelo:** anotar sempre. Coeficientes de versões antigas do DSSAT podem não ser comparáveis aos da 4.8.
- **Qualidade da calibração:** anotar com que dados ela foi feita (só fenologia; fenologia e produtividade; etc.) e quantas safras foram usadas na calibração e na avaliação.

## 6. Produtos

- `sites.csv`, `coef_dssat.csv` e `coef_aquacrop.csv`, validados por `cropemu_bench.inputs.sites.load_sites` e `load_coefficients`.
- Fluxograma PRISMA e tabela-resumo por país e região.
- A base de coeficientes publicados é um conjunto de dados citável (Zenodo).
