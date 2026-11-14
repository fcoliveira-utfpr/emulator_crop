// The site: climate of the loaded weather, soil profile and the source of every value.

import { fullDate, isoDate, monthName } from '../../engine/dates.js';
import { toCsv, download } from '../../engine/io.js';
import { COLUMNS, SRC } from '../../engine/weather.js';
import { t } from '../../i18n.js';
import { C, draw, figure, Plot } from '../charts.js';
import { grid, header, table } from '../common.js';
import { fmt, h, mean } from '../dom.js';

function texture(clay, sand) {
  const silt = 100 - clay - sand;
  if (clay >= 60) return t('very clayey', 'muito argilosa');
  if (clay >= 35) return t('clayey', 'argilosa');
  if (sand >= 70 && clay < 15) return t('sandy', 'arenosa');
  if (silt >= 50 && clay < 35) return t('silty', 'siltosa');
  return t('medium', 'média');
}

export const siteTab = {
  id: 'local', needsSite: true,
  get label() { return t('Site', 'Local'); },
  render(ctx, _, el) {
    const { site, soil, soilLayers } = ctx, ws = site.ws, tb = site.table;
    const soilSource = t(site.soilSource.en, site.soilSource.pt);
    const elevSource = { input: t('entered', 'informada'), power: 'NASA POWER', default: t('default (0 m)', 'padrão (0 m)') }[site.info.elevSource];
    // complete years for the climatology
    const years = {};
    for (let i = 0; i < ws.n; i++) {
      const d = new Date((ws.t0 + i) * 864e5), y = d.getUTCFullYear(), m = d.getUTCMonth();
      const Y = (years[y] ??= { days: 0, ok: 0, rain: Array(12).fill(0), tx: Array(12).fill(0), tn: Array(12).fill(0), nm: Array(12).fill(0) });
      Y.days++;
      if (Number.isFinite(ws.rain[i]) && Number.isFinite(ws.tmax[i]) && Number.isFinite(ws.tmin[i])) { Y.ok++; Y.rain[m] += ws.rain[i]; Y.tx[m] += ws.tmax[i]; Y.tn[m] += ws.tmin[i]; Y.nm[m]++; }
    }
    const full = Object.entries(years).filter(([, Y]) => Y.ok >= 365 && Y.days >= 365).map(([y, Y]) => ({ year: +y, ...Y }));
    const months = Array.from({ length: 12 }, (_, m) => ({ m: m + 1, name: monthName(m + 1),
      rain: mean(full.map((Y) => Y.rain[m])), tmax: mean(full.map((Y) => Y.tx[m] / Y.nm[m])), tmin: mean(full.map((Y) => Y.tn[m] / Y.nm[m])) }));
    const annual = full.map((Y) => ({ year: Y.year, rain: Y.rain.reduce((a, b) => a + b, 0) }));
    const counts = Object.fromEntries(COLUMNS.map((c) => [c, [0, 0, 0, 0]]));
    for (const c of COLUMNS) for (let i = 0; i < tb.n; i++) if (Number.isFinite(tb.cols[c][i])) counts[c][tb.src[c][i]]++;
    const names = { tmax: 'Tmax', tmin: 'Tmin', srad: t('Solar radiation', 'Radiação'), rain: t('Rain', 'Chuva'), rhum: t('Relative humidity', 'Umidade relativa'), wind: t('Wind', 'Vento'), dewp: t('Dew point', 'Ponto de orvalho') };
    const sources = ['', t('user', 'usuário'), 'NASA POWER', t('gap-filled', 'preenchido')];
    const awc = (l) => (l.dul - l.ll) * (l.bottom - l.top) * 10;

    const exportWeather = () => {
      const rows = [];
      for (let i = 0; i < tb.n; i++) rows.push({ [t('date', 'data')]: isoDate(tb.t0 + i), ...Object.fromEntries(COLUMNS.flatMap((c) => [[c, tb.cols[c][i]], [`${c}_${t('source', 'fonte')}`, sources[tb.src[c][i]]]])) });
      download(t('site_weather.csv', 'clima_local.csv'), toCsv(rows));
    };
    const exportSoil = () => download(t('site_soil.csv', 'solo_local.csv'), toCsv(soilLayers.map((l) => t(
      { top_cm: l.top, bottom_cm: l.bottom, clay: l.clay, sand: l.sand, silt: l.silt, soc: l.soc, bdod: l.bdod, ll: l.ll, dul: l.dul, sat: l.sat },
      { topo_cm: l.top, base_cm: l.bottom, argila: l.clay, areia: l.sand, silte: l.silt, carbono: l.soc, densidade: l.bdod, pmp: l.ll, cc: l.dul, sat: l.sat }))));
    el.append(header(`${t('Site', 'Local')}: ${fmt(site.lat, 3)}°, ${Number.isFinite(site.lon) ? fmt(site.lon, 3) : '—'}°`,
      t(`Daily weather from ${fullDate(site.info.span[0])} to ${fullDate(site.info.span[1])} · elevation ${fmt(site.elev, 0)} m (${elevSource}) · soil: ${soilSource}.`,
        `Clima diário de ${fullDate(site.info.span[0])} a ${fullDate(site.info.span[1])} · altitude ${fmt(site.elev, 0)} m (${elevSource}) · solo: ${soilSource}.`),
      [h('button.secondary', { type: 'button', onclick: exportWeather }, t('Download weather (CSV)', 'Baixar clima (CSV)')), h('button.secondary', { type: 'button', onclick: exportSoil }, t('Download soil (CSV)', 'Baixar solo (CSV)'))]));

    const tile = (l, v, sub) => h('div.tile', h('span.t-label', l), h('span.t-value', v), sub ? h('span.t-sub', sub) : null);
    el.append(h('div.tiles',
      tile(t('Mean annual rain', 'Chuva anual média'), `${fmt(mean(annual.map((a) => a.rain)), 0)} mm`, t(`${full.length} complete years`, `${full.length} anos completos`)),
      tile(t('Soil available water', 'Água disponível do solo'), `${fmt(soil.paw_mm, 0)} mm`, t(`to ${fmt(soil.depth_cm, 0)} cm; ${fmt(soil.paw30_mm, 0)} mm in the top 30 cm`, `até ${fmt(soil.depth_cm, 0)} cm; ${fmt(soil.paw30_mm, 0)} mm nos 30 cm`)),
      tile(t('Texture 0–30 cm', 'Textura 0–30 cm'), texture(soil.clay30, soil.sand30), `${t('clay', 'argila')} ${fmt(soil.clay30, 0)} %, ${t('sand', 'areia')} ${fmt(soil.sand30, 0)} %`),
      tile(t('Organic carbon 0–30 cm', 'Carbono orgânico 0–30 cm'), `${fmt(soil.soc30, 2)} %`, `${t('bulk density', 'densidade')} ${fmt(soil.bdod30, 2)} g/cm³`)));

    const WP = t('Wilting point', 'Ponto de murcha'), FC = t('Field capacity', 'Capacidade de campo');
    const f1 = figure(t('Mean monthly rain', 'Chuva mensal média'), `${full.length ? `${full[0].year}–${full.at(-1).year}` : ''}`);
    const f2 = figure(t('Mean monthly temperature', 'Temperatura mensal média'), null, { legend: [['Tmax', C.orange], ['Tmin', C.blue]] });
    const f3 = figure(t('Annual rain', 'Chuva anual'), t('Complete years.', 'Anos completos.'));
    const f4 = figure(t('Water retention of the profile', 'Retenção de água do perfil'), soilLayers.some((l) => !l.measured)
      ? t(`Estimated with the training method (${ctx.emu.card.hydraulics}); the area between the lines is the available water.`, `Estimada pelo método do treino (${ctx.emu.card.hydraulics}); a área entre as linhas é a água disponível.`)
      : t('Measured values (from your spreadsheet).', 'Valores medidos (da sua planilha).'),
    { legend: [[WP, C.red], [FC, C.blue], [t('Saturation', 'Saturação'), C.gray, 'dash']] });
    el.append(grid(f1.card, f2.card, f3.card, f4.card));
    draw(f1.body, { x: { label: null, domain: months.map((m) => m.name) }, y: { label: t('mm/month', 'mm/mês') }, marks: [
      Plot.barY(months, { x: 'name', y: 'rain', fill: C.rain, rx: 2, insetLeft: 2, insetRight: 2, tip: true, title: (d) => `${d.name}: ${fmt(d.rain, 0)} mm` }), Plot.ruleY([0])] });
    draw(f2.body, { x: { label: null, domain: months.map((m) => m.name) }, y: { label: '°C' }, marks: [
      Plot.areaY(months, { x: 'name', y1: 'tmin', y2: 'tmax', fill: C.orange, fillOpacity: 0.12, curve: 'monotone-x' }),
      Plot.lineY(months, { x: 'name', y: 'tmax', stroke: C.orange, strokeWidth: 2, marker: 'circle-stroke', curve: 'monotone-x' }),
      Plot.lineY(months, { x: 'name', y: 'tmin', stroke: C.blue, strokeWidth: 2, marker: 'circle-stroke', curve: 'monotone-x' }),
      Plot.tip(months, Plot.pointerX({ x: 'name', y: 'tmax', title: (d) => `${d.name}\nTmax ${fmt(d.tmax, 1)} °C\nTmin ${fmt(d.tmin, 1)} °C` }))] });
    const mr = mean(annual.map((a) => a.rain));
    draw(f3.body, { x: { label: null, tickFormat: 'd' }, y: { label: 'mm' }, marks: [
      Plot.rectY(annual, { x: 'year', y: 'rain', interval: 1, fill: C.rain, insetLeft: 1, insetRight: 1, rx: 2, tip: true, title: (d) => `${d.year}: ${fmt(d.rain, 0)} mm` }),
      Plot.ruleY([mr], { stroke: 'currentColor', strokeOpacity: 0.5, strokeDasharray: '4,3' }), Plot.ruleY([0])] });
    const prof = soilLayers.flatMap((l) => [{ depth: l.top, ...l }, { depth: l.bottom, ...l }]);
    draw(f4.body, { height: 300, x: { label: 'cm³/cm³', domain: [0, Math.max(...soilLayers.map((l) => l.sat ?? l.dul)) * 1.05] }, y: { label: t('depth (cm)', 'profundidade (cm)'), reverse: true }, marks: [
      Plot.areaX(prof, { y: 'depth', x1: 'll', x2: 'dul', fill: C.blue, fillOpacity: 0.12 }),
      Plot.lineX(prof, { y: 'depth', x: 'll', stroke: C.red, strokeWidth: 2 }),
      Plot.lineX(prof, { y: 'depth', x: 'dul', stroke: C.blue, strokeWidth: 2 }),
      Plot.lineX(prof.filter((p) => Number.isFinite(p.sat)), { y: 'depth', x: 'sat', stroke: C.gray, strokeWidth: 1.5, strokeDasharray: '5,4' }),
      Plot.tip(soilLayers, Plot.pointerY({ y: (l) => (l.top + l.bottom) / 2, x: 'dul', title: (l) => `${l.top}–${l.bottom} cm\n${WP.toLowerCase()} ${fmt(l.ll, 3)}\n${FC.toLowerCase()} ${fmt(l.dul, 3)}\n${t('available water', 'água disponível')} ${fmt(awc(l), 0)} mm` }))] });

    el.append(h('section.card', h('h2', t('Soil profile', 'Perfil de solo')), table(soilLayers, [
      [t('Layer (cm)', 'Camada (cm)'), (l) => `${l.top}–${l.bottom}`], [t('Clay %', 'Argila %'), (l) => fmt(l.clay, 1), 'num'], [t('Sand %', 'Areia %'), (l) => fmt(l.sand, 1), 'num'], [t('Silt %', 'Silte %'), (l) => fmt(l.silt ?? 100 - l.clay - l.sand, 1), 'num'],
      [t('Org. C %', 'C org. %'), (l) => fmt(l.soc, 2), 'num'], [t('Bulk density g/cm³', 'Densidade g/cm³'), (l) => fmt(l.bdod, 2), 'num'], [WP, (l) => fmt(l.ll, 3), 'num'], [FC, (l) => fmt(l.dul, 3), 'num'],
      [t('Avail. water (mm)', 'Água disp. (mm)'), (l) => fmt(awc(l), 0), 'num']]),
      h('p.hint', t(`Source: ${soilSource}. Profiles deeper than 2 m are cut at 2 m, the depth of every training profile.`, `Fonte: ${soilSource}. Perfis mais profundos que 2 m são cortados em 2 m, a profundidade de todos os perfis do treino.`))));

    const cell = site.info.cell ? t(`NASA POWER cell: ${fmt(site.info.cell.lat, 2)}°, ${fmt(site.info.cell.lon, 2)}°.`, `Célula NASA POWER: ${fmt(site.info.cell.lat, 2)}°, ${fmt(site.info.cell.lon, 2)}°.`) : '';
    el.append(h('section.card', h('h2', t('Source of the weather data', 'Origem dos dados de clima')), table(Object.keys(names), [
      [t('Variable', 'Variável'), (c) => names[c]], [t('Your spreadsheet', 'Sua planilha'), (c) => fmt(counts[c][SRC.user], 0), 'num'], ['NASA POWER', (c) => fmt(counts[c][SRC.power], 0), 'num'],
      [t('Gap-filled (gaps ≤ 5 days)', 'Preenchidos (falhas ≤ 5 dias)'), (c) => fmt(counts[c][SRC.filled], 0), 'num'],
      [t('Missing', 'Faltando'), (c) => fmt(tb.n - counts[c].reduce((a, b) => a + b, 0), 0), 'num']]),
      h('p.hint', t(`Daily values. Your values always take precedence; NASA POWER only completes missing days and columns (no bias correction). Gaps of up to 5 days are interpolated (rain = 0). ${cell} Without humidity, dew point = Tmin is used; without wind, 2 m/s.`,
        `Valores diários. Seus valores sempre têm precedência; a NASA POWER só completa dias e colunas ausentes (sem correção de viés). Falhas de até 5 dias são interpoladas (chuva = 0). ${cell} Sem umidade, usa-se ponto de orvalho = Tmin; sem vento, 2 m/s.`))));
  },
};
