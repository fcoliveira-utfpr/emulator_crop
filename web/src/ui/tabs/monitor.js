// Crop monitoring: the season in progress, with the weather observed so far and the forecast
// (Open-Meteo), the rest of the cycle completed by each past year; the expected yield and the
// yield gap followed week by week from sowing.

import { dayNumber, fromYMD, fullDate, isoDate, shortDate, today } from '../../engine/dates.js';
import { analogYears, lastContinuous, monitor, scenarioDays, summary } from '../../engine/monitor.js';
import { fetchOpenMeteo, fetchSeasonal, PAST_DAYS } from '../../engine/openmeteo.js';
import { combine, fillGaps, SRC } from '../../engine/weather.js';
import { t } from '../../i18n.js';
import { C, draw, figure, Plot } from '../charts.js';
import { domainSummary, exporter, grid, header, table as dataTable } from '../common.js';
import { auto, fmt, h, mean } from '../dom.js';

const asDate = (day) => new Date(day * 864e5);

/** Most recent sowing on the sidebar day and month that is not in the future. */
function defaultSowing(s) {
  const now = today(), y = new Date(now * 864e5).getUTCFullYear();
  const d = fromYMD(y, s.month, s.day);
  return d <= now ? d : fromYMD(y - 1, s.month, s.day);
}

/** Site weather (spreadsheet / NASA POWER) extended with Open-Meteo, once per site and day. */
const extended = new Map();
async function siteWeather(site, sowing) {
  const key = `${site.lat},${site.lon},${today()},${sowing}`;
  if (!extended.has(key)) {
    extended.set(key, (async () => {
      let om = null, error = null;
      if (Number.isFinite(site.lon)) {
        const powerEnd = lastContinuous(site.table, sowing - 30);
        try { om = await fetchOpenMeteo(site.lat, site.lon, powerEnd < today() - PAST_DAYS ? Math.max(powerEnd + 1, sowing - 30) : null); } catch (e) { error = e.message; }
      }
      const { table } = combine(site.table, om?.table ?? null);
      const copy = { ...table, cols: Object.fromEntries(Object.entries(table.cols).map(([c, x]) => [c, Float64Array.from(x)])), src: Object.fromEntries(Object.entries(table.src).map(([c, x]) => [c, Uint8Array.from(x)])) };
      fillGaps(copy);
      return { table: copy, openMeteo: !!om, error };
    })().catch((e) => { extended.delete(key); throw e; }));
  }
  return extended.get(key);
}

