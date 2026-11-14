# CropEmu web

Página estática, em inglês (padrão) e português (seletor EN/PT no topo ou `?lang=pt` no link), que executa os emuladores do `cropemu` (DSSAT CROPGRO-Soybean e AquaCrop) no navegador:
nenhum servidor próprio, nenhum executável. Hospedável no GitHub Pages, Vercel ou qualquer servidor de arquivos.

```sh
npm install
npm run dev        # desenvolvimento
npm run build      # site estático em dist/ (caminhos relativos)
npm test           # confere o motor JS contra o pacote Python (tests/reference.json)
```

## O que roda onde

| Etapa | Onde | Fonte |
|---|---|---|
| Clima diário desde 1984 | navegador → NASA POWER (CORS liberado; resposta guardada no Cache do navegador) | mesma fonte do treino |
| Solo, 6 camadas até 2 m | navegador → mapas SoilGrids 2.0 de 1 km por HTTP Range (mediana 3×3 km), com WCS 250 m como reserva | mesmos mapas e amostragem do treino (`cropemu.soil.soilgrids`) |
| Planilhas do usuário | navegador (CSV; mesmas colunas e conversões de `cropemu.io`) | têm precedência; a NASA POWER só completa lacunas |
| Entradas da rede (janelas de clima, ETo, balde hídrico, tempo térmico, ΔT/chuva, solo, cultivar) | navegador, `src/engine/` | port de `cropemu.features`/`emulator` |
| Inferência | navegador, ONNX Runtime Web (WASM, 1 thread) | ~40 µs por safra; 1.000 safras em ~50 ms |

## Abas

- **Uma safra**: todas as saídas do modelo com unidade, nível de aceitação e erro de validação; sequeiro × sem estresse hídrico; curvas de biomassa/grãos e IAF (ou cobertura do dossel) passando pelos valores previstos — a forma entre os pontos é esquemática (função beta de crescimento), pois o emulador prevê valores da safra, não séries diárias; clima do ciclo por fase, gráficos, tabela diária e CSV; as 79/82 entradas com a faixa de treino.
- **Série de anos**: a mesma data em vários anos (CSV com o clima diário de todos os ciclos); variável escolhida entre todas as saídas; lacuna hídrica, chuva × ET, fenologia, dispersões, distribuição e resumo.
- **Janela de semeadura**: mapa ano × data, mediana e faixas, risco abaixo de um limiar, melhor data, duração do ciclo.
- **Cultivares**: grupos de maturidade (DSSAT) ou fatores de ciclo (AquaCrop) e sensibilidade a qualquer parâmetro do cultivar.
- **Cenários climáticos**: ΔT × CO₂, ΔT com CO₂ observado e fator de chuva, nas faixas do treino.
- **Local**: climatologia, perfil de solo e retenção de água, origem de cada valor de clima; download de clima e solo.
- **Sobre o modelo**: validação de cada saída, posição da safra no domínio de treino, limites.

O local pode ser escolhido num mapa (Leaflet + OpenStreetMap, busca de cidades pelo Nominatim), por coordenadas ou pela localização do dispositivo; funciona em qualquer ponto do globo (o treino cobriu as áreas de soja entre 44° S e 63° N; fora disso a página sinaliza extrapolação). Enquanto carrega ou calcula, um aviso mostra as etapas e o progresso. Cada aba exporta CSV. Todos os parâmetros do cultivar, o manejo (sequeiro/sem estresse hídrico), o CO₂ e o cenário (ΔT, fator de chuva) ficam na barra lateral.

## Verificação

`tests/make_reference.py` gera, com o pacote Python, 64 safras de referência (Fazenda A dos dados de exemplo: 4 datas, ΔT −1/0/+2, chuva ×0,8/1/1,2, sequeiro e sem estresse, dois cultivares por modelo). `npm test` recalcula tudo em JS: maior diferença relativa 1,6e-8 nas entradas e 3e-5 nas saídas (precisão float32). O perfil SoilGrids lido no navegador coincide com `cropemu.soil.soilgrids.fetch`.

## Manutenção

- Modelos e cartões em `public/models/` são cópias de `../packages/cropemu/src/cropemu/zoo/`; ao atualizar o pacote, copie de novo e rode `npm run reference && npm test`.
- A série de CO₂ está em `src/engine/co2.js` (gerada de `cropemu/data/co2_mauna_loa.csv`).
- Identidade visual: `public/brand/` (recortes de `logo.jpeg`).
