// Daily weather: tables, NASA POWER, gap filling and the prepared series used by the season inputs.
// Port of cropemu.weather (nasa_power, qc, eto) and cropemu.features.WeatherSeries.

import { dayNumber, dayOfYear, isoDate } from './dates.js';

export const COLUMNS = ['tmax', 'tmin', 'srad', 'rain', 'rhum', 'wind', 'dewp'];
export const REQUIRED = ['tmax', 'tmin', 'srad', 'rain'];
/** Source of each value in a table. */
export const SRC = { none: 0, user: 1, power: 2, filled: 3 };
export const POWER_FIRST_DAY = dayNumber('1984-01-01');

// ------------------------------------------------------------------ tables
/** A daily table: `n` contiguous days from day number `t0`; one Float64Array per column (NaN: missing). */
export function emptyTable(t0, n) {
  const cols = {}, src = {};
  for (const c of COLUMNS) { cols[c] = new Float64Array(n).fill(NaN); src[c] = new Uint8Array(n); }
  return { t0, n, cols, src };
}

/** Table from records `{date: 'YYYY-MM-DD', tmax, ...}`. */
export function tableFromRecords(records, source) {
  const list = [...records].filter((r) => r?.date);
  if (!list.length) return null;
  const days = list.map((r) => dayNumber(r.date));
  const t0 = Math.min(...days), t1 = Math.max(...days);
  const table = emptyTable(t0, t1 - t0 + 1);
  list.forEach((r, k) => {
    const i = days[k] - t0;
    for (const c of COLUMNS) if (Number.isFinite(r[c])) { table.cols[c][i] = r[c]; table.src[c][i] = source; }
  });
  return table;
}

/** `user` completed with `remote` day by day and column by column; user values always win.
 * Returns the merged table and the number of values taken from `remote` per column. */
export function combine(user, remote) {
  if (!user) return { table: remote, taken: {} };
  if (!remote) return { table: user, taken: {} };
  const t0 = Math.min(user.t0, remote.t0), t1 = Math.max(user.t0 + user.n, remote.t0 + remote.n);
  const table = emptyTable(t0, t1 - t0), taken = {};
  for (const c of COLUMNS) {
    for (let i = 0; i < table.n; i++) {
      const iu = t0 + i - user.t0, ir = t0 + i - remote.t0;
      const u = iu >= 0 && iu < user.n ? user.cols[c][iu] : NaN;
      if (Number.isFinite(u)) { table.cols[c][i] = u; table.src[c][i] = user.src[c][iu]; continue; }
      const r = ir >= 0 && ir < remote.n ? remote.cols[c][ir] : NaN;
      if (Number.isFinite(r)) { table.cols[c][i] = r; table.src[c][i] = remote.src[c][ir]; taken[c] = (taken[c] ?? 0) + 1; }
    }
  }
  return { table, taken };
}

/** Fill NaN runs of up to `maxGap` days (cropemu.weather.fill_gaps): rain becomes 0, the other
 * columns are interpolated linearly between the valid days around the gap. Longer gaps stay NaN. */
export function fillGaps(table, maxGap = 5) {
  let filled = 0;
  for (const c of COLUMNS) {
    const x = table.cols[c], s = table.src[c];
    let i = 0;
    while (i < table.n) {
      if (Number.isFinite(x[i])) { i++; continue; }
      let j = i;
      while (j < table.n && !Number.isFinite(x[j])) j++;          // NaN run [i, j)
      if (j - i <= maxGap) {
        if (c === 'rain') for (let k = i; k < j; k++) { x[k] = 0; s[k] = SRC.filled; filled++; }
        else if (i > 0 && j < table.n) {                            // inside: valid days on both sides
          const a = x[i - 1], b = x[j];
          for (let k = i; k < j; k++) { x[k] = a + (b - a) * (k - i + 1) / (j - i + 1); s[k] = SRC.filled; filled++; }
        }
      }
      i = j;
    }
  }
  return filled;
}

