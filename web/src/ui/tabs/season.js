// One season: every output, domain flags, the weather of the cycle and the inputs.

import { brDate, isoDate, shortDate } from '../../engine/dates.js';
import { download, toCsv } from '../../engine/io.js';
import { etoDay, gdd } from '../../engine/weather.js';
import { C, draw, figure, Plot } from '../charts.js';
import { domainSummary, exporter, grid, header, levelBadge, table } from '../common.js';
import { auto, fmt, h, mean } from '../dom.js';

/** Beta growth function (Yin et al., 2003): 0 at t=0, wmax at t=te, inflection at tm (0 < tm < te). */
const beta = (t, te, tm, wmax) => (t <= 0 ? 0 : t >= te ? wmax : wmax * (1 + (te - t) / (te - tm)) * (t / te) ** (te / (te - tm)));

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
    const t = d - emr;
    const canopy = d < emr ? 0 : d <= peak ? beta(t, peak - emr, 0.6 * (peak - emr), canopyMax)
      : canopyMax * (1 - (1 - end) * ((d - peak) / (mat - peak)) ** 1.6);
    pts.push({ das: d, bio: beta(t, mat - emr, 0.55 * (mat - emr), bio), grain: d < seedStart ? 0 : beta(d - seedStart, mat - seedStart, 0.5 * (mat - seedStart), grain), canopy });
  }
  return { pts, emr, flo, mat, peak, bio, grain, canopyMax };
}

function growthCharts(ctx, main, potential, el) {
  const { emu } = ctx, dssat = emu.family === 'dssat', m = emu.meta, k = emu.keys;
  const c = curves(emu, main), p = curves(emu, potential);
  if (!c) return;
  const label = main.irrigated ? 'Sem estresse hídrico' : 'Sequeiro';
  const date = (das) => new Date((main.sowing + das) * 864e5);
  const note = 'Pontos: valores previstos pelo emulador. Linha: curva esquemática (função beta de crescimento) passando pelos pontos — o emulador prevê os valores da safra, não a série diária.';
  const fb = figure('Biomassa aérea e grãos ao longo do ciclo', note, { legend: [[`Biomassa (${label.toLowerCase()})`, C.green], ['Grãos', C.yellow], ...(main.irrigated ? [] : [['Sem estresse hídrico', C.gray, 'dash']])] });
  const canopyLabel = dssat ? 'Índice de área foliar (IAF)' : 'Cobertura do dossel';
  const fl = figure(`${canopyLabel} ao longo do ciclo`, dssat ? 'Ponto: IAF máximo previsto (LAIX); a data do máximo é suposta entre a floração e a maturidade.' : 'Ponto: cobertura máxima prevista (CC_max); a data do máximo é suposta entre a floração e a maturidade.',
    { legend: [[label, C.aqua], ...(main.irrigated ? [] : [['Sem estresse hídrico', C.gray, 'dash']])] });
  el.append(grid(fb.card, fl.card));
  const stages = [['emergência', c.emr], ['floração', c.flo], ['maturidade', c.mat]].map(([s, d]) => ({ s, x: date(d) }));
  const stageMarks = [Plot.ruleX(stages, { x: 'x', stroke: 'currentColor', strokeOpacity: 0.3, strokeDasharray: '3,3' }),
    Plot.text(stages, { x: 'x', text: 's', frameAnchor: 'top', dy: -2, dx: 4, textAnchor: 'start', fill: 'currentColor', fillOpacity: 0.7, fontSize: 10.5 })];
  const pot = main.irrigated || !p ? [] : p.pts;
  const bioUnit = m[k.biomass].unit;
  const bioPoints = [{ x: date(c.emr), y: 0, t: 'emergência' }, { x: date(c.mat), y: c.bio, t: `biomassa ${fmt(c.bio, 2)} ${bioUnit}` }];
  const grainPoint = [{ x: date(c.mat), y: c.grain, t: `grãos ${fmt(c.grain, 2)} ${m[k.yield].unit}` }];
  draw(fb.body, { marginTop: 18, x: { label: null }, y: { label: bioUnit, zero: true }, marks: [
    ...stageMarks,
    Plot.lineY(pot, { x: (d) => date(d.das), y: 'bio', stroke: C.gray, strokeWidth: 1.5, strokeDasharray: '5,4' }),
    Plot.lineY(c.pts, { x: (d) => date(d.das), y: 'bio', stroke: C.green, strokeWidth: 2 }),
    Plot.lineY(c.pts, { x: (d) => date(d.das), y: 'grain', stroke: C.yellow, strokeWidth: 2 }),
    Plot.dot(bioPoints, { x: 'x', y: 'y', r: 5.5, fill: C.green, stroke: 'var(--surface)', strokeWidth: 1.5, tip: true, title: 't' }),
    Plot.dot(grainPoint, { x: 'x', y: 'y', r: 5.5, fill: C.yellow, stroke: 'var(--surface)', strokeWidth: 1.5, tip: true, title: 't' }),
    p && !main.irrigated ? Plot.dot([{ x: date(p.mat), y: p.bio }], { x: 'x', y: 'y', r: 4.5, fill: 'var(--surface)', stroke: C.gray, strokeWidth: 1.5, tip: true, title: () => `sem estresse: biomassa ${fmt(p.bio, 2)} ${bioUnit}` }) : null,
    Plot.ruleY([0]),
  ] });
  const cu = dssat ? 'm²/m²' : '%';
  draw(fl.body, { marginTop: 18, x: { label: null }, y: { label: cu, zero: true }, marks: [
    ...stageMarks,
    Plot.lineY(pot, { x: (d) => date(d.das), y: 'canopy', stroke: C.gray, strokeWidth: 1.5, strokeDasharray: '5,4' }),
    Plot.areaY(c.pts, { x: (d) => date(d.das), y: 'canopy', fill: C.aqua, fillOpacity: 0.1 }),
    Plot.lineY(c.pts, { x: (d) => date(d.das), y: 'canopy', stroke: C.aqua, strokeWidth: 2 }),
    Plot.dot([{ x: date(c.peak), y: c.canopyMax }], { x: 'x', y: 'y', r: 5.5, fill: C.aqua, stroke: 'var(--surface)', strokeWidth: 1.5, tip: true, title: () => `${dssat ? 'IAF máximo' : 'cobertura máxima'}: ${fmt(c.canopyMax, dssat ? 2 : 0)} ${cu}` }),
    p && !main.irrigated ? Plot.dot([{ x: date(p.peak), y: p.canopyMax }], { x: 'x', y: 'y', r: 4.5, fill: 'var(--surface)', stroke: C.gray, strokeWidth: 1.5, tip: true, title: () => `sem estresse: ${fmt(p.canopyMax, dssat ? 2 : 0)} ${cu}` }) : null,
    Plot.ruleY([0]),
  ] });
}

