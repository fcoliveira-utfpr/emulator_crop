// Climate scenarios as in training: warming added to Tmax and Tmin, CO₂, rain factor.

import { t } from '../../i18n.js';
import { C, draw, figure, Plot } from '../charts.js';
import { exporter, grid, header, levelNote, table, variableSelect } from '../common.js';
import { auto, fmt, h, mean, numberList } from '../dom.js';

export const scenariosTab = {
  id: 'cenarios', needsSite: true,
  get label() { return t('Climate scenarios', 'Cenários climáticos'); },
  defaults: { dts: '-1 0 1 2 3 4', co2s: '400 500 600 700 800', rfs: '0.7 0.8 0.9 1 1.1 1.2 1.3' },

  async compute(ctx) {
    const st = ctx.tabState('cenarios', this.defaults);
    if (!ctx.years.length) throw new Error(t('No year of the period has complete weather.', 'Nenhum ano do período tem clima completo.'));
    const dts = numberList(st.dts).slice(0, 10), co2s = numberList(st.co2s).slice(0, 10), rfs = numberList(st.rfs).slice(0, 12);
    const cultivar = ctx.cultivar();
    const base = { cultivar, dt: 0, rainFactor: 1, co2: NaN };
    const list = [];
    const add = (tag, extra) => ctx.years.forEach((y) => list.push(ctx.season(y, { ...base, ...extra, tag })));
    add('base', {});
    dts.forEach((dt) => co2s.forEach((co2) => add(`g:${dt}:${co2}`, { dt, co2 })));
    dts.forEach((dt) => add(`t:${dt}`, { dt }));
    rfs.forEach((rf) => add(`r:${rf}`, { rainFactor: rf }));
    const rows = await ctx.run(list);
    return { rows, dts, co2s, rfs, st };
  },

  render(ctx, { rows, dts, co2s, rfs, st }, el) {
    const { emu } = ctx, mv = emu.meta[ctx.variable], V = ctx.variable;
    const by = {};
    for (const r of rows) (by[r.tag] ??= []).push(r);
    const m = (tag) => mean((by[tag] ?? []).map((r) => r.outputs[V] * mv.scale));
    const b = m('base'), change = (tag) => 100 * (m(tag) / b - 1);
    const absolute = !(Math.abs(b) > 1e-6) || /dap$/.test(V);
    const metric = (tag) => (absolute ? m(tag) - b : change(tag));
    const unit = absolute ? mv.unit : '%';
    const what = absolute ? t('Difference of the mean', 'Diferença da média') : t('Change of the mean', 'Mudança da média');
    const gridData = dts.flatMap((dt) => co2s.map((co2) => ({ dt, co2, c: metric(`g:${dt}:${co2}`), v: m(`g:${dt}:${co2}`) })));
    const tData = dts.map((dt) => ({ dt, c: metric(`t:${dt}`), v: m(`t:${dt}`) }));
    const rData = rfs.map((rf) => ({ rf, c: metric(`r:${rf}`), v: m(`r:${rf}`) }));
    const co2Obs = mean((by.base ?? []).map((r) => r.inputs?.co2));
    const s = ctx.tabState('cenarios');
    const listInput = (label, key, width) => h('label.inline', h('span', label), h('input', { type: 'text', value: st[key], style: { width }, onchange: (e) => { s[key] = e.target.value; ctx.refresh(); } }));
    const period = `${ctx.years.length} ${t('seasons', 'safras')} (${ctx.years[0]}–${ctx.years.at(-1)})`;
    const meanLabel = t('mean', 'média');

    el.append(header(t('Climate scenarios', 'Cenários climáticos'),
      t(`Perturbations of the observed weather as in training (ΔT on the maximum and minimum temperatures, rain multiplied, fixed CO₂), applied to ${period}. ${what} relative to the observed weather with Mauna Loa CO₂ (${fmt(co2Obs, 0)} ppm on average). The ΔT, rain and CO₂ fields of the sidebar do not apply here.`,
        `Perturbações do clima observado iguais às do treino (ΔT nas temperaturas máxima e mínima, chuva multiplicada, CO₂ fixo), aplicadas a ${period}. ${what} em relação ao clima observado com CO₂ de Mauna Loa (${fmt(co2Obs, 0)} ppm em média). Os campos ΔT, chuva e CO₂ da barra lateral não se aplicam aqui.`),
      [listInput('ΔT (°C)', 'dts', '9em'), listInput('CO₂ (ppm)', 'co2s', '11em'), listInput(t('rain ×', 'chuva ×'), 'rfs', '12em'), variableSelect(ctx)],
      exporter(`${t('scenarios', 'cenarios')}_${emu.card.name}.csv`, [
        ...gridData.map((d) => ({ [t('scenario', 'cenario')]: 'dT x CO2', dT: d.dt, co2: d.co2, [t('rain_factor', 'fator_chuva')]: 1, [meanLabel]: d.v, [t('change', 'mudanca')]: d.c })),
        ...tData.map((d) => ({ [t('scenario', 'cenario')]: t('dT, observed CO2', 'dT, CO2 observado'), dT: d.dt, co2: '', [t('rain_factor', 'fator_chuva')]: 1, [meanLabel]: d.v, [t('change', 'mudanca')]: d.c })),
        ...rData.map((d) => ({ [t('scenario', 'cenario')]: t('rain', 'chuva'), dT: 0, co2: '', [t('rain_factor', 'fator_chuva')]: d.rf, [meanLabel]: d.v, [t('change', 'mudanca')]: d.c })),
        { [t('scenario', 'cenario')]: 'base', dT: 0, co2: '', [t('rain_factor', 'fator_chuva')]: 1, [meanLabel]: b, [t('change', 'mudanca')]: 0 }])));
    const note = levelNote(ctx, V); if (note) el.append(note);
    el.append(h('div.tiles', h('div.tile', h('span.t-label', t('Mean with the observed weather', 'Média com o clima observado')), h('span.t-value', `${auto(b)} ${mv.unit}`),
      h('span.t-sub', `${ctx.s.irrigated ? t('no water stress', 'sem estresse hídrico') : t('rainfed', 'sequeiro')} · ${ctx.years.length} ${t('years', 'anos')}`))));

    const lim = Math.max(1e-9, ...gridData.map((d) => Math.abs(d.c)).filter(Number.isFinite));
    const outside = (dt, co2) => dt < -1 || dt > 4 || co2 < 350 || co2 > 800;
    const f1 = figure(`${mv.label}: ${t('warming × CO₂', 'aquecimento × CO₂')}`, t(`${what} (${unit}). Cells with a border: outside the training range.`, `${what} (${unit}). Células com borda: fora da faixa de treino.`));
    const f2 = figure(t('Warming with the observed CO₂', 'Aquecimento com o CO₂ observado'), `${what} (${unit}).`);
    const f3 = figure(t('Rain', 'Chuva'), t(`${what} (${unit}). Training range: ×0.7 to ×1.3.`, `${what} (${unit}). Faixa de treino: ×0,7 a ×1,3.`));
    el.append(grid(f1.card, f2.card, f3.card));
    const sign = (c) => `${c > 0 ? '+' : ''}${fmt(c, 1)} %`;
    draw(f1.body, { height: 300, marginLeft: 48, x: { label: 'CO₂ (ppm)', type: 'band', domain: co2s }, y: { label: 'ΔT (°C)', type: 'band', domain: [...dts].reverse(), grid: false },
      color: { type: 'diverging', scheme: 'rdbu', domain: [-lim, lim], legend: true, label: unit, width: 280 },
      marks: [
        Plot.cell(gridData.filter((d) => outside(d.dt, d.co2)), { x: 'co2', y: 'dt', inset: 0.5, rx: 3, fill: 'none', stroke: 'currentColor', strokeOpacity: 0.6, strokeDasharray: '3,2' }),
        Plot.cell(gridData, { x: 'co2', y: 'dt', fill: 'c', inset: 1.5, rx: 3, tip: true, title: (d) => `ΔT ${fmt(d.dt, 1)} °C, CO₂ ${d.co2} ppm\n${meanLabel} ${auto(d.v)} ${mv.unit}\n${absolute ? '' : sign(d.c)}` }),
        Plot.text(gridData, { x: 'co2', y: 'dt', text: (d) => `${d.c > 0 ? '+' : ''}${absolute ? auto(d.c) : fmt(d.c, 0)}`, fill: (d) => (Math.abs(d.c) > lim * 0.55 ? 'white' : 'currentColor'), fontSize: 11 }),
      ] });
    const line = (body, data, x, label) => draw(body, { x: { label }, y: { label: unit }, marks: [
      Plot.ruleY([0], { stroke: 'currentColor', strokeOpacity: 0.4 }),
      Plot.lineY(data, { x, y: 'c', stroke: C.blue, strokeWidth: 2, marker: 'circle-stroke' }),
      Plot.tip(data, Plot.pointerX({ x, y: 'c', title: (d) => `${label}: ${fmt(d[x], 2)}\n${meanLabel} ${auto(d.v)} ${mv.unit}\n${absolute ? `${auto(d.c)} ${mv.unit}` : sign(d.c)}` })),
    ] });
    line(f2.body, tData, 'dt', 'ΔT (°C)');
    line(f3.body, rData, 'rf', t('rain factor', 'fator de chuva'));

    el.append(h('details.card', h('summary', h('h2', t('Table', 'Tabela'))), table(gridData, [['ΔT (°C)', (r) => fmt(r.dt, 1), 'num'], ['CO₂ (ppm)', 'co2', 'num'],
      [`${t('Mean', 'Média')} (${mv.unit})`, (r) => auto(r.v), 'num'], [absolute ? `${t('Difference', 'Diferença')} (${mv.unit})` : t('Change (%)', 'Mudança (%)'), (r) => fmt(r.c, 1), 'num']])));
  },
};