export const monitorTab = {
  id: 'monitor', needsSite: true,
  get label() { return t('Crop monitoring', 'Monitoramento da cultura'); },

  async compute(ctx) {
    const { emu, site, s } = ctx, st = ctx.tabState('monitor', { sowing: null });
    const sowing = st.sowing ?? defaultSowing(s), now = today();
    if (sowing > now) throw new Error(t('The sowing date is in the future: monitoring follows a season already sown.', 'A data de semeadura está no futuro: o monitoramento acompanha uma safra já semeada.'));
    const { table, openMeteo, error } = await siteWeather(site, sowing);
    const known = lastContinuous(table, sowing - 30);
    if (known < sowing) throw new Error(t(`The weather does not reach the sowing date (${fullDate(sowing)}); it ends on ${fullDate(known)}.`, `O clima não chega à data de semeadura (${fullDate(sowing)}); termina em ${fullDate(known)}.`));
    const observedEnd = Math.min(known, now - 1);
    const period = ctx.covered.filter((y) => y >= s.yearFrom && y <= s.yearTo);
    let analogs = analogYears(table, sowing, emu.card, period);
    if (analogs.length < 10) analogs = analogYears(table, sowing, emu.card);
    if (analogs.length < 5) throw new Error(t('Fewer than 5 past years with complete weather to complete the season.', 'Menos de 5 anos passados com clima completo para completar a safra.'));
    const n = scenarioDays(emu.card);
    let seasonal = null, seasonalError = null;
    if (Number.isFinite(site.lon) && known < sowing + n) {
      try { seasonal = await fetchSeasonal(site.lat, site.lon); } catch (e) { seasonalError = e.message; }
    }
    const cps = await monitor(emu, table, { lat: site.lat, elev: site.elev, soil: ctx.soil, sowing, cultivar: ctx.cultivar(), observedEnd, known, analogs, seasonal });
    return { sowing, now, known, observedEnd, table, analogs, cps, n, openMeteo, error, seasonal, seasonalError };
  },

  render(ctx, data, el) {
    const { emu } = ctx, k = emu.keys, meta = emu.meta, my = meta[k.yield], st = ctx.tabState('monitor', { sowing: null });
    const { sowing, now, known, observedEnd, table, analogs, cps, n, openMeteo, error, seasonal, seasonalError } = data;
    const val = (r) => r.outputs[k.yield] * my.scale;
    const RF = t('Rainfed', 'Sequeiro'), NS = t('No water stress', 'Sem estresse hídrico');
    const all = cps.map((cp) => {
      const rf = cp.rainfed.map(val), pt = cp.potential.map(val);
      const gaps = rf.map((v, i) => Math.max(pt[i] - v, 0));
      return { ...cp, date: asDate(cp.day), rf: summary(rf), pt: summary(pt), gap: summary(gaps).p50, gapPct: 100 * summary(gaps).p50 / summary(pt).p50 };
    });
    const traj = all.filter((d) => !d.seasonal), seas = all.find((d) => d.seasonal) ?? null;
    const first = traj[0], last = traj.at(-1);
    const useSeasonal = !!seas && (st.mode ?? 'seasonal') === 'seasonal', cur = useSeasonal ? seas : last;
    const SEAS = t('Past years adjusted by the ECMWF seasonal forecast', 'Anos passados ajustados pela previsão sazonal do ECMWF');
    const finished = known >= sowing + n || observedEnd >= sowing + Math.round(mean(last.rainfed.map((r) => r.outputs[k.maturity])));
    const flo = mean(cur.rainfed.map((r) => r.outputs[k.flowering])), mat = mean(cur.rainfed.map((r) => r.outputs[k.maturity]));
    const das = observedEnd - sowing;
    const stage = das < 0 ? t('before sowing', 'antes da semeadura') : das < flo ? t(`vegetative · flowering in ~${fmt(flo - das, 0)} days`, `vegetativo · floração em ~${fmt(flo - das, 0)} dias`)
      : das < mat ? t(`reproductive · maturity in ~${fmt(mat - das, 0)} days`, `reprodutivo · maturidade em ~${fmt(mat - das, 0)} dias`) : t('at or past maturity', 'maturidade atingida');
    const forecastEnd = known > observedEnd ? known : null;

    // header and controls
    const input = h('input', { type: 'date', value: isoDate(sowing), max: isoDate(now), onchange: (e) => { st.sowing = e.target.value ? dayNumber(e.target.value) : null; ctx.refresh(); } });
    const reset = st.sowing != null ? h('button.secondary', { type: 'button', onclick: () => { st.sowing = null; ctx.refresh(); } }, t('Use the sidebar date', 'Usar a data do painel')) : null;
    const exportRows = all.map((d) => ({ [t('date', 'data')]: isoDate(d.day), [t('weather_known_until', 'clima_conhecido_ate')]: isoDate(d.known), [t('forecast', 'previsao')]: d.forecast ? 1 : 0,
      [`${t('rainfed', 'sequeiro')}_p10`]: d.rf.p10, [`${t('rainfed', 'sequeiro')}_p50`]: d.rf.p50, [`${t('rainfed', 'sequeiro')}_p90`]: d.rf.p90,
      [`${t('no_stress', 'sem_estresse')}_p50`]: d.pt.p50, [t('yield_gap', 'yield_gap')]: d.gap, [t('yield_gap_pct', 'yield_gap_pct')]: d.gapPct,
      [t('rest_of_cycle', 'resto_do_ciclo')]: d.seasonal ? t('past years + ECMWF seasonal', 'anos passados + sazonal ECMWF') : t('past years', 'anos passados'), [t('unit', 'unidade')]: my.unit }));
    const modeSelect = seas ? h('label.inline', h('span', t('Rest of the cycle', 'Resto do ciclo')), h('select', { onchange: (e) => { st.mode = e.target.value; ctx.redraw(); } },
      h('option', { value: 'seasonal', selected: useSeasonal }, t('Seasonal forecast (ECMWF)', 'Previsão sazonal (ECMWF)')),
      h('option', { value: 'past', selected: !useSeasonal }, t('Past years only', 'Só anos passados')))) : null;
    el.append(header(t(`Season sown on ${fullDate(sowing)}`, `Safra semeada em ${fullDate(sowing)}`),
      t(`Weather observed until ${fullDate(observedEnd)}${forecastEnd ? `, forecast until ${fullDate(forecastEnd)}` : ''}; the rest of the cycle comes from each of ${analogs.length} past years (${analogs[0].year}–${analogs.at(-1).year})${useSeasonal ? ', shifted month by month to the ECMWF seasonal forecast' : ''}. Soil and cultivar stay fixed; only the weather changes between scenarios.`,
        `Clima observado até ${fullDate(observedEnd)}${forecastEnd ? `, previsão até ${fullDate(forecastEnd)}` : ''}; o resto do ciclo vem de cada um de ${analogs.length} anos passados (${analogs[0].year}–${analogs.at(-1).year})${useSeasonal ? ', deslocados mês a mês para a previsão sazonal do ECMWF' : ''}. Solo e cultivar ficam fixos; só o clima muda entre os cenários.`),
      [h('label.inline', h('span', t('Sowing', 'Semeadura')), input), reset, modeSelect],
      exporter(`${t('monitoring', 'monitoramento')}_${isoDate(sowing)}_${emu.card.name}.csv`, exportRows)));
    if (seasonalError) el.append(h('p.note.warn', t(`Seasonal forecast unavailable (${seasonalError}): the rest of the cycle uses the past years only.`, `Previsão sazonal indisponível (${seasonalError}): o resto do ciclo usa só os anos passados.`)));
    if (error) el.append(h('p.note.warn', t(`Open-Meteo unavailable (${error}): monitoring with the NASA POWER days only.`, `Open-Meteo indisponível (${error}): monitoramento só com os dias da NASA POWER.`)));

    // headline numbers
    const yu = my.unit, change = cur.rf.p50 - first.rf.p50;
    const tile = (label, value, unit, sub, cls = '') => h(`div.tile${cls}`, h('span.t-label', label), h('span.t-value', value, unit ? h('small', ` ${unit}`) : null), sub ? h('span.t-sub', sub) : null);
    el.append(h('div.tiles',
      tile(finished ? t('Simulated yield of the season', 'Produtividade simulada da safra') : t('Expected yield (median of the scenarios)', 'Produtividade esperada (mediana dos cenários)'), fmt(cur.rf.p50, 2), yu,
        finished ? RF : `${t(`80 % of the scenarios between ${fmt(cur.rf.p10, 2)} and ${fmt(cur.rf.p90, 2)}`, `80 % dos cenários entre ${fmt(cur.rf.p10, 2)} e ${fmt(cur.rf.p90, 2)}`)}${seas ? ` · ${useSeasonal ? t('with the seasonal forecast', 'com a previsão sazonal') : t(`past years only (seasonal: ${fmt(seas.rf.p50, 2)})`, `só anos passados (sazonal: ${fmt(seas.rf.p50, 2)})`)}` : ''}`, '.hero'),
      tile(t('Change since sowing', 'Variação desde a semeadura'), `${change >= 0 ? '+' : '−'}${fmt(Math.abs(change), 2)}`, yu,
        t(`${change >= 0 ? '+' : '−'}${fmt(Math.abs(100 * change / first.rf.p50), 0)} % on the ${fmt(first.rf.p50, 2)} expected at sowing`, `${change >= 0 ? '+' : '−'}${fmt(Math.abs(100 * change / first.rf.p50), 0)} % sobre os ${fmt(first.rf.p50, 2)} esperados na semeadura`)),
      tile(t('Yield gap (water)', 'Yield gap (água)'), fmt(cur.gap, 2), yu, t(`${fmt(cur.gapPct, 0)} % of ${fmt(cur.pt.p50, 2)} without water stress`, `${fmt(cur.gapPct, 0)} % de ${fmt(cur.pt.p50, 2)} sem estresse hídrico`)),
      tile(t('Crop stage', 'Fase da cultura'), `${fmt(das, 0)}`, t('days after sowing', 'dias após a semeadura'), stage),
    ));

    // 1. expected yield along the season
    const obs = traj.filter((d) => !d.forecast), fc = traj.filter((d, i) => d.forecast || (traj[i + 1]?.forecast));
    const f1 = figure(t('Expected yield along the season', 'Produtividade esperada ao longo da safra'),
      t('Each point re-runs the season with the weather known on that date and each past year for the rest. The band holds 80 % of the scenarios and narrows as the season advances; the red area is the yield gap (no water stress − rainfed). Dashed: with the forecast.',
        'Cada ponto refaz a safra com o clima conhecido naquela data e cada ano passado para o resto. A faixa contém 80 % dos cenários e estreita conforme a safra avança; a área vermelha é o yield gap (sem estresse hídrico − sequeiro). Tracejado: com a previsão.'),
      { wide: true, legend: [[`${RF} (${t('median', 'mediana')})`, C.blue], [t('80 % of the scenarios', '80 % dos cenários'), C.blue, 'band'], [NS, C.gray, 'dash'], [t('Yield gap', 'Yield gap'), C.red, 'band'], ...(seas ? [[t('With the seasonal forecast (80 % range)', 'Com a previsão sazonal (faixa de 80 %)'), C.violet, 'dot']] : [])] });
    const f2 = figure(t('Yield gap along the season', 'Yield gap ao longo da safra'), t('Median over the scenarios of the yield lost to the lack of water.', 'Mediana, entre os cenários, da produtividade perdida por falta de água.'),
      { legend: [[t('Yield gap', 'Yield gap'), C.red, 'band']] });
    const f3 = figure(t('Final yield in each scenario', 'Produtividade final em cada cenário'),
      t(`With the weather known until ${fullDate(cur.known)}; each point takes the rest of the cycle from one past year${useSeasonal ? ', adjusted by the seasonal forecast' : ''}.`, `Com o clima conhecido até ${fullDate(cur.known)}; cada ponto toma o resto do ciclo de um ano passado${useSeasonal ? ', ajustado pela previsão sazonal' : ''}.`),
      { legend: [[RF, C.blue, 'dot'], [NS, C.gray, 'dot']] });
    el.append(grid(f1.card, f2.card, f3.card));
    const cycleX = { label: null, domain: [asDate(sowing), asDate(sowing + Math.max(Math.round(mat) + 7, traj.at(-1).day - sowing))], ticks: 6 };
    const todayRule = [Plot.ruleX([asDate(Math.min(now, sowing + n))], { stroke: 'currentColor', strokeOpacity: 0.35, strokeDasharray: '2,3' })];
    const tipText = (d) => `${fullDate(d.day)}${d.forecast ? ` (${t('with forecast', 'com previsão')})` : ''}\n${RF}: ${fmt(d.rf.p50, 2)} ${yu} (${fmt(d.rf.p10, 2)}–${fmt(d.rf.p90, 2)})\n${NS}: ${fmt(d.pt.p50, 2)}\n${t('yield gap', 'yield gap')}: ${fmt(d.gap, 2)} (${fmt(d.gapPct, 0)} %)`;
    draw(f1.body, { height: 320, marginTop: 18, x: cycleX, y: { label: yu, zero: true }, marks: [
      Plot.areaY(traj, { x: 'date', y1: (d) => d.rf.p10, y2: (d) => d.rf.p90, fill: C.blue, fillOpacity: 0.13 }),
      Plot.areaY(traj, { x: 'date', y1: (d) => d.rf.p50, y2: (d) => Math.max(d.rf.p50, d.pt.p50), fill: C.red, fillOpacity: 0.14 }),
      Plot.ruleY([first.rf.p50], { stroke: C.blue, strokeOpacity: 0.4, strokeDasharray: '1,3' }),
      Plot.text([first], { x: 'date', y: (d) => d.rf.p50, text: () => t('expected at sowing', 'esperado na semeadura'), dy: -8, textAnchor: 'start', fill: 'currentColor', fillOpacity: 0.6, fontSize: 10.5 }),
      Plot.lineY(traj, { x: 'date', y: (d) => d.pt.p50, stroke: C.gray, strokeWidth: 1.5, strokeDasharray: '5,4' }),
      Plot.lineY(obs, { x: 'date', y: (d) => d.rf.p50, stroke: C.blue, strokeWidth: 2 }),
      Plot.lineY(fc, { x: 'date', y: (d) => d.rf.p50, stroke: C.blue, strokeWidth: 2, strokeDasharray: '4,3' }),
      Plot.dot(obs, { x: 'date', y: (d) => d.rf.p50, r: 3.5, fill: C.blue, stroke: 'var(--surface)', strokeWidth: 1 }),
      Plot.dot(traj.filter((d) => d.forecast), { x: 'date', y: (d) => d.rf.p50, r: 4.5, fill: 'var(--surface)', stroke: C.blue, strokeWidth: 2 }),
      ...(seas ? [Plot.ruleX([seas], { x: (d) => asDate(d.day + 2), y1: (d) => d.rf.p10, y2: (d) => d.rf.p90, stroke: C.violet, strokeWidth: 2 }),
        Plot.dot([seas], { x: (d) => asDate(d.day + 2), y: (d) => d.rf.p50, symbol: 'diamond', r: 6, fill: C.violet, stroke: 'var(--surface)', strokeWidth: 1, tip: true,
          title: (d) => `${t('With the ECMWF seasonal forecast', 'Com a previsão sazonal do ECMWF')}\n${RF}: ${fmt(d.rf.p50, 2)} ${yu} (${fmt(d.rf.p10, 2)}–${fmt(d.rf.p90, 2)})\n${NS}: ${fmt(d.pt.p50, 2)}\n${t('yield gap', 'yield gap')}: ${fmt(d.gap, 2)}` })] : []),
      ...todayRule,
      Plot.tip(traj, Plot.pointerX({ x: 'date', y: (d) => d.rf.p50, title: tipText })),
    ] });
    draw(f2.body, { marginTop: 18, x: cycleX, y: { label: yu, zero: true }, marks: [
      Plot.areaY(traj, { x: 'date', y: 'gap', fill: C.red, fillOpacity: 0.18, curve: 'step-after' }),
      Plot.lineY(traj, { x: 'date', y: 'gap', stroke: C.red, strokeWidth: 2, curve: 'step-after' }), Plot.ruleY([0]), ...todayRule,
      Plot.tip(traj, Plot.pointerX({ x: 'date', y: 'gap', title: (d) => `${fullDate(d.day)}\n${t('yield gap', 'yield gap')}: ${fmt(d.gap, 2)} ${yu} (${fmt(d.gapPct, 0)} %)` })),
    ] });
    const scen = cur.rainfed.map((r, i) => ({ year: r.year, rf: val(r), pt: val(cur.potential[i]) })).filter((d) => Number.isFinite(d.rf));
    draw(f3.body, { marginTop: 18, x: { label: t('rest of the cycle like the year', 'resto do ciclo como o ano'), tickFormat: 'd' }, y: { label: yu, zero: true }, marks: [
      Plot.ruleX(scen, { x: 'year', y1: 'rf', y2: (d) => Math.max(d.rf, d.pt), stroke: C.red, strokeOpacity: 0.35 }),
      Plot.dot(scen, { x: 'year', y: 'pt', r: 3.5, stroke: C.gray, strokeWidth: 1.5 }),
      Plot.dot(scen, { x: 'year', y: 'rf', r: 4, fill: C.blue, stroke: 'var(--surface)', strokeWidth: 1 }),
      Plot.ruleY([cur.rf.p50], { stroke: C.blue, strokeOpacity: 0.5, strokeDasharray: '4,3' }),
      Plot.tip(scen, Plot.pointerX({ x: 'year', y: 'rf', title: (d) => `${t('rest of the cycle like', 'resto do ciclo como')} ${d.year}\n${RF}: ${fmt(d.rf, 2)} ${yu}\n${NS}: ${fmt(d.pt, 2)} ${yu}` })),
    ] });

    // 2. weather of the season against the past years
    const ix = (d) => d - table.t0, cutoff = Math.min(known, sowing + n);
    const days = [];
    let cr = 0;
    for (let d = sowing - 30; d <= cutoff; d++) {
      const i = ix(d);
      const src = table.src.tmax[i], rain = table.cols.rain[i];
      if (d >= sowing) cr += rain;
      days.push({ day: d, date: asDate(d), tmax: table.cols.tmax[i], tmin: table.cols.tmin[i], rain, cum: d >= sowing ? cr : null, forecast: src === SRC.forecast || table.src.rain[i] === SRC.forecast });
    }
    const normal = [];                                   // past years, same days after sowing
    for (let k2 = 0; k2 <= n; k2++) {
      const cums = [], tmaxes = [];
      for (const a of analogs) {
        let c = 0;
        for (let j = 0; j <= k2; j++) c += table.cols.rain[ix(sowing - a.shift + j)];
        cums.push(c); tmaxes.push(table.cols.tmax[ix(sowing - a.shift + k2)]);
      }
      normal.push({ date: asDate(sowing + k2), cum: summary(cums), tmax: summary(tmaxes).p50 });
    }
    // rain expected for the rest of the cycle (median of the scenarios of the chosen mode)
    const adj = (d) => (useSeasonal ? seasonal.byMonth.get(isoDate(d).slice(0, 7)) ?? null : null);
    const kn = Math.max(0, cutoff - sowing), cumKnown = days.find((d) => d.day === cutoff)?.cum ?? 0, proj = [];
    if (cutoff < sowing + n) {
      const run = analogs.map(() => cumKnown);
      for (let k2 = kn + 1; k2 <= n; k2++) {
        const d = sowing + k2, a = adj(d);
        analogs.forEach((an, j) => { run[j] += table.cols.rain[ix(d - an.shift)] * (a ? a.rain : 1); });
        proj.push({ date: asDate(d), day: d, cum: summary(run).p50, tmax: normal[k2].tmax + (a ? a.dT : 0) });
      }
      proj.unshift({ date: asDate(cutoff), day: cutoff, cum: cumKnown, tmax: NaN });
    }
    const PROJ = useSeasonal ? t('Expected, with the seasonal forecast', 'Esperada, com a previsão sazonal') : t('Expected, past years', 'Esperada, anos passados');
    const events = [[t('flowering', 'floração'), flo], [t('maturity', 'maturidade'), mat]].filter(([, d]) => Number.isFinite(d))
      .map(([label, d]) => ({ label, date: asDate(sowing + Math.round(d)) }));
    const evRules = [Plot.ruleX(events, { x: 'date', stroke: 'currentColor', strokeOpacity: 0.3, strokeDasharray: '3,3' }),
      Plot.text(events, { x: 'date', text: 'label', frameAnchor: 'top', dy: -2, dx: 4, textAnchor: 'start', fill: 'currentColor', fillOpacity: 0.7, fontSize: 10.5 }), ...todayRule];
    const seg = (pred) => days.filter((d, i) => pred(d) || (days[i + 1] && pred(days[i + 1])));
    const after = days.filter((d) => d.cum != null);
    const w1 = figure(t('Rain accumulated since sowing', 'Chuva acumulada desde a semeadura'), t('This season against the same days of the past years (band: 80 % of the years). Dashed: forecast. Expected flowering and maturity: mean of the scenarios.', 'Esta safra contra os mesmos dias dos anos passados (faixa: 80 % dos anos). Tracejado: previsão. Floração e maturidade esperadas: média dos cenários.'),
      { legend: [[t('This season', 'Esta safra'), C.blue], [t('Past years (median)', 'Anos passados (mediana)'), C.gray, 'dash'], [t('80 % of the years', '80 % dos anos'), C.gray, 'band'], ...(proj.length ? [[PROJ, C.violet, 'dash']] : [])] });
    const w2 = figure(t('Daily temperature', 'Temperatura diária'), t('Thin gray: median Tmax of the past years. Faded: forecast.', 'Cinza fino: Tmax mediana dos anos passados. Esmaecido: previsão.'), { legend: [['Tmax', C.orange], ['Tmin', C.blue], [t('Tmax, past years', 'Tmax, anos passados'), C.gray], ...(useSeasonal ? [[t('Tmax expected with the seasonal forecast', 'Tmax esperada com a previsão sazonal'), C.violet]] : [])] });
    el.append(grid(w1.card, w2.card));
    draw(w1.body, { marginTop: 18, x: { label: null, ticks: 6 }, y: { label: 'mm', zero: true }, marks: [
      Plot.areaY(normal, { x: 'date', y1: (d) => d.cum.p10, y2: (d) => d.cum.p90, fill: C.gray, fillOpacity: 0.15 }),
      Plot.lineY(normal, { x: 'date', y: (d) => d.cum.p50, stroke: C.gray, strokeWidth: 1.5, strokeDasharray: '5,4' }),
      Plot.lineY(after.filter((d) => !d.forecast), { x: 'date', y: 'cum', stroke: C.blue, strokeWidth: 2 }),
      Plot.lineY(seg((d) => d.forecast).filter((d) => d.cum != null), { x: 'date', y: 'cum', stroke: C.blue, strokeWidth: 2, strokeDasharray: '4,3' }),
      Plot.lineY(proj, { x: 'date', y: 'cum', stroke: C.violet, strokeWidth: 1.8, strokeDasharray: '2,3' }),
      ...evRules,
      Plot.tip(after, Plot.pointerX({ x: 'date', y: 'cum', title: (d) => { const nm = normal[d.day - sowing]; return `${fullDate(d.day)}${d.forecast ? ` (${t('forecast', 'previsão')})` : ''}\n${t('this season', 'esta safra')}: ${fmt(d.cum, 0)} mm\n${t('past years', 'anos passados')}: ${fmt(nm.cum.p50, 0)} mm (${fmt(nm.cum.p10, 0)}–${fmt(nm.cum.p90, 0)})`; } })),
    ] });
    draw(w2.body, { marginTop: 18, x: { label: null, ticks: 6 }, y: { label: '°C' }, marks: [
      Plot.lineY(normal, { x: 'date', y: 'tmax', stroke: C.gray, strokeWidth: 1 }),
      ...(useSeasonal ? [Plot.lineY(proj.filter((d) => Number.isFinite(d.tmax)), { x: 'date', y: 'tmax', stroke: C.violet, strokeWidth: 1.2 })] : []),
      ...[['tmax', C.orange], ['tmin', C.blue]].flatMap(([v, c]) => [
        Plot.lineY(days.filter((d) => !d.forecast), { x: 'date', y: v, stroke: c, strokeWidth: 1.6 }),
        Plot.lineY(seg((d) => d.forecast), { x: 'date', y: v, stroke: c, strokeWidth: 1.6, strokeOpacity: 0.45 })]),
      ...evRules,
      Plot.tip(days, Plot.pointerX({ x: 'date', y: 'tmax', title: (d) => `${fullDate(d.day)}${d.forecast ? ` (${t('forecast', 'previsão')})` : ''}\nTmax ${fmt(d.tmax, 1)} °C · Tmin ${fmt(d.tmin, 1)} °C\n${t('rain', 'chuva')} ${fmt(d.rain, 1)} mm` })),
    ] });

    // seasonal forecast used
    if (seasonal && seas) {
      const pct = (r) => { const v = Math.round(100 * (r - 1)); return `${v > 0 ? '+' : v < 0 ? '−' : ''}${fmt(Math.abs(v), 0)} %`; };
      el.append(h('section.card', h('h2', t('ECMWF seasonal forecast used', 'Previsão sazonal do ECMWF usada')),
        h('p.hint', t('Monthly anomalies of the ensemble mean relative to the model’s own climate (its re-forecasts), so the model biases cancel. Each past year keeps its day-to-day sequence and is shifted by these anomalies after the last day of the weather forecast: temperature and dew point added, rain and radiation multiplied. A seasonal forecast tells whether a month tends to be warmer, wetter or drier than normal — not the weather of each day — and its skill varies by region and season.',
          'Anomalias mensais da média do conjunto em relação ao clima do próprio modelo (as suas re-previsões), de modo que os erros sistemáticos do modelo se cancelam. Cada ano passado mantém a sua sequência dia a dia e é deslocado por essas anomalias depois do último dia da previsão do tempo: temperatura e ponto de orvalho somados, chuva e radiação multiplicadas. A previsão sazonal indica se um mês tende a ser mais quente, chuvoso ou seco que o normal — não o tempo de cada dia — e a sua qualidade varia com a região e a época.')),
        dataTable(seasonal.months, [
          [t('Month', 'Mês'), (m) => m.month],
          [t('Temperature', 'Temperatura'), (m) => `${m.dT >= 0 ? '+' : '−'}${fmt(Math.abs(m.dT), 1)} °C`, 'num'],
          [t('Rain', 'Chuva'), (m) => pct(m.rain), 'num'],
          [t('Rain, model forecast / normal', 'Chuva, previsão / normal do modelo'), (m) => `${fmt(m.rainMean, 0)} / ${fmt(m.rainNormal, 0)} mm`, 'num'],
          [t('Radiation', 'Radiação'), (m) => pct(m.srad), 'num'],
          [t('Dew point', 'Ponto de orvalho'), (m) => `${m.dDew >= 0 ? '+' : '−'}${fmt(Math.abs(m.dDew), 1)} °C`, 'num'],
        ])));
    }

    // 3. what happened so far
    const span = (a, b) => days.filter((d) => d.day >= a && d.day <= b);
    const soFar = span(sowing, observedEnd), k3 = Math.max(0, observedEnd - sowing);
    const rainNow = soFar.reduce((x, d) => x + d.rain, 0), rainNormal = normal[Math.min(k3, n)]?.cum;
    const hot = soFar.filter((d) => d.tmax >= 35).length, fcDays = days.filter((d) => d.forecast && d.day >= sowing);
    const fcRain = fcDays.reduce((x, d) => x + d.rain, 0);
    const seq = last.rainfed.find((r) => r.inputs?.sequence)?.inputs.sequence, L = emu.card.sequence ? emu.card.sequence.days[1] - emu.card.sequence.days[0] + 1 : 0;
    const stressMean = (a, b) => { if (!seq) return NaN; const v = []; for (let d = a; d <= b; d++) { const kk = d - sowing + 30; if (kk >= 0 && kk < L) v.push(seq[7 * L + kk]); } return mean(v); };
    const items = [
      [t('Rain since sowing', 'Chuva desde a semeadura'), `${fmt(rainNow, 0)} mm`, rainNormal ? t(`past years: ${fmt(rainNormal.p50, 0)} mm (${fmt(rainNormal.p10, 0)}–${fmt(rainNormal.p90, 0)})`, `anos passados: ${fmt(rainNormal.p50, 0)} mm (${fmt(rainNormal.p10, 0)}–${fmt(rainNormal.p90, 0)})`) : ''],
      [t('Days with Tmax ≥ 35 °C', 'Dias com Tmax ≥ 35 °C'), fmt(hot, 0), t('since sowing', 'desde a semeadura')],
      [t('Water stress, last 14 days', 'Estresse hídrico, últimos 14 dias'), fmt(stressMean(observedEnd - 13, observedEnd), 2), t('simple soil bucket: 0 none, 1 severe', 'balde de solo simples: 0 nenhum, 1 severo')],
      ...(fcDays.length ? [[t(`Forecast, next ${fcDays.length} days`, `Previsão, próximos ${fcDays.length} dias`), `${fmt(fcRain, 0)} mm`, t(`water stress ${fmt(stressMean(observedEnd + 1, known), 2)}`, `estresse hídrico ${fmt(stressMean(observedEnd + 1, known), 2)}`)]] : []),
    ];
    el.append(h('section.card', h('h2', t('The season so far', 'A safra até agora')),
      h('div.tiles', items.map(([a, b, c]) => tile(a, b, '', c))),
      domainSummary(cur.rainfed),
      h('p.hint', t('The yield is what DSSAT/AquaCrop would simulate for this weather, soil and cultivar — not a measurement of the field (pests, management and the real soil are outside the model), with the emulator error on top. Use the changes along the season, the yield gap and the range of the scenarios rather than a single number. ',
        'A produtividade é o que o DSSAT/AquaCrop simularia para este clima, solo e cultivar — não uma medida da lavoura (pragas, manejo e o solo real estão fora do modelo), com o erro do emulador por cima. Use as mudanças ao longo da safra, o yield gap e a faixa dos cenários, não um número único. '),
        openMeteo ? h('span', t('Recent days and forecast: ', 'Dias recentes e previsão: '), h('a', { href: 'https://open-meteo.com/', target: '_blank', rel: 'noopener' }, t('weather data by Open-Meteo.com', 'dados meteorológicos de Open-Meteo.com')), ' (CC BY 4.0)', seas ? t('; seasonal forecast based on ECMWF data and products (www.ecmwf.int).', '; previsão sazonal baseada em dados e produtos do ECMWF (www.ecmwf.int).') : '.') : null)));
  },
};