const SOURCE = ['', 'sua planilha', 'NASA POWER', 'preenchido'];

/** Daily weather of the cycle (30 days before sowing to 15 days after maturity), with the scenario
 * (ΔT, rain factor) applied as in the emulator inputs: summary by phase, charts, table and CSV. */
function cycleWeather(ctx, main, el, floDay, matDay) {
  const { site, s } = ctx, ws = site.ws, t = site.table, cols = t.cols;
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
    rows.push({ data: isoDate(d), das, fase: das < 0 ? 'pré-semeadura' : d < floDay ? 'vegetativa' : d <= matDay ? 'reprodutiva' : 'pós-maturidade',
      tmax, tmin, srad: ws.srad[i], chuva: rain, umidade: cols.rhum[i], vento: cols.wind[i], orvalho: cols.dewp[i],
      eto, dpv: ws.vpd[i], fotoperiodo: ws.dayl[i], graus_dia: g, graus_dia_acum: das >= 0 ? cumGdd : null, chuva_acum: das >= 0 ? cumRain : null,
      fonte_tmax: SOURCE[t.src.tmax[i]], fonte_chuva: SOURCE[t.src.rain[i]], fonte_rad: SOURCE[t.src.srad[i]] });
  }
  const phases = ['pré-semeadura', 'vegetativa', 'reprodutiva'].map((f) => {
    const r = rows.filter((x) => x.fase === f), sum = (k) => r.reduce((a, x) => a + (x[k] ?? 0), 0);
    return { f, dias: r.length, tmax: mean(r.map((x) => x.tmax)), tmin: mean(r.map((x) => x.tmin)), srad: mean(r.map((x) => x.srad)), chuva: sum('chuva'), eto: sum('eto'),
      dpv: mean(r.map((x) => x.dpv)), quentes: r.filter((x) => x.tmax >= 32).length, gd: sum('graus_dia'), dias_secos: r.filter((x) => x.chuva < 1).length };
  });
  const name = `clima_ciclo_${isoDate(main.sowing)}.csv`;
  const scen = s.dt || s.rainFactor !== 1 ? ` Valores com o cenário aplicado (ΔT ${fmt(s.dt, 1)} °C, chuva ×${fmt(s.rainFactor, 2)}), como nas entradas do emulador.` : '';
  const sec = h('section.card', h('div.card-head', h('h2', 'Clima do ciclo'),
    h('button.secondary', { type: 'button', onclick: () => download(name, toCsv(rows)) }, 'Baixar clima do ciclo (CSV)')),
    h('p.hint', `Dias de ${brDate(first)} a ${brDate(last)}: 30 dias antes da semeadura até 15 dias após a maturidade.${scen}`),
    table(phases, [['Fase', (r) => ({ 'pré-semeadura': '30 dias antes da semeadura', vegetativa: 'Semeadura → floração', reprodutiva: 'Floração → maturidade' })[r.f]], ['Dias', 'dias', 'num'],
      ['Tmax (°C)', (r) => fmt(r.tmax, 1), 'num'], ['Tmin (°C)', (r) => fmt(r.tmin, 1), 'num'], ['Radiação (MJ/m²/d)', (r) => fmt(r.srad, 1), 'num'],
      ['Chuva (mm)', (r) => fmt(r.chuva, 0), 'num'], ['ETo (mm)', (r) => fmt(r.eto, 0), 'num'], ['Chuva − ETo', (r) => fmt(r.chuva - r.eto, 0), 'num'],
      ['DPV (kPa)', (r) => fmt(r.dpv, 2), 'num'], ['Dias ≥ 32 °C', 'quentes', 'num'], ['Dias sem chuva', 'dias_secos', 'num'], ['Graus-dia', (r) => fmt(r.gd, 0), 'num']]));
  const f1 = figure('Radiação solar diária', 'MJ/m²/dia.');
  const f2 = figure('Déficit de pressão de vapor', 'kPa; quanto maior, mais seca a atmosfera.');
  const f3 = figure('Graus-dia acumulados desde a semeadura', 'Base 5 °C, teto 30 °C (método do AquaCrop).');
  sec.append(h('div.grid.inner', f1.card, f2.card, f3.card));
  const daily = h('details', h('summary', `Ver a tabela diária (${rows.length} dias)`), table(rows, [
    ['Data', (r) => brDate(Math.round(Date.parse(r.data) / 864e5))], ['DAS', 'das', 'num'], ['Tmax', (r) => fmt(r.tmax, 1), 'num'], ['Tmin', (r) => fmt(r.tmin, 1), 'num'],
    ['Rad.', (r) => fmt(r.srad, 1), 'num'], ['Chuva', (r) => fmt(r.chuva, 1), 'num'], ['UR %', (r) => fmt(r.umidade, 0), 'num'], ['Vento', (r) => fmt(r.vento, 1), 'num'],
    ['ETo', (r) => fmt(r.eto, 1), 'num'], ['DPV', (r) => fmt(r.dpv, 2), 'num'], ['Fotoper.', (r) => fmt(r.fotoperiodo, 2), 'num'], ['Fonte', 'fonte_tmax']], '.scroll'));
  sec.append(daily);
  el.append(sec);
  const x = (r) => new Date(Date.parse(r.data));
  const rules = [Plot.ruleX([main.sowing, floDay, matDay].map((d) => new Date(d * 864e5)), { stroke: 'currentColor', strokeOpacity: 0.3, strokeDasharray: '3,3' })];
  const tipDay = (y, f) => Plot.tip(rows, Plot.pointerX({ x, y, title: (r) => `${brDate(Math.round(Date.parse(r.data) / 864e5))} (${r.das} DAS)\n${f(r)}` }));
  draw(f1.body, { height: 220, x: { label: null }, y: { label: 'MJ/m²/d', zero: true }, marks: [...rules, Plot.lineY(rows, { x, y: 'srad', stroke: C.yellow, strokeWidth: 1.5 }), tipDay('srad', (r) => `${fmt(r.srad, 1)} MJ/m²/d`)] });
  draw(f2.body, { height: 220, x: { label: null }, y: { label: 'kPa', zero: true }, marks: [...rules, Plot.lineY(rows, { x, y: 'dpv', stroke: C.orange, strokeWidth: 1.5 }), tipDay('dpv', (r) => `${fmt(r.dpv, 2)} kPa`)] });
  const after = rows.filter((r) => r.das >= 0);
  draw(f3.body, { height: 220, x: { label: null }, y: { label: '°C·dia', zero: true }, marks: [...rules, Plot.lineY(after, { x, y: 'graus_dia_acum', stroke: C.violet, strokeWidth: 2 }), Plot.tip(after, Plot.pointerX({ x, y: 'graus_dia_acum', title: (r) => `${r.das} DAS: ${fmt(r.graus_dia_acum, 0)} °C·dia` }))] });
}

