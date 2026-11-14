// Sowing window: every sowing date of a window in every year.

import { fromYMD, monthName, shortDate } from '../../engine/dates.js';
import { C, draw, figure, Plot } from '../charts.js';
import { domainSummary, exporter, grid, header, levelNote, table, variableSelect } from '../common.js';
import { auto, fmt, h, quantile } from '../dom.js';
import { t } from '../../i18n.js';

function dayMonth(label, value, onChange) {
  const [d, m] = value;
  const day = h('select', { 'aria-label': `${label}: ${t('day', 'dia')}` }, Array.from({ length: 31 }, (_, i) => h('option', { value: i + 1 }, i + 1)));
  const month = h('select', { 'aria-label': `${label}: ${t('month', 'mês')}` }, Array.from({ length: 12 }, (_, i) => h('option', { value: i + 1 }, monthName(i + 1))));
  day.value = d; month.value = m;
  const fire = () => onChange([+day.value, +month.value]);
  day.onchange = fire; month.onchange = fire;
  return h('label.inline', h('span', label), day, month);
}

export const windowTab = {
  id: 'janela', needsSite: true,
  get label() { return t('Sowing window', 'Janela de semeadura'); },
  defaults: (ctx) => (ctx.site.lat < 0 ? { start: [1, 9], end: [31, 12], step: 4, pct: 20 } : { start: [1, 4], end: [30, 6], step: 4, pct: 20 }),

  async compute(ctx) {
    const st = ctx.tabState(`janela${Math.sign(ctx.site.lat)}`, this.defaults(ctx));
    if (!ctx.years.length) throw new Error(t('No year of the period has complete weather.', 'Nenhum ano do período tem clima completo.'));
    const y0 = 2001, a = fromYMD(y0, st.start[1], st.start[0]);
    let b = fromYMD(y0, st.end[1], st.end[0]);
    if (b < a) b = fromYMD(y0 + 1, st.end[1], st.end[0]);                 // window across the new year
    const offsets = [];
    for (let o = 0; o <= b - a; o += Math.max(1, st.step)) offsets.push(o);
    const cultivar = ctx.cultivar();
    const seasons = ctx.years.flatMap((y) => offsets.map((o) => ({ ...ctx.season(y, { cultivar }), sowing: fromYMD(y, st.start[1], st.start[0]) + o, offset: o })));
    const rows = await ctx.run(seasons);
    return { rows, offsets, st, first: a };
  },

  render(ctx, { rows, offsets, st, first }, el) {
    const { emu } = ctx, meta = ctx.emu.meta, V = ctx.variable, mv = meta[V], k = emu.keys;
    const label = (o) => shortDate(first + o);
    const cells = rows.map((r) => ({ year: r.year, offset: r.offset, date: label(r.offset), v: r.outputs[V] * mv.scale, mat: r.outputs[k.maturity], ood: r.outOfDomain.length > 0 }));
    const finite = cells.filter((c) => Number.isFinite(c.v));
    const pctThr = quantile(finite.map((c) => c.v), st.pct / 100);
    const thr = Number.isFinite(st.thr) ? st.thr : pctThr;
    const byDate = offsets.map((o) => {
      const vs = cells.filter((c) => c.offset === o && Number.isFinite(c.v));
      const v = vs.map((c) => c.v);
      return { offset: o, date: label(o), n: v.length, p10: quantile(v, 0.1), p25: quantile(v, 0.25), p50: quantile(v, 0.5), p75: quantile(v, 0.75), p90: quantile(v, 0.9),
        risk: v.length ? v.filter((x) => x < thr).length / v.length : NaN, mat: quantile(vs.map((c) => c.mat), 0.5), ood: cells.filter((c) => c.offset === o && c.ood).length };
    });
    const best = byDate.reduce((a, b) => (b.p50 > a.p50 ? b : a), byDate[0]);

    const s = ctx.tabState(`janela${Math.sign(ctx.site.lat)}`);
    const set = (patch) => { Object.assign(s, patch); ctx.refresh(); };
    const controls = [
      dayMonth(t('From', 'De'), st.start, (v) => set({ start: v })), dayMonth(t('to', 'até'), st.end, (v) => set({ end: v })),
      h('label.inline', h('span', t('every', 'a cada')), h('input', { type: 'number', min: 1, max: 15, value: st.step, style: { width: '4em' }, onchange: (e) => set({ step: Math.max(1, +e.target.value || 4) }) }), h('span', t('days', 'dias'))),
      variableSelect(ctx),
    ];
    const water = ctx.s.irrigated ? t('no water stress', 'sem estresse hídrico') : t('rainfed', 'sequeiro');
    el.append(header(t(`Sowing window: ${rows.length} seasons`, `Janela de semeadura: ${rows.length} safras`),
      t(`${offsets.length} dates from ${label(0)} to ${label(offsets.at(-1))} in ${ctx.years.length} years (${ctx.years[0]}–${ctx.years.at(-1)}), ${water}, the same cultivar on every date.`,
        `${offsets.length} datas de ${label(0)} a ${label(offsets.at(-1))} em ${ctx.years.length} anos (${ctx.years[0]}–${ctx.years.at(-1)}), ${water}, mesmo cultivar em todas as datas.`),
      controls, exporter(`${t('sowing_window', 'janela')}_${emu.card.name}.csv`, rows.map((r) => ({ [t('year', 'ano')]: r.year, [t('sowing', 'semeadura')]: ctx.isoDate(r.sowing),
        ...Object.fromEntries(Object.keys(meta).map((n) => [n, r.outputs[n] * meta[n].scale])), [t('out_of_domain', 'fora_do_dominio')]: r.outOfDomain.join(' ') })))));
    const note = levelNote(ctx, V); if (note) el.append(note);

    const tile = (l, v, sub) => h('div.tile', h('span.t-label', l), h('span.t-value', v), sub ? h('span.t-sub', sub) : null);
    const safest = byDate.reduce((a, b) => (b.risk < a.risk ? b : a), byDate[0]);
    el.append(h('div.tiles',
      tile(t('Best median', 'Melhor mediana'), best.date, `${auto(best.p50)} ${mv.unit} (10–90 %: ${auto(best.p10)}–${auto(best.p90)})`),
      tile(t('Lowest risk', 'Menor risco'), safest.date, t(`${fmt(100 * safest.risk, 0)} % of the years below ${auto(thr)} ${mv.unit}`, `${fmt(100 * safest.risk, 0)} % dos anos abaixo de ${auto(thr)} ${mv.unit}`)),
      tile(t('Maturity at the best date', 'Maturidade na melhor data'), `${fmt(best.mat, 0)} ${t('days', 'dias')}`, `${t('around', 'por volta de')} ${shortDate(first + best.offset + Math.round(best.mat))}`)));

    const f1 = figure(t(`${mv.label} by year and sowing date`, `${mv.label} por ano e data de semeadura`), t('Each cell is one season. Dots: inputs outside the training domain.', 'Cada célula é uma safra. Pontos: entradas fora do domínio de treino.'), { wide: true });
    const f2 = figure(t('Median and bands across the years', 'Mediana e faixas entre os anos'), t('Bands: 25–75 % and 10–90 % of the years. Dashed line: best median.', 'Faixas: 25–75 % e 10–90 % dos anos. Linha tracejada: melhor mediana.'), { wide: true, legend: [[t('Median', 'Mediana'), C.blue], ['25–75 %', C.blue, 'band'], ['10–90 %', C.blue, 'band light']] });
    const f3 = figure(t(`Risk: years with ${mv.label.toLowerCase()} below ${auto(thr)} ${mv.unit}`, `Risco: anos com ${mv.label.toLowerCase()} abaixo de ${auto(thr)} ${mv.unit}`), null);
    const f4 = figure(t('Cycle length', 'Duração do ciclo'), t('Median days from sowing to maturity.', 'Mediana dos dias da semeadura à maturidade.'));
    el.append(grid(f1.card, f2.card, f3.card, f4.card));

    const thrInput = h('span.inline-controls',
      h('label.inline', h('span', t('threshold: percentile', 'limiar: percentil')), h('input', { type: 'number', min: 5, max: 50, step: 5, value: st.pct, style: { width: '4.2em' }, onchange: (e) => { s.pct = +e.target.value || 20; s.thr = NaN; ctx.redraw(); } })),
      h('label.inline', h('span', t('or value', 'ou valor')), h('input', { type: 'number', step: 'any', value: Number.isFinite(st.thr) ? st.thr : '', placeholder: auto(pctThr), style: { width: '5.5em' }, onchange: (e) => { s.thr = e.target.value === '' ? NaN : +e.target.value; ctx.redraw(); } })));
    f3.card.querySelector('figcaption').append(thrInput);

    const dates = offsets.map(label), every = Math.max(1, Math.ceil(offsets.length / 12));
    const xTicks = dates.filter((_, i) => i % every === 0);
    draw(f1.body, { height: Math.max(260, Math.min(560, ctx.years.length * 13 + 60)), marginLeft: 44, padding: 0,
      x: { label: null, domain: dates, ticks: xTicks, tickRotate: -35 }, y: { label: null, tickFormat: 'd', reverse: true, grid: false, type: 'band' },
      color: { scheme: /dap$/.test(V) ? 'purples' : 'greens', legend: true, label: `${mv.label} (${mv.unit})`, width: 320 },
      marks: [
        Plot.cell(cells, { x: 'date', y: 'year', fill: 'v', inset: 0.4, tip: true, title: (c) => `${c.year}, ${t('sown', 'semeadura')} ${c.date}\n${auto(c.v)} ${mv.unit}${c.ood ? `\n${t('outside the training domain', 'fora do domínio de treino')}` : ''}` }),
        Plot.dot(cells.filter((c) => c.ood), { x: 'date', y: 'year', r: 1.6, fill: C.red }),
      ] });
    const xi = (d) => d.offset;
    const tickFmt = (o) => label(o);
    draw(f2.body, { height: 280, x: { label: null, tickFormat: tickFmt, ticks: xTicks.map((_, i) => offsets[i * every]) }, y: { label: mv.unit }, marks: [
      Plot.areaY(byDate, { x: xi, y1: 'p10', y2: 'p90', fill: C.blue, fillOpacity: 0.12 }),
      Plot.areaY(byDate, { x: xi, y1: 'p25', y2: 'p75', fill: C.blue, fillOpacity: 0.25 }),
      Plot.lineY(byDate, { x: xi, y: 'p50', stroke: C.blue, strokeWidth: 2 }),
      Plot.ruleX([best], { x: xi, stroke: C.red, strokeDasharray: '4,3' }),
      Plot.text([best], { x: xi, y: 'p50', text: (d) => `${t('best median', 'melhor mediana')}: ${d.date}`, dy: -12, dx: 6, textAnchor: 'start', fill: 'currentColor', fontWeight: 600 }),
      Plot.tip(byDate, Plot.pointerX({ x: xi, y: 'p50', title: (d) => `${d.date}\n${t('median', 'mediana')} ${auto(d.p50)} ${mv.unit}\n25–75 %: ${auto(d.p25)}–${auto(d.p75)}\n10–90 %: ${auto(d.p10)}–${auto(d.p90)}` })),
    ] });
    draw(f3.body, { x: { label: null, domain: dates, ticks: xTicks, tickRotate: -35 }, y: { label: t('% of the years', '% dos anos'), domain: [0, 100] }, marks: [
      Plot.barY(byDate, { x: 'date', y: (d) => 100 * d.risk, fill: C.red, insetLeft: 1, insetRight: 1, rx: 2, tip: true, title: (d) => `${d.date}\n${fmt(100 * d.risk, 0)} % ${t('of the years below', 'dos anos abaixo de')} ${auto(thr)} ${mv.unit}` }),
      Plot.ruleY([0]),
    ] });
    draw(f4.body, { x: { label: null, tickFormat: tickFmt, ticks: xTicks.map((_, i) => offsets[i * every]) }, y: { label: t('days', 'dias'), zero: false }, marks: [
      Plot.lineY(byDate, { x: xi, y: 'mat', stroke: C.violet, strokeWidth: 2 }),
      Plot.tip(byDate, Plot.pointerX({ x: xi, y: 'mat', title: (d) => `${d.date}\n${t('maturity', 'maturidade')}: ${fmt(d.mat, 0)} ${t('days (median)', 'dias (mediana)')}` })),
    ] });

    el.append(h('details.card', h('summary', h('h2', t('Table by sowing date', 'Tabela por data de semeadura'))), table(byDate, [
      [t('Date', 'Data'), 'date'], [t('Seasons', 'Safras'), 'n', 'num'], ['10 %', (r) => auto(r.p10), 'num'], [t('Median', 'Mediana'), (r) => auto(r.p50), 'num'], ['90 %', (r) => auto(r.p90), 'num'],
      [t('Risk', 'Risco'), (r) => `${fmt(100 * r.risk, 0)} %`, 'num'], [t('Maturity (d)', 'Maturidade (d)'), (r) => fmt(r.mat, 0), 'num'], [t('Out of domain', 'Fora do domínio'), 'ood', 'num'],
    ]), domainSummary(rows)));
  },
};
