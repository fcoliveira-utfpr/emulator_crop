// Many years at a fixed sowing day: year-to-year variability, rainfed vs. no water stress.

import { C, draw, figure, Plot } from '../charts.js';
import { domainSummary, exporter, grid, header, levelNote, table, variableSelect } from '../common.js';
import { auto, corr, fmt, h, mean, quantile, sd } from '../dom.js';
import { isoDate } from '../../engine/dates.js';
import { download, toCsv } from '../../engine/io.js';
import { etoDay } from '../../engine/weather.js';

export const stats = (values) => ({ n: values.filter(Number.isFinite).length, mean: mean(values), sd: sd(values), cv: 100 * sd(values) / Math.abs(mean(values)),
  min: Math.min(...values.filter(Number.isFinite)), p10: quantile(values, 0.1), p50: quantile(values, 0.5), p90: quantile(values, 0.9), max: Math.max(...values.filter(Number.isFinite)) });

export const yearsTab = {
  id: 'anos', label: 'Série de anos', needsSite: true,
  async compute(ctx) {
    if (!ctx.years.length) throw new Error('Nenhum ano do período escolhido tem clima completo para esta data de semeadura.');
    const seasons = ctx.years.map((y) => ctx.season(y, { irrigated: false }));
    const rows = await ctx.run([...seasons, ...seasons.map((s) => ({ ...s, irrigated: true }))]);
    return { rainfed: rows.slice(0, seasons.length), potential: rows.slice(seasons.length) };
  },

  render(ctx, { rainfed, potential }, el) {
    const { emu, s } = ctx, k = emu.keys, meta = emu.meta, V = ctx.variable, mv = meta[V];
    const val = (r, name) => r.outputs[name] * meta[name].scale;
    const data = rainfed.map((r, i) => ({
      year: r.year, sowing: ctx.isoDate(r.sowing), v: val(r, V), vi: val(potential[i], V),
      yield: val(r, k.yield), yieldI: val(potential[i], k.yield), flo: r.outputs[k.flowering], mat: r.outputs[k.maturity],
      rain: val(r, k.rain), et: val(r, k.et), ood: r.outOfDomain.length > 0, rare: r.rare.length > 0, flags: r.outOfDomain.join(' '),
    })).filter((d) => Number.isFinite(d.v));
    const yearLabel = `${s.day}/${String(s.month).padStart(2, '0')}`;
    const exportRows = rainfed.map((r, i) => ({ ano: r.year, semeadura: ctx.isoDate(r.sowing),
      ...Object.fromEntries(Object.keys(meta).flatMap((n) => [[`${n}_sequeiro`, val(r, n)], [`${n}_sem_estresse`, val(potential[i], n)]])),
      fora_do_dominio: r.outOfDomain.join(' '), entradas_raras: r.rare.join(' ') }));

    el.append(header(`${data.length} safras semeadas em ${yearLabel}, ${ctx.years[0]}–${ctx.years.at(-1)}`,
      'Mesma data de semeadura em todos os anos: a variação vem só do clima de cada ano. Sequeiro e sem estresse hídrico (o balanço de água desligado, como no treino).',
      [variableSelect(ctx), h('button.secondary', { type: 'button', onclick: () => download(`clima_ciclos_${yearLabel.replace('/', '-')}.csv`, toCsv(cycleWeatherRows(ctx, rainfed))) }, 'Baixar clima dos ciclos (CSV)')], exporter(`serie_${yearLabel.replace('/', '-')}_${emu.card.name}.csv`, exportRows)));
    if (!data.length) { el.append(h('div.empty', h('p', 'Sem safras calculadas.'))); return; }
    const note = levelNote(ctx, V); if (note) el.append(note);

    const st = stats(data.map((d) => d.v)), sti = stats(data.map((d) => d.vi));
    const gap = data.map((d) => Math.max(d.vi - d.v, 0));
    const tile = (label, value, sub) => h('div.tile', h('span.t-label', label), h('span.t-value', value), sub ? h('span.t-sub', sub) : null);
    el.append(h('div.tiles',
      tile(`Média, sequeiro`, `${auto(st.mean)} ${mv.unit}`, `mediana ${auto(st.p50)}`),
      tile('Variabilidade entre anos', `CV ${fmt(st.cv, 0)} %`, `desvio ${auto(st.sd)} ${mv.unit}`),
      tile('Anos ruins / bons', `${auto(st.p10)} / ${auto(st.p90)}`, '10 % e 90 % dos anos'),
      tile('Sem estresse hídrico', `${auto(sti.mean)} ${mv.unit}`, `diferença média ${auto(mean(gap))} (${fmt(100 * mean(gap) / sti.mean, 0)} %)`)));

    const series = [['Sequeiro', C.blue], ['Sem estresse hídrico', C.gray, 'dash']];
    const f1 = figure(`${mv.label} por ano`, 'Área vermelha: diferença atribuída à falta de água. Anéis vermelhos: safras com entradas fora do domínio de treino.', { wide: true, legend: series });
    const f2 = figure('Chuva e evapotranspiração no ciclo', 'Sequeiro, da semeadura à maturidade.', { legend: [['Chuva', C.rain, 'bar'], ['Evapotranspiração', C.aqua]] });
    const f3 = figure('Fenologia', 'Dias após a semeadura.', { legend: [['Floração', C.yellow], ['Maturidade', C.violet]] });
    const f4 = figure(`${mv.label} × chuva no ciclo`, null);
    const f5 = figure(`${mv.label} × evapotranspiração`, null);
    const f6 = figure('Distribuição entre os anos', 'Probabilidade de um valor menor ou igual.', { legend: series });
    el.append(grid(f1.card, f2.card, f3.card, f4.card, f5.card, f6.card));

    const tipTitle = (d) => `${d.year} (semeadura ${d.sowing})\nsequeiro: ${auto(d.v)} ${mv.unit}\nsem estresse: ${auto(d.vi)} ${mv.unit}${d.ood ? `\nfora do domínio: ${d.flags}` : ''}`;
    draw(f1.body, { height: 300, x: { label: null, tickFormat: 'd' }, y: { label: mv.unit, zero: mv.unit.includes('/ha') }, marks: [
      Plot.areaY(data, { x: 'year', y1: 'v', y2: (d) => Math.max(d.v, d.vi), fill: C.red, fillOpacity: 0.12 }),
      Plot.lineY(data, { x: 'year', y: 'vi', stroke: C.gray, strokeWidth: 1.5, strokeDasharray: '5,4' }),
      Plot.lineY(data, { x: 'year', y: 'v', stroke: C.blue, strokeWidth: 2 }),
      Plot.dot(data, { x: 'year', y: 'v', r: 3.5, fill: C.blue, stroke: 'var(--surface)', strokeWidth: 1 }),
      Plot.dot(data.filter((d) => d.ood), { x: 'year', y: 'v', r: 7, stroke: C.red, strokeWidth: 1.5 }),
      Plot.tip(data, Plot.pointerX({ x: 'year', y: 'v', title: tipTitle })),
    ] });
    draw(f2.body, { x: { label: null, tickFormat: 'd' }, y: { label: 'mm' }, marks: [
      Plot.rectY(data, { x: 'year', y: 'rain', interval: 1, fill: C.rain, insetLeft: 1.5, insetRight: 1.5, rx: 2 }),
      Plot.lineY(data, { x: (d) => d.year + 0.5, y: 'et', stroke: C.aqua, strokeWidth: 2, marker: 'circle-stroke' }), Plot.ruleY([0]),
      Plot.tip(data, Plot.pointerX({ x: (d) => d.year + 0.5, y: 'rain', title: (d) => `${d.year}\nchuva ${fmt(d.rain, 0)} mm\nevapotranspiração ${fmt(d.et, 0)} mm` })),
    ] });
    draw(f3.body, { x: { label: null, tickFormat: 'd' }, y: { label: 'dias após a semeadura', zero: true }, marks: [
      Plot.lineY(data, { x: 'year', y: 'flo', stroke: C.yellow, strokeWidth: 2, marker: 'circle-stroke' }),
      Plot.lineY(data, { x: 'year', y: 'mat', stroke: C.violet, strokeWidth: 2, marker: 'circle-stroke' }),
      Plot.tip(data, Plot.pointerX({ x: 'year', y: 'mat', title: (d) => `${d.year}\nfloração ${fmt(d.flo, 0)} d\nmaturidade ${fmt(d.mat, 0)} d` })),
    ] });
    const scatter = (body, x, label) => draw(body, { x: { label }, y: { label: mv.unit }, color: { type: 'linear', scheme: 'blues', range: [0.3, 1], label: 'ano', legend: true, tickFormat: 'd' }, marks: [
      Plot.dot(data, { x, y: 'v', fill: 'year', r: 5, stroke: 'var(--surface)', strokeWidth: 1, tip: true, title: (d) => `${d.year}\n${label}: ${fmt(d[x], 0)}\n${mv.label}: ${auto(d.v)} ${mv.unit}` }),
      Plot.linearRegressionY(data, { x, y: 'v', stroke: C.gray, strokeOpacity: 0.7, ci: 0 }),
    ] });
    scatter(f4.body, 'rain', 'chuva no ciclo (mm)');
    scatter(f5.body, 'et', 'evapotranspiração (mm)');
    f4.card.querySelector('figcaption').append(h('p', `Correlação: ${fmt(corr(data.map((d) => d.rain), data.map((d) => d.v)), 2)}`));
    f5.card.querySelector('figcaption').append(h('p', `Correlação: ${fmt(corr(data.map((d) => d.et), data.map((d) => d.v)), 2)}`));
    const ecdf = (values, name) => values.filter(Number.isFinite).sort((a, b) => a - b).map((x, i, a) => ({ x, p: (i + 1) / a.length, name }));
    const cdf = [...ecdf(data.map((d) => d.v), 'Sequeiro'), ...ecdf(data.map((d) => d.vi), 'Sem estresse hídrico')];
    draw(f6.body, { x: { label: mv.unit }, y: { label: 'probabilidade acumulada', domain: [0, 1], tickFormat: '%' }, marks: [
      Plot.line(cdf, { x: 'x', y: 'p', z: 'name', curve: 'step-after', stroke: (d) => (d.name === 'Sequeiro' ? C.blue : C.gray), strokeWidth: 2, strokeDasharray: (d) => (d.name === 'Sequeiro' ? null : '5,4') }),
      Plot.tip(cdf, Plot.pointer({ x: 'x', y: 'p', title: (d) => `${d.name}\n${fmt(d.p * 100, 0)} % dos anos ≤ ${auto(d.x)} ${mv.unit}` })),
    ] });

    // summary of the main outputs
    const names = [...new Set([V, k.yield, k.biomass, k.flowering, k.maturity, k.rain, k.et, k.hi])];
    const statRows = names.flatMap((n) => [['sequeiro', rainfed], ['sem estresse', potential]].map(([w, rows]) => ({ name: n, w, ...stats(rows.map((r) => val(r, n))) })));
    el.append(h('section.card', h('h2', 'Resumo entre os anos'), table(statRows, [
      ['Saída', (r) => h('span', meta[r.name].label, ' ', h('small.muted', `(${meta[r.name].unit})`))], ['Água', 'w'],
      ['Média', (r) => auto(r.mean), 'num'], ['Desvio', (r) => auto(r.sd), 'num'], ['CV %', (r) => fmt(r.cv, 0), 'num'],
      ['Mín.', (r) => auto(r.min), 'num'], ['10 %', (r) => auto(r.p10), 'num'], ['Mediana', (r) => auto(r.p50), 'num'], ['90 %', (r) => auto(r.p90), 'num'], ['Máx.', (r) => auto(r.max), 'num'],
    ]), domainSummary(rainfed)));
  },
};

/** Daily weather of every cycle (30 days before sowing to maturity), scenario applied. */
function cycleWeatherRows(ctx, rows) {
  const ws = ctx.site.ws, { dt, rainFactor } = ctx.s, k = ctx.emu.keys, out = [];
  for (const r of rows) {
    if (!r.ok) continue;
    const mat = r.sowing + Math.round(r.outputs[k.maturity]);
    for (let d = r.sowing - 30; d <= mat; d++) {
      const i = ws.index(d);
      if (i < 0 || i >= ws.n) continue;
      const tmax = ws.tmax[i] + dt, tmin = ws.tmin[i] + dt;
      out.push({ safra: r.year, data: isoDate(d), das: d - r.sowing, tmax, tmin, srad: ws.srad[i], chuva: ws.rain[i] * rainFactor,
        eto: dt ? etoDay(tmax, tmin, ws.srad[i], ws.wind[i], ws.ea[i], ws.lat, ws.elev, ws.doy[i]) : ws.eto[i], dpv: ws.vpd[i], fotoperiodo: ws.dayl[i] });
    }
  }
  return out;
}
