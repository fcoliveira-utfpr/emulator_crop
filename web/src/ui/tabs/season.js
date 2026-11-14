// One season: every output, domain flags, growth curves, the weather of the cycle and the inputs.

import { fullDate, isoDate, shortDate } from '../../engine/dates.js';
import { download, toCsv } from '../../engine/io.js';
import { GROUP_ORDER, groupLabel } from '../../engine/units.js';
import { etoDay, gdd } from '../../engine/weather.js';
import { t } from '../../i18n.js';
import { C, draw, figure, Plot } from '../charts.js';
import { domainSummary, exporter, grid, header, levelBadge, table } from '../common.js';
import { auto, fmt, h, mean } from '../dom.js';

/** Beta growth function (Yin et al., 2003): 0 at x=0, wmax at x=te, inflection at tm (0 < tm < te). */
const beta = (x, te, tm, wmax) => (x <= 0 ? 0 : x >= te ? wmax : wmax * (1 + (te - x) / (te - tm)) * (x / te) ** (te / (te - tm)));

/** Schematic seasonal curves through the emulator's points: biomass and grain (beta growth) and
 * leaf area index or canopy cover (beta rise to the maximum, then senescence to maturity).
 * The emulator predicts season summaries only; the shape between the points is assumed. */
function curves(emu, row) {
  const o = row.outputs, k = emu.keys, dssat = emu.family === 'dssat', m = emu.meta;
  const emr = Math.max(1, o[dssat ? 'EDAT_dap' : 'EMR_dap']), flo = o[k.flowering], mat = o[k.maturity];
  const bio = o[k.biomass] * m[k.biomass].scale, grain = o[k.yield] * m[k.yield].scale;
  const canopyMax = dssat ? o.LAIX : o.CC_max;
  if (![emr, flo, mat, bio, grain, canopyMax].every(Number.isFinite) || mat <= flo || flo <= emr) return null;
  const seedStart = flo + 0.3 * (mat - flo), peak = flo + 0.45 * (mat - flo), end = dssat ? 0.25 : 0.35;
  const pts = [];
  for (let d = 0; d <= Math.ceil(mat); d++) {
    const x = d - emr;
    const canopy = d < emr ? 0 : d <= peak ? beta(x, peak - emr, 0.6 * (peak - emr), canopyMax)
      : canopyMax * (1 - (1 - end) * ((d - peak) / (mat - peak)) ** 1.6);
    pts.push({ das: d, bio: beta(x, mat - emr, 0.55 * (mat - emr), bio), grain: d < seedStart ? 0 : beta(d - seedStart, mat - seedStart, 0.5 * (mat - seedStart), grain), canopy });
  }
  return { pts, emr, flo, mat, peak, bio, grain, canopyMax };
}

const stageNames = () => [t('emergence', 'emergência'), t('flowering', 'floração'), t('maturity', 'maturidade')];