const GROUPS = ['produção', 'fenologia', 'água', 'estresses', 'eficiência', 'nitrogênio e carbono', 'clima do ciclo', 'outros'];

export const seasonTab = {
  id: 'safra', label: 'Uma safra', needsSite: true,
  async compute(ctx) {
    const { s } = ctx;
    if (!ctx.covered.includes(s.year)) {
      throw new Error(`O clima carregado não cobre a safra semeada em ${s.day}/${s.month}/${s.year} (são necessários 30 dias antes e 130 dias depois da semeadura). Escolha outro ano.`);
    }
    const base = ctx.season(s.year);
    const [main, rainfed, potential] = await ctx.run([base, { ...base, irrigated: false }, { ...base, irrigated: true }]);
    return { main, rainfed, potential };
  },

  render(ctx, { main, rainfed, potential }, el) {
    const { emu, s } = ctx, k = emu.keys, meta = emu.meta;
    const v = (row, name) => row.outputs[name] * meta[name].scale;
    const dateOf = (name) => main.sowing + Math.round(main.outputs[name]);
    const mgText = emu.family === 'dssat' ? `GM ${fmt(main.cultivar.mg, 1)}` : `${fmt(main.cultivar.gdd_maturity, 0)} °C·d até a maturidade`;
    const scen = [s.dt ? `ΔT ${s.dt > 0 ? '+' : ''}${fmt(s.dt, 1)} °C` : '', s.rainFactor !== 1 ? `chuva ×${fmt(s.rainFactor, 2)}` : '', Number.isFinite(s.co2) ? `CO₂ ${fmt(s.co2, 0)} ppm` : `CO₂ ${fmt(main.inputs?.co2, 0)} ppm (Mauna Loa)`].filter(Boolean).join(' · ');
    const rows = Object.values(meta).map((m) => ({ ...m, value: v(main, m.name), rainfed: v(rainfed, m.name), potential: v(potential, m.name) }));

    el.append(header(`Safra semeada em ${brDate(main.sowing)}`,
      `${emu.card.model.replace(' (official executable)', '')} · ${mgText} · ${s.irrigated ? 'sem estresse hídrico' : 'sequeiro'} · ${scen}`, [],
      exporter(`safra_${ctx.isoDate(main.sowing)}_${emu.card.name}.csv`, rows.map((r) => ({ saida: r.name, descricao: r.label, unidade: r.unit, valor: r.value, sequeiro: r.rainfed, sem_estresse_hidrico: r.potential, nivel: r.level })))));

    if (!main.ok) { el.append(h('div.empty.error', h('h2', 'Safra sem cálculo'), h('p', main.reason))); return; }

    // headline numbers
    const y = v(main, k.yield), yp = v(potential, k.yield), yr = v(rainfed, k.yield), gap = Math.max(yp - yr, 0);
    const tile = (label, value, unit, sub, cls = '') => h(`div.tile${cls}`, h('span.t-label', label), h('span.t-value', value, h('small', ` ${unit}`)), sub ? h('span.t-sub', sub) : null);
    el.append(h('div.tiles',
      tile('Produtividade de grãos', fmt(y, 2), meta[k.yield].unit, s.irrigated ? `sequeiro: ${fmt(yr, 2)} ${meta[k.yield].unit}` : `sem estresse hídrico: ${fmt(yp, 2)} · lacuna ${fmt(gap, 2)} (${fmt(100 * gap / yp, 0)} %)`, '.hero'),
      tile('Floração', shortDate(dateOf(k.flowering)), '', `${fmt(main.outputs[k.flowering], 0)} dias após a semeadura`),
      tile('Maturidade', shortDate(dateOf(k.maturity)), '', `${fmt(main.outputs[k.maturity], 0)} dias após a semeadura`),
      tile('Biomassa aérea', fmt(v(main, k.biomass), 2), meta[k.biomass].unit),
      tile('Chuva no ciclo', fmt(v(main, k.rain), 0), 'mm'),
      tile('Evapotranspiração', fmt(v(main, k.et), 0), 'mm'),
    ));

    // domain
    const outList = main.outOfDomain.map((name) => [name, main.inputs[name], emu.card.domain[name]]);
    el.append(h('section.card', h('h2', 'Confiabilidade'), domainSummary([main], 'safra'),
      outList.length ? table(outList, [['Entrada', (r) => h('code', r[0])], ['Valor', (r) => auto(r[1]), 'num'], ['Faixa de treino', (r) => `${auto(r[2].min)} a ${auto(r[2].max)}`, 'num']]) : null,
      h('p.hint', 'Cada saída tem um nível de aceitação da validação por blocos espaciais de 5° (o emulador testado em regiões que não viu): recomendada, com cautela ou não recomendada. Entradas fora do domínio de treino tornam a safra uma extrapolação.')));

    // weather of the cycle
    const ws = ctx.site.ws, end = Math.min(dateOf(k.maturity) + 15, main.sowing + 200);
    const days = [];
    let cr = 0, ce = 0;
    for (let d = main.sowing - 30; d <= end; d++) {
      const i = ws.index(d);
      if (i < 0 || i >= ws.n) continue;
      const date = new Date(d * 864e5), after = d >= main.sowing;
      if (after) { cr += ws.rain[i] * s.rainFactor; ce += ws.eto[i]; }
      days.push({ date, tmax: ws.tmax[i] + s.dt, tmin: ws.tmin[i] + s.dt, rain: ws.rain[i] * s.rainFactor, cumRain: after ? cr : null, cumEto: after ? ce : null });
    }
    const events = [['semeadura', main.sowing], ['floração', dateOf(k.flowering)], ['maturidade', dateOf(k.maturity)]].map(([label, d]) => ({ label, date: new Date(d * 864e5) }));
    const rules = [Plot.ruleX(events, { x: 'date', stroke: 'currentColor', strokeOpacity: 0.35, strokeDasharray: '3,3' }),
      Plot.text(events, { x: 'date', text: 'label', frameAnchor: 'top', dy: -2, dx: 4, textAnchor: 'start', fill: 'currentColor', fillOpacity: 0.7, fontSize: 10.5 })];
    const temp = figure('Temperatura diária', s.dt ? `Com ΔT ${fmt(s.dt, 1)} °C aplicado.` : 'NASA POWER e/ou sua planilha.', { legend: [['Tmax', C.orange], ['Tmin', C.blue]] });
    const rain = figure('Chuva diária', s.rainFactor !== 1 ? `Multiplicada por ${fmt(s.rainFactor, 2)}.` : null);
    const water = figure('Chuva e demanda acumuladas desde a semeadura', 'Evapotranspiração de referência (FAO-56) mostra a demanda da atmosfera; a da cultura é menor no início do ciclo.', { legend: [['Chuva acumulada', C.blue], ['ETo acumulada', C.aqua]] });
    el.append(grid(temp.card, rain.card, water.card));
    const dateTip = { x: { label: null }, };
    draw(temp.body, { ...dateTip, marginTop: 18, y: { label: '°C' }, marks: [
      Plot.areaY(days, { x: 'date', y1: 'tmin', y2: 'tmax', fill: C.orange, fillOpacity: 0.12 }),
      Plot.lineY(days, { x: 'date', y: 'tmax', stroke: C.orange, strokeWidth: 1.6 }),
      Plot.lineY(days, { x: 'date', y: 'tmin', stroke: C.blue, strokeWidth: 1.6 }),
      ...rules,
      Plot.tip(days, Plot.pointerX({ x: 'date', y: 'tmax', title: (d) => `${d.date.toLocaleDateString('pt-BR', { timeZone: 'UTC' })}\nTmax ${fmt(d.tmax, 1)} °C\nTmin ${fmt(d.tmin, 1)} °C` })),
    ] });
    draw(rain.body, { ...dateTip, marginTop: 18, y: { label: 'mm/dia' }, marks: [
      Plot.rectY(days, { x: 'date', y: 'rain', interval: 'day', fill: C.rain, insetLeft: 0.3, insetRight: 0.3 }), Plot.ruleY([0]), ...rules,
      Plot.tip(days, Plot.pointerX({ x: 'date', y: 'rain', title: (d) => `${d.date.toLocaleDateString('pt-BR', { timeZone: 'UTC' })}\n${fmt(d.rain, 1)} mm` })),
    ] });
    const after = days.filter((d) => d.cumRain != null);
    draw(water.body, { ...dateTip, marginTop: 18, y: { label: 'mm' }, marks: [
      Plot.lineY(after, { x: 'date', y: 'cumRain', stroke: C.blue, strokeWidth: 2 }),
      Plot.lineY(after, { x: 'date', y: 'cumEto', stroke: C.aqua, strokeWidth: 2 }), Plot.ruleY([0]), ...rules,
      Plot.tip(after, Plot.pointerX({ x: 'date', y: 'cumRain', title: (d) => `${d.date.toLocaleDateString('pt-BR', { timeZone: 'UTC' })}\nchuva ${fmt(d.cumRain, 0)} mm\nETo ${fmt(d.cumEto, 0)} mm` })),
    ] });

    growthCharts(ctx, main, potential, el);
    cycleWeather(ctx, main, el, dateOf(k.flowering), dateOf(k.maturity));

    // every output
    const byGroup = GROUPS.map((g) => [g, rows.filter((r) => r.group === g)]).filter(([, r]) => r.length);
    el.append(h('section.card', h('h2', `Todas as saídas do modelo (${rows.length})`),
      h('p.hint', 'Valores desta safra no manejo escolhido e, ao lado, em sequeiro e sem estresse hídrico. Datas em dias após a semeadura.'),
      byGroup.map(([g, list]) => h('div', h('h3.group', g[0].toUpperCase() + g.slice(1)), table(list, [
        ['Saída', (r) => h('span', r.label, ' ', h('code', r.name))],
        ['Valor', (r) => h('strong', auto(r.value)), 'num'], ['Unidade', 'unit'],
        ['Sequeiro', (r) => auto(r.rainfed), 'num'], ['Sem estresse', (r) => auto(r.potential), 'num'],
        ['Aceitação', (r) => levelBadge(r.level)], ['Erro de validação', (r) => (Number.isFinite(r.rmse) ? `±${auto(r.rmse * r.scale)}` : '—'), 'num'],
      ])))));

    // inputs
    const inputs = emu.card.inputs.map((name) => {
      const d = emu.card.domain[name], x = main.inputs[name];
      return { name, x, ...d, status: x < d.min || x > d.max ? 'fora do domínio' : x < d.q005 || x > d.q995 ? 'rara' : d.min === d.max ? 'fixa no treino' : 'ok' };
    });
    el.append(h('details.card', h('summary', h('h2', `As ${inputs.length} entradas calculadas para a rede`)),
      h('p.hint', 'Calculadas a partir do clima diário (janelas de 30 dias a partir de 30 dias antes da semeadura), do solo, do cultivar e do manejo — o mesmo código do treino.'),
      table(inputs, [['Entrada', (r) => h('code', r.name)], ['Valor', (r) => auto(r.x), 'num'], ['Mín. treino', (r) => auto(r.min), 'num'], ['0,5 %', (r) => auto(r.q005), 'num'], ['99,5 %', (r) => auto(r.q995), 'num'], ['Máx. treino', (r) => auto(r.max), 'num'],
        ['Situação', (r) => h(`span.st.${r.status.replace(/\s.*/, '')}`, r.status)]])));
  },
};