/** First and last day (numbers) with all required columns, or null. */
export function completeSpan(table) {
  const ok = (i) => REQUIRED.every((c) => Number.isFinite(table.cols[c][i]));
  let a = 0, b = table.n - 1;
  while (a <= b && !ok(a)) a++;
  while (b >= a && !ok(b)) b--;
  return a > b ? null : [table.t0 + a, table.t0 + b];
}

/** Days with any required column missing between `first` and `last` (day numbers). */
export function missingDays(table, first, last) {
  const out = [];
  for (let d = first; d <= last; d++) {
    const i = d - table.t0;
    if (i < 0 || i >= table.n || REQUIRED.some((c) => !Number.isFinite(table.cols[c][i]))) out.push(d);
  }
  return out;
}

// ------------------------------------------------------------------ NASA POWER
const POWER_URL = 'https://power.larc.nasa.gov/api/temporal/daily/point';
const POWER_PARAMETERS = { ALLSKY_SFC_SW_DWN: 'srad', T2M_MAX: 'tmax', T2M_MIN: 'tmin', PRECTOTCORR: 'rain', RH2M: 'rhum', WS2M: 'wind', T2MDEW: 'dewp' };

async function cachedJson(url) {
  let cache = null;
  try { cache = await caches.open('cropemu-power-v1'); const hit = await cache.match(url); if (hit) return hit.json(); } catch { cache = null; }
  const response = await fetch(url);
  if (!response.ok) throw new Error(`a NASA POWER respondeu ${response.status}`);
  const text = await response.text();
  try { await cache?.put(url, new Response(text, { headers: { 'content-type': 'application/json' } })); } catch { /* cache is optional */ }
  return JSON.parse(text);
}

/** Daily weather of a point from NASA POWER (the source of the training weather).
 * `first`/`last` are day numbers; values not yet available (fill -999) are NaN. */
export async function fetchPower(lat, lon, first, last) {
  const url = new URL(POWER_URL);
  url.search = new URLSearchParams({
    parameters: Object.keys(POWER_PARAMETERS).join(','), community: 'AG',
    latitude: Number(lat).toFixed(4), longitude: Number(lon).toFixed(4),
    start: isoDate(first).replaceAll('-', ''), end: isoDate(last).replaceAll('-', ''), format: 'JSON',
  });
  const payload = await cachedJson(url.toString());
  const params = payload?.properties?.parameter;
  if (!params) throw new Error('resposta da NASA POWER sem dados diários');
  const fill = payload.header?.fill_value ?? -999;
  const records = Object.keys(Object.values(params)[0] ?? {}).map((k) => {
    const r = { date: `${k.slice(0, 4)}-${k.slice(4, 6)}-${k.slice(6, 8)}` };
    for (const [api, name] of Object.entries(POWER_PARAMETERS)) {
      const v = params[api]?.[k];
      if (Number.isFinite(v) && v !== fill && v > -900) r[name] = v;
    }
    return r;
  });
  const [plon, plat, elev] = payload.geometry?.coordinates ?? [];
  return { table: tableFromRecords(records, SRC.power), elevation: Number.isFinite(elev) ? elev : null, cell: { lat: plat, lon: plon } };
}

// ------------------------------------------------------------------ physics (FAO-56)
const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));
const rad = (x) => x * Math.PI / 180;
export const satVp = (t) => 0.6108 * Math.exp(17.27 * t / (t + 237.3));

/** Day length (h) with civil twilight (sun at -6°), the CROPGRO photoperiod. */
export function daylength(lat, doy) {
  const phi = rad(lat), dec = rad(-23.45 * Math.cos(2 * Math.PI * (doy + 10) / 365));
  const cosH = (Math.sin(rad(-6)) - Math.sin(phi) * Math.sin(dec)) / (Math.cos(phi) * Math.cos(dec));
  return 24 / Math.PI * Math.acos(clamp(cosH, -1, 1));
}