function growthCharts(ctx, main, potential, el) {
  const { emu } = ctx, dssat = emu.family === 'dssat', m = emu.meta, k = emu.keys;
  const c = curves(emu, main), p = curves(emu, potential);
  if (!c) return;
  const label = main.irrigated ? t('No water stress', 'Sem estresse hídrico') : t('Rainfed', 'Sequeiro');
  const noStress = t('No water stress', 'Sem estresse hídrico');
  const date = (das) => new Date((main.sowing + das) * 864e5);
  const note = t('Points: values predicted by the emulator. Line: schematic curve (beta growth function) through the points — the emulator predicts season values, not the daily series.',
    'Pontos: valores previstos pelo emulador. Linha: curva esquemática (função beta de crescimento) passando pelos pontos — o emulador prevê os valores da safra, não a série diária.');
  const fb = figure(t('Above-ground biomass and grain through the cycle', 'Biomassa aérea e grãos ao longo do ciclo'), note,
    { legend: [[`${t('Biomass', 'Biomassa')} (${label.toLowerCase()})`, C.green], [t('Grain', 'Grãos'), C.yellow], ...(main.irrigated ? [] : [[noStress, C.gray, 'dash']])] });
  const canopyLabel = dssat ? t('Leaf area index (LAI)', 'Índice de área foliar (IAF)') : t('Canopy cover', 'Cobertura do dossel');
  const fl = figure(`${canopyLabel} ${t('through the cycle', 'ao longo do ciclo')}`, dssat
    ? t('Point: predicted maximum LAI (LAIX); the date of the maximum is assumed between flowering and maturity.', 'Ponto: IAF máximo previsto (LAIX); a data do máximo é suposta entre a floração e a maturidade.')
    : t('Point: predicted maximum canopy cover (CC_max); the date of the maximum is assumed between flowering and maturity.', 'Ponto: cobertura máxima prevista (CC_max); a data do máximo é suposta entre a floração e a maturidade.'),
  { legend: [[label, C.aqua], ...(main.irrigated ? [] : [[noStress, C.gray, 'dash']])] });
  el.append(grid(fb.card, fl.card));
  const names = stageNames();
  const stages = [c.emr, c.flo, c.mat].map((d, i) => ({ s: names[i], x: date(d) }));
  const stageMarks = [Plot.ruleX(stages, { x: 'x', stroke: 'currentColor', strokeOpacity: 0.3, strokeDasharray: '3,3' }),
    Plot.text(stages, { x: 'x', text: 's', frameAnchor: 'top', dy: -2, dx: 4, textAnchor: 'start', fill: 'currentColor', fillOpacity: 0.7, fontSize: 10.5 })];
  const pot = main.irrigated || !p ? [] : p.pts;
  const bioUnit = m[k.biomass].unit;
  const bioPoints = [{ x: date(c.emr), y: 0, t: names[0] }, { x: date(c.mat), y: c.bio, t: `${t('biomass', 'biomassa')} ${fmt(c.bio, 2)} ${bioUnit}` }];
  const grainPoint = [{ x: date(c.mat), y: c.grain, t: `${t('grain', 'grãos')} ${fmt(c.grain, 2)} ${m[k.yield].unit}` }];
  draw(fb.body, { marginTop: 18, x: { label: null }, y: { label: bioUnit, zero: true }, marks: [
    ...stageMarks,
    Plot.lineY(pot, { x: (d) => date(d.das), y: 'bio', stroke: C.gray, strokeWidth: 1.5, strokeDasharray: '5,4' }),
    Plot.lineY(c.pts, { x: (d) => date(d.das), y: 'bio', stroke: C.green, strokeWidth: 2 }),
    Plot.lineY(c.pts, { x: (d) => date(d.das), y: 'grain', stroke: C.yellow, strokeWidth: 2 }),
    Plot.dot(bioPoints, { x: 'x', y: 'y', r: 5.5, fill: C.green, stroke: 'var(--surface)', strokeWidth: 1.5, tip: true, title: 't' }),
    Plot.dot(grainPoint, { x: 'x', y: 'y', r: 5.5, fill: C.yellow, stroke: 'var(--surface)', strokeWidth: 1.5, tip: true, title: 't' }),
    p && !main.irrigated ? Plot.dot([{ x: date(p.mat), y: p.bio }], { x: 'x', y: 'y', r: 4.5, fill: 'var(--surface)', stroke: C.gray, strokeWidth: 1.5, tip: true, title: () => `${noStress}: ${fmt(p.bio, 2)} ${bioUnit}` }) : null,
    Plot.ruleY([0]),
  ] });
  const cu = dssat ? 'm²/m²' : '%';
  draw(fl.body, { marginTop: 18, x: { label: null }, y: { label: cu, zero: true }, marks: [
    ...stageMarks,
    Plot.lineY(pot, { x: (d) => date(d.das), y: 'canopy', stroke: C.gray, strokeWidth: 1.5, strokeDasharray: '5,4' }),
    Plot.areaY(c.pts, { x: (d) => date(d.das), y: 'canopy', fill: C.aqua, fillOpacity: 0.1 }),
    Plot.lineY(c.pts, { x: (d) => date(d.das), y: 'canopy', stroke: C.aqua, strokeWidth: 2 }),
    Plot.dot([{ x: date(c.peak), y: c.canopyMax }], { x: 'x', y: 'y', r: 5.5, fill: C.aqua, stroke: 'var(--surface)', strokeWidth: 1.5, tip: true, title: () => `${dssat ? t('max. LAI', 'IAF máximo') : t('max. canopy cover', 'cobertura máxima')}: ${fmt(c.canopyMax, dssat ? 2 : 0)} ${cu}` }),
    p && !main.irrigated ? Plot.dot([{ x: date(p.peak), y: p.canopyMax }], { x: 'x', y: 'y', r: 4.5, fill: 'var(--surface)', stroke: C.gray, strokeWidth: 1.5, tip: true, title: () => `${noStress}: ${fmt(p.canopyMax, dssat ? 2 : 0)} ${cu}` }) : null,
    Plot.ruleY([0]),
  ] });
}

