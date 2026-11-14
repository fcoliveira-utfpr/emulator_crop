// What CropEmu is: purpose, non-commercial use, summary of the method, data sources and links.

import { t } from '../../i18n.js';
import { header } from '../common.js';
import { auto, fmt, h } from '../dom.js';

export const GITHUB = 'https://github.com/fcoliveira-utfpr/emulator_crop';
const PYPI = 'https://pypi.org/project/cropemu/';

const link = (href, text) => h('a', { href, target: '_blank', rel: 'noopener' }, text);

export const aboutTab = {
  id: 'sobre', needsSite: false,
  get label() { return t('About CropEmu', 'Sobre o CropEmu'); },
  render(ctx, _, el) {
    const { emu } = ctx, k = emu.keys, m = emu.meta, y = m[k.yield], mat = m[k.maturity];
    const name = emu.family === 'dssat' ? 'DSSAT CROPGRO-Soybean' : 'AquaCrop';
    const valid = Number.isFinite(y?.rmse)
      ? t(`For the ${name} emulator now selected, the error on regions not seen in training is ${auto(y.rmse * y.scale)} ${y.unit} for grain yield (R² ${fmt(y.r2, 2)})${Number.isFinite(mat?.rmse) ? ` and ${fmt(mat.rmse, 1)} days for maturity` : ''}.`,
        `Para o emulador ${name} selecionado agora, o erro em regiões não vistas no treino é de ${auto(y.rmse * y.scale)} ${y.unit} na produtividade de grãos (R² ${fmt(y.r2, 2)})${Number.isFinite(mat?.rmse) ? ` e de ${fmt(mat.rmse, 1)} dias na maturidade` : ''}.`)
      : '';

    el.append(header(t('About CropEmu', 'Sobre o CropEmu'),
      t('A free, open-source and non-commercial academic tool to simulate soybean seasons anywhere in the world with emulators of two process-based crop models.',
        'Uma ferramenta acadêmica gratuita, de código aberto e sem fins comerciais para simular safras de soja em qualquer lugar do mundo com emuladores de dois modelos de cultura baseados em processos.')));

    el.append(h('section.card.about',
      h('h2', t('What it is', 'Do que se trata')),
      h('p', t('Crop models such as DSSAT and AquaCrop describe how the weather, the soil, the cultivar and the management shape a season, but running them takes installation, input files and time. CropEmu replaces each model with a neural network trained to reproduce its results: a whole season (phenology, yield, biomass and water balance) is computed in a fraction of a millisecond, here in your browser.',
        'Modelos de cultura como o DSSAT e o AquaCrop descrevem como o clima, o solo, a cultivar e o manejo determinam uma safra, mas rodá-los exige instalação, arquivos de entrada e tempo. O CropEmu substitui cada modelo por uma rede neural treinada para reproduzir os seus resultados: uma safra inteira (fenologia, produtividade, biomassa e balanço hídrico) é calculada em uma fração de milissegundo, aqui no seu navegador.')),
      h('p', t('It is meant for research, teaching and exploring questions such as sowing dates, cultivars, year-to-year risk, climate scenarios and the follow-up of the season in progress. It is not a recommendation service and does not replace field observation or technical advice.',
        'Serve para pesquisa, ensino e para explorar questões como datas de semeadura, cultivares, risco entre anos, cenários climáticos e o acompanhamento da safra em andamento. Não é um serviço de recomendação e não substitui a observação da lavoura nem a assistência técnica.')),

      h('h2', t('Non-commercial use', 'Sem fins comerciais')),
      h('ul.plain',
        h('li', t('Free, with no account, no advertising and no sale of data or services.', 'Gratuito, sem cadastro, sem propaganda e sem venda de dados ou serviços.')),
        h('li', t('Everything is computed in your browser: your spreadsheets are not sent anywhere. Only the coordinates of the site go to the public data services below (weather, soil, forecast and map search).',
          'Tudo é calculado no seu navegador: as suas planilhas não são enviadas a lugar nenhum. Só as coordenadas do local vão aos serviços públicos de dados abaixo (clima, solo, previsão e busca no mapa).')),
        h('li', t('The source code is open under the MIT license and the results are provided as they are, without warranty.', 'O código é aberto sob a licença MIT e os resultados são fornecidos como estão, sem garantia.'))),

      h('h2', t('How the emulators were built', 'Como os emuladores foram construídos')),
      h('ol.steps',
        h('li', h('strong', t('Simulations. ', 'Simulações. ')),
          t('The official executables of DSSAT 4.8 CROPGRO-Soybean and FAO AquaCrop 7.3 were run for 117,720 seasons each: 60 seasons at each of 1,962 points of the world soybean area and of its expansion areas. A Latin hypercube varied the year (1985–2024), the sowing date (GGCMI crop calendar ± 30 days), the maturity group and cultivar coefficients, rainfed or without water stress, and, in 30 % of the seasons, the climate (−1 to +4 °C, rain × 0.7–1.3, CO₂ 350–800 ppm). Weather from NASA POWER; soil from SoilGrids 2.0 with pedotransfer functions.',
            'Os executáveis oficiais do DSSAT 4.8 CROPGRO-Soybean e do FAO AquaCrop 7.3 foram rodados em 117.720 safras cada: 60 safras em cada um de 1.962 pontos da área mundial de soja e das suas áreas de expansão. Um hipercubo latino variou o ano (1985–2024), a data de semeadura (calendário GGCMI ± 30 dias), o grupo de maturidade e os coeficientes da cultivar, sequeiro ou sem estresse hídrico e, em 30 % das safras, o clima (−1 a +4 °C, chuva × 0,7–1,3, CO₂ de 350 a 800 ppm). Clima da NASA POWER; solo do SoilGrids 2.0 com funções de pedotransferência.')),
        h('li', h('strong', t('Inputs. ', 'Entradas. ')),
          t('Each season is described by the site, the soil, the cultivar, the management and CO₂, by weather summaries in five windows from 30 days before to 130 days after sowing, and by the daily weather itself (temperature, radiation, rain, evapotranspiration, vapour pressure deficit, day length and a soil-water stress index, from 30 days before to 170 days after sowing).',
            'Cada safra é descrita pelo local, pelo solo, pela cultivar, pelo manejo e pelo CO₂, por resumos do clima em cinco janelas de 30 dias antes a 130 dias depois da semeadura, e pelo próprio clima diário (temperatura, radiação, chuva, evapotranspiração, déficit de pressão de vapor, fotoperíodo e um índice de estresse hídrico do solo, de 30 dias antes a 170 dias depois da semeadura).')),
        h('li', h('strong', t('Neural networks. ', 'Redes neurais. ')),
          t('The development dates come from the mean of four dense networks; yield, biomass, water balance and the other outputs come from a one-dimensional convolutional network that reads the daily weather and so sees when heat, drought or rain happen in the cycle. The networks are exported to ONNX and run the same way in this page and in the Python library.',
            'As datas de desenvolvimento vêm da média de quatro redes densas; produtividade, biomassa, balanço hídrico e as demais saídas vêm de uma rede convolucional unidimensional que lê o clima diário e, assim, vê quando o calor, a seca ou a chuva acontecem no ciclo. As redes são exportadas em ONNX e rodam do mesmo jeito nesta página e na biblioteca Python.')),
        h('li', h('strong', t('Validation. ', 'Validação. ')),
          t('Five-fold cross-validation by 5° × 5° spatial blocks: each fold tests the emulator on regions it did not see. Every output receives an acceptance level (recommended, caution or not recommended). The emulators were also compared with new runs of the crop models at 7 independent sites. ',
            'Validação cruzada em cinco partes por blocos espaciais de 5° × 5°: cada parte testa o emulador em regiões que ele não viu. Cada saída recebe um nível de aceitação (recomendada, com cautela ou não recomendada). Os emuladores também foram comparados com novas rodadas dos modelos de cultura em 7 locais independentes. '), valid),
        h('li', h('strong', t('Crop monitoring. ', 'Monitoramento da cultura. ')),
          t('For the season in progress, the weather observed so far and the 16-day forecast (Open-Meteo) are completed by the weather of each past year, optionally shifted month by month by the anomalies of the ECMWF seasonal forecast (up to 6 months); the season is re-run week by week to follow the expected yield and the yield gap.',
            'Para a safra em andamento, o clima observado até agora e a previsão de 16 dias (Open-Meteo) são completados pelo clima de cada ano passado, opcionalmente deslocado mês a mês pelas anomalias da previsão sazonal do ECMWF (até 6 meses); a safra é refeita semana a semana para acompanhar a produtividade esperada e o yield gap.'))),
      h('p.hint', t('Limits: the emulators reproduce the crop models, not the field — the errors of the models are inherited, the models were not calibrated for each site, and pests, diseases, weeds and nitrogen are outside them. Details in the tab “About the model”.',
        'Limites: os emuladores reproduzem os modelos de cultura, não a lavoura — os erros dos modelos são herdados, os modelos não foram calibrados para cada local, e pragas, doenças, plantas daninhas e nitrogênio ficam de fora. Detalhes na aba “Sobre o modelo”.')),

      h('h2', t('Data and credits', 'Dados e créditos')),
      h('ul.plain',
        h('li', link('https://power.larc.nasa.gov/', 'NASA POWER'), t(' — daily weather since 1984 (training and analyses).', ' — clima diário desde 1984 (treino e análises).')),
        h('li', link('https://open-meteo.com/', 'Open-Meteo'), t(' — recent days, the weather forecast and the ECMWF seasonal forecast in crop monitoring (CC BY 4.0; seasonal forecast based on ECMWF data and products).', ' — dias recentes, previsão do tempo e previsão sazonal do ECMWF no monitoramento da cultura (CC BY 4.0; previsão sazonal baseada em dados e produtos do ECMWF).')),
        h('li', link('https://soilgrids.org/', 'SoilGrids 2.0 (ISRIC)'), t(' — soil profiles (CC BY 4.0).', ' — perfis de solo (CC BY 4.0).')),
        h('li', link('https://dssat.net/', 'DSSAT'), ' · ', link('https://www.fao.org/aquacrop/', 'FAO AquaCrop'), t(' — the crop models emulated.', ' — os modelos de cultura emulados.')),
        h('li', t('GGCMI Phase 3 crop calendar (Jägermeyr et al., 2021); map © ', 'Calendário agrícola GGCMI Fase 3 (Jägermeyr et al., 2021); mapa © '), link('https://www.openstreetmap.org/copyright', 'OpenStreetMap'), '.')),

      h('h2', t('More information', 'Mais informações')),
      h('p', t('Code, methods, the Python library (', 'Código, métodos, a biblioteca Python ('), h('code', 'pip install cropemu'),
        t('), example notebooks and the validation results are in the GitHub repository. Questions and suggestions are welcome as issues there.', '), notebooks de exemplo e os resultados da validação estão no repositório do GitHub. Dúvidas e sugestões são bem-vindas como issues lá.')),
      h('p.about-links', h('a.button', { href: GITHUB, target: '_blank', rel: 'noopener' }, t('GitHub repository', 'Repositório no GitHub')), ' ',
        h('a.button.secondary', { href: PYPI, target: '_blank', rel: 'noopener' }, t('Python library (PyPI)', 'Biblioteca Python (PyPI)'))),
      h('p.hint', 'Fabrício Correia de Oliveira · MIT License')));
  },
};