function extraterrestrial(lat, doy) {
  const phi = rad(lat), dr = 1 + 0.033 * Math.cos(2 * Math.PI * doy / 365);
  const dec = 0.409 * Math.sin(2 * Math.PI * doy / 365 - 1.39);
  const ws = Math.acos(clamp(-Math.tan(phi) * Math.tan(dec), -1, 1));
  return 24 * 60 / Math.PI * 0.0820 * dr * (ws * Math.sin(phi) * Math.sin(dec) + Math.cos(phi) * Math.cos(dec) * Math.sin(ws));
}

/** Daily reference ET (mm), FAO-56 Penman-Monteith; missing wind is 2 m/s. */
export function etoDay(tmax, tmin, srad, wind, ea, lat, elev, doy) {
  const u2 = Number.isFinite(wind) ? wind : 2;
  const tmean = (tmax + tmin) / 2, p = 101.3 * ((293 - 0.0065 * elev) / 293) ** 5.26;
  const gamma = 0.000665 * p, delta = 4098 * satVp(tmean) / (tmean + 237.3) ** 2;
  const es = (satVp(tmax) + satVp(tmin)) / 2, e = Math.min(ea, es);
  const rso = (0.75 + 2e-5 * elev) * extraterrestrial(lat, doy);
  const ratio = clamp(rso > 0 ? srad / rso : 1, 0.3, 1);
  const rnl = 4.903e-9 * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2 * (0.34 - 0.14 * Math.sqrt(e)) * (1.35 * ratio - 0.35);
  const eto = (0.408 * delta * (0.77 * srad - rnl) + gamma * 900 / (tmean + 273) * u2 * (es - e)) / (delta + gamma * (1 + 0.34 * u2));
  return Math.max(eto, 0);
}

/** Growing degrees of a day, AquaCrop method 3. */
export const gdd = (tmax, tmin, tbase = 5, tupper = 30) => Math.max((clamp(tmax, tbase, tupper) + Math.min(tmin, tupper)) / 2 - tbase, 0);