const sourceName = (s) => ['', t('your spreadsheet', 'sua planilha'), 'NASA POWER', t('gap-filled', 'preenchido')][s];

/** Daily weather of the cycle (30 days before sowing to 15 days after maturity), with the scenario
 * (ΔT, rain factor) applied as in the emulator inputs: summary by phase, charts, table and CSV. */
function cycleWeather(ctx, main, el, floDay, matDay) {
  const { site, s } = ctx, ws = site.ws, tb = site.table, cols = tb.cols;
  const first = main.sowing - 30, last = Math.min(matDay + 15, ws.t0 + ws.n - 1);
  const rows = [];
  let cumGdd = 0, cumRain = 0;
  for (let d = first; d <= last; d++) {
    const i = ws.index(d);
    if (i < 0 || i >= ws.n) continue;
    const tmax = ws.tmax[i] + s.dt, tmin = ws.tmin[i] + s.dt, rain = ws.rain[i] * s.rainFactor;
    const eto = s.dt ? etoDay(tmax, tmin, ws.srad[i], ws.wind[i], ws.ea[i], ws.lat, ws.elev, ws.doy[i]) : ws.eto[i];
    const das = d - main.sowing, g = gdd(tmax, tmin);
    if (das >= 0) { cumGdd += g; cumRain += rain; }
    rows.push({ day: d, date: isoDate(d), das, phase: das < 0 ? 'pre' : d < floDay ? 'veg' : d <= matDay ? 'rep' : 'post',
      tmax, tmin, srad: ws.srad[i], rain, rhum: cols.rhum[i], wind: cols.wind[i], dewp: cols.dewp[i],
      eto, vpd: ws.vpd[i], daylength: ws.dayl[i], gdd: g, gdd_cum: das >= 0 ? cumGdd : null, rain_cum: das >= 0 ? cumRain : null,
      src_tmax: tb.src.tmax[i], src_rain: tb.src.rain[i], src_srad: tb.src.srad[i] });
  }
  const phaseName = { pre: t('30 days before sowing', '30 dias antes da semeadura'), veg: t('Sowing → flowering', 'Semeadura → floração'), rep: t('Flowering → maturity', 'Floração → maturidade') };
  const phases = ['pre', 'veg', 'rep'].map((f) => {
    const r = rows.filter((x) => x.phase === f), sum = (key) => r.reduce((a, x) => a + (x[key] ?? 0), 0);
    return { f, days: r.length, tmax: mean(r.map((x) => x.tmax)), tmin: mean(r.map((x) => x.tmin)), srad: mean(r.map((x) => x.srad)), rain: sum('rain'), eto: sum('eto'),
      vpd: mean(r.map((x) => x.vpd)), hot: r.filter((x) => x.tmax >= 32).length, gdd: sum('gdd'), dry: r.filter((x) => x.rain < 1).length };
  });
  const csvRows = () => rows.map((r) => ({ [t('date', 'data')]: r.date, das: r.das, [t('phase', 'fase')]: phaseName[r.phase] ?? t('after maturity', 'pós-maturidade'),
    tmax: r.tmax, tmin: r.tmin, srad: r.srad, [t('rain', 'chuva')]: r.rain, [t('rhum', 'umidade')]: r.rhum, [t('wind', 'vento')]: r.wind, [t('dewp', 'orvalho')]: r.dewp,
    eto: r.eto, [t('vpd', 'dpv')]: r.vpd, [t('daylength', 'fotoperiodo')]: r.daylength, [t('gdd', 'graus_dia')]: r.gdd, [t('gdd_cum', 'graus_dia_acum')]: r.gdd_cum, [t('rain_cum', 'chuva_acum')]: r.rain_cum,
    [t('source_tmax', 'fonte_tmax')]: sourceName(r.src_tmax), [t('source_rain', 'fonte_chuva')]: sourceName(r.src_rain), [t('source_srad', 'fonte_rad')]: sourceName(r.src_srad) }));
  const name = `${t('cycle_weather', 'clima_ciclo')}_${isoDate(main.sowing)}.csv`;
  const scen = s.dt || s.rainFactor !== 1 ? t(` Values with the scenario applied (ΔT ${fmt(s.dt, 1)} °C, rain ×${fmt(s.rainFactor, 2)}), as in the emulator inputs.`, ` Valores com o cenário aplicado (ΔT ${fmt(s.dt, 1)} °C, chuva ×${fmt(s.rainFactor, 2)}), como nas entradas do emulador.`) : '';
  const sec = h('section.card', h('div.card-head', h('h2', t('Weather of the cycle', 'Clima do ciclo')),
    h('button.secondary', { type: 'button', onclick: () => download(name, toCsv(csvRows())) }, t('Download cycle weather (CSV)', 'Baixar clima do ciclo (CSV)'))),
    h('p.hint', t(`Days from ${fullDate(first)} to ${fullDate(last)}: 30 days before sowing to 15 days after maturity.${scen}`, `Dias de ${fullDate(first)} a ${fullDate(last)}: 30 dias antes da semeadura até 15 dias após a maturidade.${scen}`)),
    table(phases, [[t('Phase', 'Fase'), (r) => phaseName[r.f]], [t('Days', 'Dias'), 'days', 'num'],
      ['Tmax (°C)', (r) => fmt(r.tmax, 1), 'num'], ['Tmin (°C)', (r) => fmt(r.tmin, 1), 'num'], [t('Radiation (MJ/m²/d)', 'Radiação (MJ/m²/d)'), (r) => fmt(r.srad, 1), 'num'],
      [t('Rain (mm)', 'Chuva (mm)'), (r) => fmt(r.rain, 0), 'num'], ['ETo (mm)', (r) => fmt(r.eto, 0), 'num'], [t('Rain − ETo', 'Chuva − ETo'), (r) => fmt(r.rain - r.eto, 0), 'num'],
      [t('VPD (kPa)', 'DPV (kPa)'), (r) => fmt(r.vpd, 2), 'num'], [t('Days ≥ 32 °C', 'Dias ≥ 32 °C'), 'hot', 'num'], [t('Days without rain', 'Dias sem chuva'), 'dry', 'num'], [t('Growing degrees', 'Graus-dia'), (r) => fmt(r.gdd, 0), 'num']]));
  const f1 = figure(t('Daily solar radiation', 'Radiação solar diária'), 'MJ/m²/d.');
  const f2 = figure(t('Vapour pressure deficit', 'Déficit de pressão de vapor'), t('kPa; the higher, the drier the air.', 'kPa; quanto maior, mais seca a atmosfera.'));
  const f3 = figure(t('Growing degrees accumulated since sowing', 'Graus-dia acumulados desde a semeadura'), t('Base 5 °C, upper 30 °C (AquaCrop method).', 'Base 5 °C, teto 30 °C (método do AquaCrop).'));
  sec.append(h('div.grid.inner', f1.card, f2.card, f3.card));
  sec.append(h('details', h('summary', t(`Show the daily table (${rows.length} days)`, `Ver a tabela diária (${rows.length} dias)`)), table(rows, [
    [t('Date', 'Data'), (r) => fullDate(r.day)], [t('DAS', 'DAS'), 'das', 'num'], ['Tmax', (r) => fmt(r.tmax, 1), 'num'], ['Tmin', (r) => fmt(r.tmin, 1), 'num'],
    ['Rad.', (r) => fmt(r.srad, 1), 'num'], [t('Rain', 'Chuva'), (r) => fmt(r.rain, 1), 'num'], [t('RH %', 'UR %'), (r) => fmt(r.rhum, 0), 'num'], [t('Wind', 'Vento'), (r) => fmt(r.wind, 1), 'num'],
    ['ETo', (r) => fmt(r.eto, 1), 'num'], [t('VPD', 'DPV'), (r) => fmt(r.vpd, 2), 'num'], [t('Daylength', 'Fotoper.'), (r) => fmt(r.daylength, 2), 'num'], [t('Source', 'Fonte'), (r) => sourceName(r.src_tmax)]], '.scroll')));
  el.append(sec);
  const x = (r) => new Date(r.day * 864e5);
  const rules = [Plot.ruleX([main.sowing, floDay, matDay].map((d) => new Date(d * 864e5)), { stroke: 'currentColor', strokeOpacity: 0.3, strokeDasharray: '3,3' })];
  const tipDay = (y, f) => Plot.tip(rows, Plot.pointerX({ x, y, title: (r) => `${fullDate(r.day)} (${r.das} ${t('DAS', 'DAS')})\n${f(r)}` }));
  draw(f1.body, { height: 220, x: { label: null }, y: { label: 'MJ/m²/d', zero: true }, marks: [...rules, Plot.lineY(rows, { x, y: 'srad', stroke: C.yellow, strokeWidth: 1.5 }), tipDay('srad', (r) => `${fmt(r.srad, 1)} MJ/m²/d`)] });
  draw(f2.body, { height: 220, x: { label: null }, y: { label: 'kPa', zero: true }, marks: [...rules, Plot.lineY(rows, { x, y: 'vpd', stroke: C.orange, strokeWidth: 1.5 }), tipDay('vpd', (r) => `${fmt(r.vpd, 2)} kPa`)] });
  const after = rows.filter((r) => r.das >= 0);
  draw(f3.body, { height: 220, x: { label: null }, y: { label: t('°C·day', '°C·dia'), zero: true }, marks: [...rules, Plot.lineY(after, { x, y: 'gdd_cum', stroke: C.violet, strokeWidth: 2 }), Plot.tip(after, Plot.pointerX({ x, y: 'gdd_cum', title: (r) => `${r.das} ${t('DAS', 'DAS')}: ${fmt(r.gdd_cum, 0)} ${t('°C·day', '°C·dia')}` }))] });
}

