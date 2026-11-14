// Many years at a fixed sowing day: year-to-year variability, rainfed vs. no water stress.

import { isoDate, monthName } from '../../engine/dates.js';
import { download, toCsv } from '../../engine/io.js';
import { etoDay } from '../../engine/weather.js';
import { t } from '../../i18n.js';
import { C, draw, figure, Plot } from '../charts.js';
import { domainSummary, exporter, grid, header, levelNote, table, variableSelect } from '../common.js';
import { auto, corr, fmt, h, mean, quantile, sd } from '../dom.js';

export const stats = (values) => ({ n: values.filter(Number.isFinite).length, mean: mean(values), sd: sd(values), cv: 100 * sd(values) / Math.abs(mean(values)),
  min: Math.min(...values.filter(Number.isFinite)), p10: quantile(values, 0.1), p50: quantile(values, 0.5), p90: quantile(values, 0.9), max: Math.max(...values.filter(Number.isFinite)) });

export const yearsTab = {
  id: 'anos', needsSite: true,
  get label() { return t('Many years', 'Série de anos'); },
  async compute(ctx) {
    if (!ctx.years.length) throw new Error(t('No year of the chosen period has complete weather for this sowing date.', 'Nenhum ano do período escolhido tem clima completo para esta data de semeadura.'));
    const seasons = ctx.years.map((y) => ctx.season(y, { irrigated: false }));
    const rows = await ctx.run([...seasons, ...seasons.map((s) => ({ ...s, irrigated: true }))]);
    return { rainfed: rows.slice(0, seasons.length), potential: rows.slice(seasons.length) };
  },

  render(ctx, { rainfed, potential }, el) {
    const { emu, s } = ctx, k = emu.keys, meta = emu.meta, V = ctx.variable, mv = meta[V];
    const val = (r, name) => r.outputs[name] * meta[name].scale;
    const RF = t('Rainfed', 'Sequeiro'), NS = t('No water stress', 'Sem estresse hídrico');
    const data = rainfed.map((r, i) => ({
      year: r.year, sowing: ctx.isoDate(r.sowing), v: val(r, V), vi: val(potential[i], V),
      flo: r.outputs[k.flowering], mat: r.outputs[k.maturity],
      rain: val(r, k.rain), et: val(r, k.et), ood: r.outOfDomain.length > 0, flags: r.outOfDomain.join(' '),
    })).filter((d) => Number.isFinite(d.v));
    const dayLabel = `${s.day} ${monthName(s.month)}`, fileTag = `${String(s.month).padStart(2, '0')}-${String(s.day).padStart(2, '0')}`;
    const exportRows = rainfed.map((r, i) => ({ [t('year', 'ano')]: r.year, [t('sowing', 'semeadura')]: ctx.isoDate(r.sowing),
      ...Object.fromEntries(Object.keys(meta).flatMap((n) => [[`${n}_${t('rainfed', 'sequeiro')}`, val(r, n)], [`${n}_${t('no_stress', 'sem_estresse')}`, val(potential[i], n)]])),
      [t('out_of_domain', 'fora_do_dominio')]: r.outOfDomain.join(' '), [t('rare_inputs', 'entradas_raras')]: r.rare.join(' ') }));

    el.append(header(t(`${data.length} seasons sown on ${dayLabel}, ${ctx.years[0]}–${ctx.years.at(-1)}`, `${data.length} safras semeadas em ${dayLabel}, ${ctx.years[0]}–${ctx.years.at(-1)}`),
      t('Same sowing date in every year: the variation comes only from the weather of each year. Rainfed and without water stress (the water balance switched off, as in training).',
        'Mesma data de semeadura em todos os anos: a variação vem só do clima de cada ano. Sequeiro e sem estresse hídrico (o balanço de água desligado, como no treino).'),
      [variableSelect(ctx), h('button.secondary', { type: 'button', onclick: () => download(`${t('cycle_weather', 'clima_ciclos')}_${fileTag}.csv`, toCsv(cycleWeatherRows(ctx, rainfed))) }, t('Download weather of the cycles (CSV)', 'Baixar clima dos ciclos (CSV)'))],
      exporter(`${t('years', 'serie')}_${fileTag}_${emu.card.name}.csv`, exportRows)));
    if (!data.length) { el.append(h('div.empty', h('p', t('No season computed.', 'Sem safras calculadas.')))); return; }
    const note = levelNote(ctx, V); if (note) el.append(note);

    const st = stats(data.map((d) => d.v)), sti = stats(data.map((d) => d.vi));
    const gap = data.map((d) => Math.max(d.vi - d.v, 0));
    const tile = (label, value, sub) => h('div.tile', h('span.t-label', label), h('span.t-value', value), sub ? h('span.t-sub', sub) : null);
    el.append(h('div.tiles',
      tile(t('Mean, rainfed', 'Média, sequeiro'), `${auto(st.mean)} ${mv.unit}`, `${t('median', 'mediana')} ${auto(st.p50)}`),
      tile(t('Year-to-year variability', 'Variabilidade entre anos'), `CV ${fmt(st.cv, 0)} %`, `${t('SD', 'desvio')} ${auto(st.sd)} ${mv.unit}`),
      tile(t('Poor / good years', 'Anos ruins / bons'), `${auto(st.p10)} / ${auto(st.p90)}`, t('10 % and 90 % of the years', '10 % e 90 % dos anos')),
      tile(NS, `${auto(sti.mean)} ${mv.unit}`, `${t('mean difference', 'diferença média')} ${auto(mean(gap))} (${fmt(100 * mean(gap) / sti.mean, 0)} %)`)));

    const series = [[RF, C.blue], [NS, C.gray, 'dash']];
    const f1 = figure(t(`${mv.label} by year`, `${mv.label} por ano`), t('Red area: difference attributed to the lack of water. Red rings: seasons with inputs outside the training domain.', 'Área vermelha: diferença atribuída à falta de água. Anéis vermelhos: safras com entradas fora do domínio de treino.'), { wide: true, legend: series });
    const f2 = figure(t('Rain and evapotranspiration in the cycle', 'Chuva e evapotranspiração no ciclo'), t('Rainfed, sowing to maturity.', 'Sequeiro, da semeadura à maturidade.'), { legend: [[t('Rain', 'Chuva'), C.rain, 'bar'], [t('Evapotranspiration', 'Evapotranspiração'), C.aqua]] });
    const f3 = figure(t('Phenology', 'Fenologia'), t('Days after sowing.', 'Dias após a semeadura.'), { legend: [[t('Flowering', 'Floração'), C.yellow], [t('Maturity', 'Maturidade'), C.violet]] });
    const f4 = figure(`${mv.label} × ${t('rain in the cycle', 'chuva no ciclo')}`, null);
    const f5 = figure(`${mv.label} × ${t('evapotranspiration', 'evapotranspiração')}`, null);
    const f6 = figure(t('Distribution across the years', 'Distribuição entre os anos'), t('Probability of a value lower or equal.', 'Probabilidade de um valor menor ou igual.'), { legend: series });
    el.append(grid(f1.card, f2.card, f3.card, f4.card, f5.card, f6.card));

    const tipTitle = (d) => `${d.year} (${t('sown', 'semeadura')} ${d.sowing})\n${RF}: ${auto(d.v)} ${mv.unit}\n${NS}: ${auto(d.vi)} ${mv.unit}${d.ood ? `\n${t('out of domain', 'fora do domínio')}: ${d.flags}` : ''}`;
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
      Plot.tip(data, Plot.pointerX({ x: (d) => d.year + 0.5, y: 'rain', title: (d) => `${d.year}\n${t('rain', 'chuva')} ${fmt(d.rain, 0)} mm\n${t('evapotranspiration', 'evapotranspiração')} ${fmt(d.et, 0)} mm` })),
    ] });
    draw(f3.body, { x: { label: null, tickFormat: 'd' }, y: { label: t('days after sowing', 'dias após a semeadura'), zero: true }, marks: [
      Plot.lineY(data, { x: 'year', y: 'flo', stroke: C.yellow, strokeWidth: 2, marker: 'circle-stroke' }),
      Plot.lineY(data, { x: 'year', y: 'mat', stroke: C.violet, strokeWidth: 2, marker: 'circle-stroke' }),
      Plot.tip(data, Plot.pointerX({ x: 'year', y: 'mat', title: (d) => `${d.year}\n${t('flowering', 'floração')} ${fmt(d.flo, 0)} d\n${t('maturity', 'maturidade')} ${fmt(d.mat, 0)} d` })),
    ] });
    const scatter = (body, x, label) => draw(body, { x: { label }, y: { label: mv.unit }, color: { type: 'linear', scheme: 'blues', range: [0.3, 1], label: t('year', 'ano'), legend: true, tickFormat: 'd' }, marks: [
      Plot.dot(data, { x, y: 'v', fill: 'year', r: 5, stroke: 'var(--surface)', strokeWidth: 1, tip: true, title: (d) => `${d.year}\n${label}: ${fmt(d[x], 0)}\n${mv.label}: ${auto(d.v)} ${mv.unit}` }),
      Plot.linearRegressionY(data, { x, y: 'v', stroke: C.gray, strokeOpacity: 0.7, ci: 0 }),
    ] });
    scatter(f4.body, 'rain', t('rain in the cycle (mm)', 'chuva no ciclo (mm)'));
    scatter(f5.body, 'et', t('evapotranspiration (mm)', 'evapotranspiração (mm)'));
    f4.card.querySelector('figcaption').append(h('p', `${t('Correlation', 'Correlação')}: ${fmt(corr(data.map((d) => d.rain), data.map((d) => d.v)), 2)}`));
    f5.card.querySelector('figcaption').append(h('p', `${t('Correlation', 'Correlação')}: ${fmt(corr(data.map((d) => d.et), data.map((d) => d.v)), 2)}`));
    const ecdf = (values, name) => values.filter(Number.isFinite).sort((a, b) => a - b).map((x, i, a) => ({ x, p: (i + 1) / a.length, name }));
    const cdf = [...ecdf(data.map((d) => d.v), RF), ...ecdf(data.map((d) => d.vi), NS)];
    draw(f6.body, { x: { label: mv.unit }, y: { label: t('cumulative probability', 'probabilidade acumulada'), domain: [0, 1], tickFormat: '%' }, marks: [
      Plot.line(cdf, { x: 'x', y: 'p', z: 'name', curve: 'step-after', stroke: (d) => (d.name === RF ? C.blue : C.gray), strokeWidth: 2, strokeDasharray: (d) => (d.name === RF ? null : '5,4') }),
      Plot.tip(cdf, Plot.pointer({ x: 'x', y: 'p', title: (d) => `${d.name}\n${fmt(d.p * 100, 0)} % ${t('of the years', 'dos anos')} ≤ ${auto(d.x)} ${mv.unit}` })),
    ] });

    // summary of the main outputs
    const names = [...new Set([V, k.yield, k.biomass, k.flowering, k.maturity, k.rain, k.et, k.hi])];
    const statRows = names.flatMap((n) => [[t('rainfed', 'sequeiro'), rainfed], [t('no stress', 'sem estresse'), potential]].map(([w, rows]) => ({ name: n, w, ...stats(rows.map((r) => val(r, n))) })));
    el.append(h('section.card', h('h2', t('Summary across the years', 'Resumo entre os anos')), table(statRows, [
      [t('Output', 'Saída'), (r) => h('span', meta[r.name].label, ' ', h('small.muted', `(${meta[r.name].unit})`))], [t('Water', 'Água'), 'w'],
      [t('Mean', 'Média'), (r) => auto(r.mean), 'num'], [t('SD', 'Desvio'), (r) => auto(r.sd), 'num'], ['CV %', (r) => fmt(r.cv, 0), 'num'],
      ['Min.', (r) => auto(r.min), 'num'], ['10 %', (r) => auto(r.p10), 'num'], [t('Median', 'Mediana'), (r) => auto(r.p50), 'num'], ['90 %', (r) => auto(r.p90), 'num'], ['Max.', (r) => auto(r.max), 'num'],
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
      out.push({ [t('season', 'safra')]: r.year, [t('date', 'data')]: isoDate(d), das: d - r.sowing, tmax, tmin, srad: ws.srad[i], [t('rain', 'chuva')]: ws.rain[i] * rainFactor,
        eto: dt ? etoDay(tmax, tmin, ws.srad[i], ws.wind[i], ws.ea[i], ws.lat, ws.elev, ws.doy[i]) : ws.eto[i], [t('vpd', 'dpv')]: ws.vpd[i], [t('daylength', 'fotoperiodo')]: ws.dayl[i] });
    }
  }
  return out;
}