// ------------------------------------------------------------------ prepared series
/** Daily weather of one point prepared once for many seasons (cropemu.features.WeatherSeries). */
export class WeatherSeries {
  constructor(table, lat, elev = 0) {
    const { t0, n, cols } = table;
    Object.assign(this, { t0, n, lat, elev, tmax: cols.tmax, tmin: cols.tmin, srad: cols.srad, rain: cols.rain, wind: cols.wind });
    this.doy = new Int16Array(n); this.ea = new Float64Array(n); this.eto = new Float64Array(n);
    this.vpd = new Float64Array(n); this.dayl = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const doy = dayOfYear(t0 + i), tx = cols.tmax[i], tn = cols.tmin[i];
      const esMean = (satVp(tx) + satVp(tn)) / 2;
      let ea = satVp(tn);                                                  // humidity missing: dew point = Tmin
      if (Number.isFinite(cols.rhum[i])) ea = cols.rhum[i] / 100 * esMean;
      if (Number.isFinite(cols.dewp[i])) ea = satVp(cols.dewp[i]);
      this.doy[i] = doy; this.ea[i] = ea;
      this.eto[i] = etoDay(tx, tn, cols.srad[i], cols.wind[i], ea, lat, elev, doy);
      this.vpd[i] = Math.max(esMean - ea, 0);
      this.dayl[i] = daylength(lat, doy);
    }
  }

  /** Index of a day number in the series. */
  index(day) { return day - this.t0; }
  covers(day, start, end) { const i = this.index(day); return i + start >= 0 && i + end <= this.n; }

  /** Weather summary of days [start, end) after sowing, with a climate perturbation. */
  window(sowing, start, end, dt = 0, rainFactor = 1) {
    const i0 = this.index(sowing) + start, i1 = i0 + (end - start), m = end - start;
    let tmax = 0, tmin = 0, srad = 0, rain = 0, vpd = 0, dayl = 0, hot32 = 0, hot35 = 0;
    for (let i = i0; i < i1; i++) {
      const tx = this.tmax[i] + dt, tn = this.tmin[i];
      tmax += tx; tmin += tn; srad += this.srad[i]; rain += this.rain[i]; dayl += this.dayl[i];
      // ΔT also raises the VPD: shift the saturation part, keep the actual vapour pressure
      vpd += dt ? this.vpd[i] + ((satVp(tx) + satVp(tn + dt)) - (satVp(tx - dt) + satVp(tn))) / 2 : this.vpd[i];
      if (tx >= 32) hot32++;
      if (tx >= 35) hot35++;
    }
    return { tmax: tmax / m, tmin: tmin / m + dt, srad: srad / m, rain: rain * rainFactor, vpd: vpd / m, dayl: dayl / m, hot32, hot35 };
  }

  /** Daily ETo and stress index of a one-layer bucket from `start` to `end` days after sowing. */
  bucketStress(sowing, pawMm, initial = 0.5, start = -30, end = 130, dt = 0, rainFactor = 1, p = 0.5) {
    const i0 = this.index(sowing) + start, m = end - start, cap = Math.max(pawMm, 1);
    const eto = new Float64Array(m), stress = new Float64Array(m);
    let s = initial * cap;
    for (let k = 0; k < m; k++) {
      const i = i0 + k;
      eto[k] = dt ? etoDay(this.tmax[i] + dt, this.tmin[i] + dt, this.srad[i], this.wind[i], this.ea[i], this.lat, this.elev, this.doy[i]) : this.eto[i];
      s = Math.min(s + this.rain[i] * rainFactor, cap);
      stress[k] = 1 - Math.min(1, s / ((1 - p) * cap));
      s = Math.max(s - eto[k] * (1 - stress[k]), 0);
    }
    return { eto, stress };
  }

  /** Days after sowing to accumulate each thermal requirement ({name: GDD}). A requirement not
   * met within `maxDays` gets `maxDays`; one not met because the series ends gets NaN. */
  thermalDays(sowing, requirements, tbase, tupper, dt = 0, maxDays = 600) {
    const i0 = this.index(sowing), i1 = Math.min(i0 + maxDays, this.n);
    const names = Object.keys(requirements), out = {};
    let cum = 0, pending = names.length;
    for (let i = i0; i < i1 && pending; i++) {
      cum += gdd(this.tmax[i] + dt, this.tmin[i] + dt, tbase, tupper);
      for (const name of names) if (out[name] === undefined && cum >= requirements[name]) { out[name] = i - i0 + 1; pending--; }
    }
    for (const name of names) if (out[name] === undefined) out[name] = i1 - i0 >= maxDays ? maxDays : NaN;
    return out;
  }

  /** Mean GDD of the `days` days after the day of year of `sowing`, over the complete years
   * (cropemu.emulator.season_gdd; the slice is inclusive at both ends, as in pandas). */
  seasonGdd(sowingDoy, days, tbase = 5, tupper = 30) {
    const first = this.t0, last = this.t0 + this.n - 1, sums = [];
    const y0 = new Date(first * 86400000).getUTCFullYear(), y1 = new Date(last * 86400000).getUTCFullYear();
    for (let y = y0; y <= y1; y++) {
      const s = Math.round(Date.UTC(y, 0, 1) / 86400000) + sowingDoy - 1, e = s + days;
      if (s < first || e > last) continue;
      let sum = 0;
      for (let d = s; d <= e; d++) { const i = d - this.t0, g = gdd(this.tmax[i], this.tmin[i], tbase, tupper); if (Number.isFinite(g)) sum += g; }
      sums.push(sum);
    }
    if (!sums.length) throw new Error('o clima não cobre nenhuma safra completa para estimar o ciclo');
    return sums.reduce((a, b) => a + b, 0) / sums.length;
  }

  /** GDD from day `a` to day `b` (inclusive). */
  gddBetween(a, b, tbase = 5, tupper = 30) {
    let sum = 0;
    for (let d = a; d <= b; d++) sum += gdd(this.tmax[d - this.t0], this.tmin[d - this.t0], tbase, tupper);
    return sum;
  }
}
