// Crop monitoring of the current season: the weather known so far (observed, then forecast)
// completed by the weather of past years (one scenario per year), re-run week by week so the
// expected yield and the yield gap (no water stress − rainfed) can be followed along the cycle.
// Soil and cultivar stay fixed; only the weather of the rest of the cycle changes between scenarios.

import { fromYMD, isoDate, yearOf } from './dates.js';
import { daysAfter } from './season.js';
import { COLUMNS, emptyTable, REQUIRED, WeatherSeries } from './weather.js';

/** Days of weather after sowing that a scenario must provide. */
export const scenarioDays = (card) => (card.thermal ? 365 : daysAfter(card) + 1);

/** Last day `d` such that every day from `first` to `d` has the required columns (first − 1 if none). */
export function lastContinuous(table, first) {
  let d = first;
  while (d - table.t0 < table.n && d >= table.t0 && REQUIRED.every((c) => Number.isFinite(table.cols[c][d - table.t0]))) d++;
  return d - 1;
}

const complete = (table, a, b) => a >= table.t0 && b < table.t0 + table.n
  && REQUIRED.every((c) => { const x = table.cols[c]; for (let d = a; d <= b; d++) if (!Number.isFinite(x[d - table.t0])) return false; return true; });

/** Past years whose weather can complete the season: the same sowing day and month, all days present. */
export function analogYears(table, sowing, card, years = null) {
  const date = new Date(sowing * 864e5), m = date.getUTCMonth() + 1, d = date.getUTCDate(), n = scenarioDays(card);
  const out = [];
  for (let y = yearOf(table.t0); y < yearOf(sowing); y++) {
    if (years && !years.includes(y)) continue;
    const s = fromYMD(y, m, d);                               // 29 Feb rolls to 1 Mar
    if (s + n >= sowing - 30) continue;                       // must end before the current season starts
    if (complete(table, s - 30, s + n)) out.push({ year: y, shift: sowing - s });
  }
  return out;
}

/** Weather series of one scenario: `table` up to day `known`, then the weather `shift` days earlier
 * (the analog year), from 30 days before sowing to `n` days after. */
export function scenarioSeries(table, lat, elev, sowing, known, shift, n, adjust = null) {
  const t0 = sowing - 30, len = n + 31, out = emptyTable(t0, len);
  for (let k = 0; k < len; k++) {
    const d = t0 + k, i = (d <= known ? d : d - shift) - table.t0;
    if (i < 0 || i >= table.n) continue;
    for (const c of COLUMNS) { out.cols[c][k] = table.cols[c][i]; out.src[c][k] = table.src[c][i]; }
    const a = d > known && adjust ? adjust(d) : null;
    if (a) {                                   // past year shifted to the seasonal forecast of the month
      out.cols.tmax[k] += a.dT; out.cols.tmin[k] += a.dT; out.cols.dewp[k] += a.dDew;
      out.cols.rain[k] *= a.rain; out.cols.srad[k] *= a.srad;
    }
  }
  return new WeatherSeries(out, lat, elev);
}

/** Adjustment of a day by the seasonal forecast of its month (null outside the forecast months). */
export const seasonalAdjust = (seasonal) => (day) => seasonal?.byMonth.get(isoDate(day).slice(0, 7)) ?? null;

const quantile = (values, q) => {
  const v = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!v.length) return NaN;
  const p = (v.length - 1) * q, i = Math.floor(p);
  return v[i] + (v[Math.min(i + 1, v.length - 1)] - v[i]) * (p - i);
};
export const summary = (values) => ({ p10: quantile(values, 0.1), p25: quantile(values, 0.25), p50: quantile(values, 0.5), p75: quantile(values, 0.75), p90: quantile(values, 0.9) });

/** Monitoring dates: sowing, then every `step` days while the weather is observed, and the last
 * known day (forecast included) at the end. */
export function checkpoints(sowing, observedEnd, known, n, step = 7) {
  const end = Math.min(observedEnd, sowing + n), out = [];
  for (let d = sowing; d <= end; d += step) out.push({ day: d, known: d, forecast: false });
  if (out.length && out.at(-1).day < end) out.push({ day: end, known: end, forecast: false });
  if (known > observedEnd && observedEnd < sowing + n) out.push({ day: Math.min(known, sowing + n), known, forecast: true });
  return out;
}

/** Runs the scenarios of every monitoring date. Returns, per checkpoint, the rows of each analog
 * year rainfed and without water stress: [{...checkpoint, rainfed: [row], potential: [row]}]. */
export async function monitor(emu, table, { lat, elev, soil, sowing, cultivar, observedEnd, known, analogs, step = 7, co2 = NaN, seasonal = null, onProgress = null }) {
  const n = scenarioDays(emu.card), cps = checkpoints(sowing, observedEnd, known, n, step);
  // the latest estimate again with the past years adjusted by the seasonal forecast
  if (seasonal && cps.length && cps.at(-1).known < sowing + n) cps.push({ ...cps.at(-1), seasonal: true });
  const records = [], index = [];
  cps.forEach((cp, ic) => {
    for (const a of analogs) {
      const ws = scenarioSeries(table, lat, elev, sowing, cp.known, a.shift, n, cp.seasonal ? seasonalAdjust(seasonal) : null);
      const seasons = [false, true].map((irrigated) => ({ sowing, cultivar, irrigated, co2, year: a.year }));
      emu.inputs(ws, soil, seasons).forEach((rec, j) => { records.push(rec); index.push({ ic, year: a.year, irrigated: seasons[j].irrigated }); });
    }
    onProgress?.(ic + 1, cps.length);
  });
  const rows = await emu.predict(records);
  const out = cps.map((cp) => ({ ...cp, rainfed: [], potential: [] }));
  rows.forEach((r, i) => { const { ic, year, irrigated } = index[i]; out[ic][irrigated ? 'potential' : 'rainfed'].push({ ...r, year, inputs: records[i] }); });
  return out;
}
