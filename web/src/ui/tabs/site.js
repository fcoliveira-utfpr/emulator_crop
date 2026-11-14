// The site: climate of the loaded weather, soil profile and the source of every value.

import { brDate, isoDate, monthName } from '../../engine/dates.js';
import { toCsv, download } from '../../engine/io.js';
import { COLUMNS, SRC } from '../../engine/weather.js';
import { C, draw, figure, Plot } from '../charts.js';
import { grid, header, table } from '../common.js';
import { auto, fmt, h, mean } from '../dom.js';

function texture(clay, sand) {
  const silt = 100 - clay - sand;
  if (clay >= 60) return 'muito argilosa';
  if (clay >= 35) return 'argilosa';
  if (sand >= 70 && clay < 15) return 'arenosa';
  if (silt >= 50 && clay < 35) return 'siltosa';
  return 'média';
}

export const siteTab = {
  id: 'local', label: 'Local', needsSite: true,
  render(ctx, _, el) {
    const { site, soil, soilLayers } = ctx, ws = site.ws, t = site.table;
    // complete years for the climatology
    const years = {};
    for (let i = 0; i < ws.n; i++) {
      const d = new Date((ws.t0 + i) * 864e5), y = d.getUTCFullYear(), m = d.getUTCMonth();
      const Y = (years[y] ??= { days: 0, ok: 0, rain: Array(12).fill(0), tx: Array(12).fill(0), tn: Array(12).fill(0), nm: Array(12).fill(0) });
      Y.days++;
      if (Number.isFinite(ws.rain[i]) && Number.isFinite(ws.tmax[i]) && Number.isFinite(ws.tmin[i])) { Y.ok++; Y.rain[m] += ws.rain[i]; Y.tx[m] += ws.tmax[i]; Y.tn[m] += ws.tmin[i]; Y.nm[m]++; }
    }
    const full = Object.entries(years).filter(([y, Y]) => Y.ok >= 365 && Y.days >= 365).map(([y, Y]) => ({ year: +y, ...Y }));
    const months = Array.from({ length: 12 }, (_, m) => ({ m: m + 1, name: monthName(m + 1),
      rain: mean(full.map((Y) => Y.rain[m])), tmax: mean(full.map((Y) => Y.tx[m] / Y.nm[m])), tmin: mean(full.map((Y) => Y.tn[m] / Y.nm[m])) }));
    const annual = full.map((Y) => ({ year: Y.year, rain: Y.rain.reduce((a, b) => a + b, 0) }));
    const counts = Object.fromEntries(COLUMNS.map((c) => [c, [0, 0, 0, 0]]));
    for (const c of COLUMNS) for (let i = 0; i < t.n; i++) if (Number.isFinite(t.cols[c][i])) counts[c][t.src[c][i]]++;
    const names = { tmax: 'Tmax', tmin: 'Tmin', srad: 'Radiação', rain: 'Chuva', rhum: 'Umidade relativa', wind: 'Vento', dewp: 'Ponto de orvalho' };

    const exportWeather = () => {
      const rows = [];
      for (let i = 0; i < t.n; i++) rows.push({ data: isoDate(t.t0 + i), ...Object.fromEntries(COLUMNS.flatMap((c) => [[c, t.cols[c][i]], [`${c}_fonte`, ['', 'usuário', 'NASA POWER', 'preenchido'][t.src[c][i]]]])) });
      download('clima_local.csv', toCsv(rows));
    };
    const exportSoil = () => download('solo_local.csv', toCsv(soilLayers.map((l) => ({ topo_cm: l.top, base_cm: l.bottom, argila: l.clay, areia: l.sand, silte: l.silt, carbono: l.soc, densidade: l.bdod, pmp: l.ll, cc: l.dul, sat: l.sat }))));
    el.append(header(`Local: ${fmt(site.lat, 3)}°, ${Number.isFinite(site.lon) ? fmt(site.lon, 3) : '—'}°`,
      `Clima diário de ${brDate(site.info.span[0])} a ${brDate(site.info.span[1])} · altitude ${fmt(site.elev, 0)} m (${site.info.elevSource}) · solo: ${site.soilSource}.`,
      [h('button.secondary', { type: 'button', onclick: exportWeather }, 'Baixar clima (CSV)'), h('button.secondary', { type: 'button', onclick: exportSoil }, 'Baixar solo (CSV)')]));

    const tile = (l, v, sub) => h('div.tile', h('span.t-label', l), h('span.t-value', v), sub ? h('span.t-sub', sub) : null);
    el.append(h('div.tiles',
      tile('Chuva anual média', `${fmt(mean(annual.map((a) => a.rain)), 0)} mm`, `${full.length} anos completos`),
      tile('Água disponível do solo', `${fmt(soil.paw_mm, 0)} mm`, `até ${fmt(soil.depth_cm, 0)} cm; ${fmt(soil.paw30_mm, 0)} mm nos 30 cm`),
      tile('Textura 0–30 cm', texture(soil.clay30, soil.sand30), `argila ${fmt(soil.clay30, 0)} %, areia ${fmt(soil.sand30, 0)} %`),
      tile('Carbono orgânico 0–30 cm', `${fmt(soil.soc30, 2)} %`, `densidade ${fmt(soil.bdod30, 2)} g/cm³`)));

    const f1 = figure('Chuva mensal média', `${full.length ? `${full[0].year}–${full.at(-1).year}` : ''}`);
    const f2 = figure('Temperatura mensal média', null, { legend: [['Tmax', C.orange], ['Tmin', C.blue]] });
    const f3 = figure('Chuva anual', 'Anos completos.');
    const f4 = figure('Retenção de água do perfil', soilLayers.some((l) => !l.measured) ? `Estimada pelo método do treino (${ctx.emu.card.hydraulics}); a área entre as linhas é a água disponível.` : 'Valores medidos (da sua planilha).',
      { legend: [['Ponto de murcha', C.red], ['Capacidade de campo', C.blue], ['Saturação', C.gray, 'dash']] });
    el.append(grid(f1.card, f2.card, f3.card, f4.card));
    draw(f1.body, { x: { label: null, domain: months.map((m) => m.name) }, y: { label: 'mm/mês' }, marks: [
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
    draw(f4.body, { height: 300, x: { label: 'cm³/cm³', domain: [0, Math.max(...soilLayers.map((l) => l.sat ?? l.dul)) * 1.05] }, y: { label: 'profundidade (cm)', reverse: true }, marks: [
      Plot.areaX(prof, { y: 'depth', x1: 'll', x2: 'dul', fill: C.blue, fillOpacity: 0.12 }),
      Plot.lineX(prof, { y: 'depth', x: 'll', stroke: C.red, strokeWidth: 2 }),
      Plot.lineX(prof, { y: 'depth', x: 'dul', stroke: C.blue, strokeWidth: 2 }),
      Plot.lineX(prof.filter((p) => Number.isFinite(p.sat)), { y: 'depth', x: 'sat', stroke: C.gray, strokeWidth: 1.5, strokeDasharray: '5,4' }),
      Plot.tip(soilLayers, Plot.pointerY({ y: (l) => (l.top + l.bottom) / 2, x: 'dul', title: (l) => `${l.top}–${l.bottom} cm\nponto de murcha ${fmt(l.ll, 3)}\ncapacidade de campo ${fmt(l.dul, 3)}\nágua disponível ${fmt((l.dul - l.ll) * (l.bottom - l.top) * 10, 0)} mm` }))] });

    el.append(h('section.card', h('h2', 'Perfil de solo'), table(soilLayers, [
      ['Camada (cm)', (l) => `${l.top}–${l.bottom}`], ['Argila %', (l) => fmt(l.clay, 1), 'num'], ['Areia %', (l) => fmt(l.sand, 1), 'num'], ['Silte %', (l) => fmt(l.silt ?? 100 - l.clay - l.sand, 1), 'num'],
      ['C org. %', (l) => fmt(l.soc, 2), 'num'], ['Densidade g/cm³', (l) => fmt(l.bdod, 2), 'num'], ['Ponto de murcha', (l) => fmt(l.ll, 3), 'num'], ['Cap. de campo', (l) => fmt(l.dul, 3), 'num'],
      ['Água disp. (mm)', (l) => fmt((l.dul - l.ll) * (l.bottom - l.top) * 10, 0), 'num']]),
      h('p.hint', `Fonte: ${site.soilSource}. Perfis mais profundos que 2 m são cortados em 2 m, a profundidade de todos os perfis do treino.`)));

    el.append(h('section.card', h('h2', 'Origem dos dados de clima'), table(Object.keys(names), [
      ['Variável', (c) => names[c]], ['Sua planilha', (c) => fmt(counts[c][SRC.user], 0), 'num'], ['NASA POWER', (c) => fmt(counts[c][SRC.power], 0), 'num'],
      ['Preenchidos (falhas ≤ 5 dias)', (c) => fmt(counts[c][SRC.filled], 0), 'num'],
      ['Faltando', (c) => fmt(t.n - counts[c].reduce((a, b) => a + b, 0), 0), 'num']]),
      h('p.hint', `Valores diários. Seus valores sempre têm precedência; a NASA POWER só completa dias e colunas ausentes (sem correção de viés). Falhas de até 5 dias são interpoladas (chuva = 0). ${site.info.cell ? `Célula NASA POWER: ${fmt(site.info.cell.lat, 2)}°, ${fmt(site.info.cell.lon, 2)}°.` : ''} Sem umidade, usa-se ponto de orvalho = Tmin; sem vento, 2 m/s.`)));
  },
};