export const seasonTab = {
  id: 'safra', needsSite: true,
  get label() { return t('One season', 'Uma safra'); },
  async compute(ctx) {
    const { s } = ctx;
    if (!ctx.covered.includes(s.year)) {
      throw new Error(t(`The loaded weather does not cover the season sown on ${s.day}/${s.month}/${s.year} (30 days before and 130 days after sowing are needed). Choose another year.`,
        `O clima carregado não cobre a safra semeada em ${s.day}/${s.month}/${s.year} (são necessários 30 dias antes e 130 dias depois da semeadura). Escolha outro ano.`));
    }
    const base = ctx.season(s.year);
    const [main, rainfed, potential] = await ctx.run([base, { ...base, irrigated: false }, { ...base, irrigated: true }]);
    return { main, rainfed, potential };
  },

  render(ctx, { main, rainfed, potential }, el) {
    const { emu, s } = ctx, k = emu.keys, meta = emu.meta;
    const v = (row, name) => row.outputs[name] * meta[name].scale;
    const dateOf = (name) => main.sowing + Math.round(main.outputs[name]);
    const das = t('days after sowing', 'dias após a semeadura');
    const mgText = emu.family === 'dssat' ? `${t('MG', 'GM')} ${fmt(main.cultivar.mg, 1)}` : `${fmt(main.cultivar.gdd_maturity, 0)} °C·d ${t('to maturity', 'até a maturidade')}`;
    const scen = [s.dt ? `ΔT ${s.dt > 0 ? '+' : ''}${fmt(s.dt, 1)} °C` : '', s.rainFactor !== 1 ? `${t('rain', 'chuva')} ×${fmt(s.rainFactor, 2)}` : '', Number.isFinite(s.co2) ? `CO₂ ${fmt(s.co2, 0)} ppm` : `CO₂ ${fmt(main.inputs?.co2, 0)} ppm (Mauna Loa)`].filter(Boolean).join(' · ');
    const rows = Object.values(meta).map((m) => ({ ...m, value: v(main, m.name), rainfed: v(rainfed, m.name), potential: v(potential, m.name) }));

    el.append(header(t(`Season sown on ${fullDate(main.sowing)}`, `Safra semeada em ${fullDate(main.sowing)}`),
      `${emu.card.model.replace(' (official executable)', '')} · ${mgText} · ${s.irrigated ? t('no water stress', 'sem estresse hídrico') : t('rainfed', 'sequeiro')} · ${scen}`, [],
      exporter(`${t('season', 'safra')}_${ctx.isoDate(main.sowing)}_${emu.card.name}.csv`, rows.map((r) => ({
        [t('output', 'saida')]: r.name, [t('description', 'descricao')]: r.label, [t('unit', 'unidade')]: r.unit, [t('value', 'valor')]: r.value,
        [t('rainfed', 'sequeiro')]: r.rainfed, [t('no_water_stress', 'sem_estresse_hidrico')]: r.potential, [t('level', 'nivel')]: r.level })))));

    if (!main.ok) { el.append(h('div.empty.error', h('h2', t('Season not computed', 'Safra sem cálculo')), h('p', main.reason))); return; }

    // headline numbers
    const y = v(main, k.yield), yp = v(potential, k.yield), yr = v(rainfed, k.yield), gap = Math.max(yp - yr, 0), yu = meta[k.yield].unit;
    const tile = (label, value, unit, sub, cls = '') => h(`div.tile${cls}`, h('span.t-label', label), h('span.t-value', value, h('small', ` ${unit}`)), sub ? h('span.t-sub', sub) : null);
    el.append(h('div.tiles',
      tile(t('Grain yield', 'Produtividade de grãos'), fmt(y, 2), yu, s.irrigated ? `${t('rainfed', 'sequeiro')}: ${fmt(yr, 2)} ${yu}`
        : `${t('no water stress', 'sem estresse hídrico')}: ${fmt(yp, 2)} · ${t('gap', 'lacuna')} ${fmt(gap, 2)} (${fmt(100 * gap / yp, 0)} %)`, '.hero'),
      tile(t('Flowering', 'Floração'), shortDate(dateOf(k.flowering)), '', `${fmt(main.outputs[k.flowering], 0)} ${das}`),
      tile(t('Maturity', 'Maturidade'), shortDate(dateOf(k.maturity)), '', `${fmt(main.outputs[k.maturity], 0)} ${das}`),
      tile(t('Above-ground biomass', 'Biomassa aérea'), fmt(v(main, k.biomass), 2), meta[k.biomass].unit),
      tile(t('Rain in the cycle', 'Chuva no ciclo'), fmt(v(main, k.rain), 0), 'mm'),
      tile(t('Evapotranspiration', 'Evapotranspiração'), fmt(v(main, k.et), 0), 'mm'),
    ));

    // domain
    const outList = main.outOfDomain.map((name) => [name, main.inputs[name], emu.card.domain[name]]);
    el.append(h('section.card', h('h2', t('Reliability', 'Confiabilidade')), domainSummary([main]),
      outList.length ? table(outList, [[t('Input', 'Entrada'), (r) => h('code', r[0])], [t('Value', 'Valor'), (r) => auto(r[1]), 'num'], [t('Training range', 'Faixa de treino'), (r) => `${auto(r[2].min)} ${t('to', 'a')} ${auto(r[2].max)}`, 'num']]) : null,
      h('p.hint', t('Each output has an acceptance level from the 5° spatial block validation (the emulator tested on regions it did not see): recommended, caution or not recommended. Inputs outside the training domain make the season an extrapolation.',
        'Cada saída tem um nível de aceitação da validação por blocos espaciais de 5° (o emulador testado em regiões que não viu): recomendada, com cautela ou não recomendada. Entradas fora do domínio de treino tornam a safra uma extrapolação.'))));

    // weather of the cycle
    const ws = ctx.site.ws, end = Math.min(dateOf(k.maturity) + 15, main.sowing + 200);
    const days = [];
    let cr = 0, ce = 0;
    for (let d = main.sowing - 30; d <= end; d++) {
      const i = ws.index(d);
      if (i < 0 || i >= ws.n) continue;
      const date = new Date(d * 864e5), after = d >= main.sowing;
      if (after) { cr += ws.rain[i] * s.rainFactor; ce += ws.eto[i]; }
      days.push({ day: d, date, tmax: ws.tmax[i] + s.dt, tmin: ws.tmin[i] + s.dt, rain: ws.rain[i] * s.rainFactor, cumRain: after ? cr : null, cumEto: after ? ce : null });
    }
    const evNames = [t('sowing', 'semeadura'), t('flowering', 'floração'), t('maturity', 'maturidade')];
    const events = [main.sowing, dateOf(k.flowering), dateOf(k.maturity)].map((d, i) => ({ label: evNames[i], date: new Date(d * 864e5) }));
    const rules = [Plot.ruleX(events, { x: 'date', stroke: 'currentColor', strokeOpacity: 0.35, strokeDasharray: '3,3' }),
      Plot.text(events, { x: 'date', text: 'label', frameAnchor: 'top', dy: -2, dx: 4, textAnchor: 'start', fill: 'currentColor', fillOpacity: 0.7, fontSize: 10.5 })];
    const temp = figure(t('Daily temperature', 'Temperatura diária'), s.dt ? t(`With ΔT ${fmt(s.dt, 1)} °C applied.`, `Com ΔT ${fmt(s.dt, 1)} °C aplicado.`) : t('NASA POWER and/or your spreadsheet.', 'NASA POWER e/ou sua planilha.'), { legend: [['Tmax', C.orange], ['Tmin', C.blue]] });
    const rain = figure(t('Daily rain', 'Chuva diária'), s.rainFactor !== 1 ? t(`Multiplied by ${fmt(s.rainFactor, 2)}.`, `Multiplicada por ${fmt(s.rainFactor, 2)}.`) : null);
    const water = figure(t('Rain and demand accumulated since sowing', 'Chuva e demanda acumuladas desde a semeadura'),
      t('Reference evapotranspiration (FAO-56) shows the demand of the atmosphere; the crop’s is lower early in the cycle.', 'Evapotranspiração de referência (FAO-56) mostra a demanda da atmosfera; a da cultura é menor no início do ciclo.'),
      { legend: [[t('Accumulated rain', 'Chuva acumulada'), C.blue], [t('Accumulated ETo', 'ETo acumulada'), C.aqua]] });
    el.append(grid(temp.card, rain.card, water.card));
    draw(temp.body, { x: { label: null }, marginTop: 18, y: { label: '°C' }, marks: [
      Plot.areaY(days, { x: 'date', y1: 'tmin', y2: 'tmax', fill: C.orange, fillOpacity: 0.12 }),
      Plot.lineY(days, { x: 'date', y: 'tmax', stroke: C.orange, strokeWidth: 1.6 }),
      Plot.lineY(days, { x: 'date', y: 'tmin', stroke: C.blue, strokeWidth: 1.6 }),
      ...rules,
      Plot.tip(days, Plot.pointerX({ x: 'date', y: 'tmax', title: (d) => `${fullDate(d.day)}\nTmax ${fmt(d.tmax, 1)} °C\nTmin ${fmt(d.tmin, 1)} °C` })),
    ] });
    draw(rain.body, { x: { label: null }, marginTop: 18, y: { label: t('mm/day', 'mm/dia') }, marks: [
      Plot.rectY(days, { x: 'date', y: 'rain', interval: 'day', fill: C.rain, insetLeft: 0.3, insetRight: 0.3 }), Plot.ruleY([0]), ...rules,
      Plot.tip(days, Plot.pointerX({ x: 'date', y: 'rain', title: (d) => `${fullDate(d.day)}\n${fmt(d.rain, 1)} mm` })),
    ] });
    const after = days.filter((d) => d.cumRain != null);
    draw(water.body, { x: { label: null }, marginTop: 18, y: { label: 'mm' }, marks: [
      Plot.lineY(after, { x: 'date', y: 'cumRain', stroke: C.blue, strokeWidth: 2 }),
      Plot.lineY(after, { x: 'date', y: 'cumEto', stroke: C.aqua, strokeWidth: 2 }), Plot.ruleY([0]), ...rules,
      Plot.tip(after, Plot.pointerX({ x: 'date', y: 'cumRain', title: (d) => `${fullDate(d.day)}\n${t('rain', 'chuva')} ${fmt(d.cumRain, 0)} mm\nETo ${fmt(d.cumEto, 0)} mm` })),
    ] });

    growthCharts(ctx, main, potential, el);
    cycleWeather(ctx, main, el, dateOf(k.flowering), dateOf(k.maturity));

    // every output
    const byGroup = GROUP_ORDER.map((g) => [g, rows.filter((r) => r.group === g)]).filter(([, r]) => r.length);
    el.append(h('section.card', h('h2', t(`All model outputs (${rows.length})`, `Todas as saídas do modelo (${rows.length})`)),
      h('p.hint', t('Values of this season with the chosen management and, on the right, rainfed and without water stress. Dates in days after sowing.', 'Valores desta safra no manejo escolhido e, ao lado, em sequeiro e sem estresse hídrico. Datas em dias após a semeadura.')),
      byGroup.map(([g, list]) => h('div', h('h3.group', groupLabel(g)), table(list, [
        [t('Output', 'Saída'), (r) => h('span', r.label, ' ', h('code', r.name))],
        [t('Value', 'Valor'), (r) => h('strong', auto(r.value)), 'num'], [t('Unit', 'Unidade'), 'unit'],
        [t('Rainfed', 'Sequeiro'), (r) => auto(r.rainfed), 'num'], [t('No water stress', 'Sem estresse'), (r) => auto(r.potential), 'num'],
        [t('Acceptance', 'Aceitação'), (r) => levelBadge(r.level)], [t('Validation error', 'Erro de validação'), (r) => (Number.isFinite(r.rmse) ? `±${auto(r.rmse * r.scale)}` : '—'), 'num'],
      ])))));

    // inputs
    const status = { out: t('out of domain', 'fora do domínio'), rare: t('rare', 'rara'), fixed: t('fixed in training', 'fixa no treino'), ok: 'ok' };
    const inputs = emu.card.inputs.map((name) => {
      const d = emu.card.domain[name], x = main.inputs[name];
      return { name, x, ...d, st: x < d.min || x > d.max ? 'out' : x < d.q005 || x > d.q995 ? 'rare' : d.min === d.max ? 'fixed' : 'ok' };
    });
    el.append(h('details.card', h('summary', h('h2', t(`The ${inputs.length} inputs computed for the network`, `As ${inputs.length} entradas calculadas para a rede`))),
      h('p.hint', t('Computed from the daily weather (30-day windows from 30 days before sowing), the soil, the cultivar and the management — the same code as in training.', 'Calculadas a partir do clima diário (janelas de 30 dias a partir de 30 dias antes da semeadura), do solo, do cultivar e do manejo — o mesmo código do treino.')),
      table(inputs, [[t('Input', 'Entrada'), (r) => h('code', r.name)], [t('Value', 'Valor'), (r) => auto(r.x), 'num'], [t('Training min.', 'Mín. treino'), (r) => auto(r.min), 'num'],
        ['0.5 %', (r) => auto(r.q005), 'num'], ['99.5 %', (r) => auto(r.q995), 'num'], [t('Training max.', 'Máx. treino'), (r) => auto(r.max), 'num'],
        [t('Status', 'Situação'), (r) => h(`span.st.${r.st}`, status[r.st])]])));
  },
};
