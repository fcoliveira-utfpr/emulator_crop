// Open-Meteo (ERA5 archive, used by the app for the most recent days) against NASA POWER (the training
// source) at the 7 independent sites, 2015–2024: daily bias and RMSE of each variable, and the change of
// the expected yield of the monitoring when the last 5 known days (as in the app) or the whole observed
// part of the season come from Open-Meteo instead of NASA POWER.
//   node tests/openmeteo_vs_power.mjs
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Emulator } from '../src/engine/emulator.js';
import { dayNumber, fromYMD, isoDate } from '../src/engine/dates.js';
import { scenarioDays, scenarioSeries } from '../src/engine/monitor.js';
import { prepareSoil } from '../src/engine/soil.js';
import { fetchSoilGrids } from '../src/engine/soilgrids.js';
import { COLUMNS, fetchPower, fillGaps, tableFromRecords, SRC } from '../src/engine/weather.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(here, '../../data/hindcast');
const cacheDir = path.join(os.homedir(), '.cache', 'cropemu', 'power_js');
fs.mkdirSync(cacheDir, { recursive: true });
const netFetch = globalThis.fetch;
globalThis.fetch = async (url, init) => {                       // disk cache for NASA POWER and Open-Meteo
  const u = String(url);
  if (!u.includes('power.larc.nasa.gov') && !u.includes('open-meteo.com')) return netFetch(url, init);
  const f = path.join(cacheDir, crypto.createHash('sha1').update(u).digest('hex') + '.json');
  if (!fs.existsSync(f)) {
    const r = await netFetch(url, init);
    if (!r.ok) return r;
    fs.writeFileSync(f, await r.text());
  }
  return new Response(fs.readFileSync(f, 'utf8'), { status: 200, headers: { 'content-type': 'application/json' } });
};
const fetcher = async (p) => { const b = fs.readFileSync(path.join(here, '../public', p)); return { json: async () => JSON.parse(b), arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.length) }; };

const SITES = [
  ['Londrina-PR', -23.19, -51.18, 304], ['Rio Verde-GO', -17.80, -50.92, 319], ['Sorriso-MT', -12.55, -55.71, 304],
  ['Passo Fundo-RS', -28.26, -52.41, 334], ['Pergamino-AR', -33.89, -60.57, 334], ['Ames-IA', 42.03, -93.62, 123],
  ['Harbin-CN', 46.20, 126.50, 122]];
const DAILY = { temperature_2m_max: 'tmax', temperature_2m_min: 'tmin', shortwave_radiation_sum: 'srad', precipitation_sum: 'rain',
  relative_humidity_2m_mean: 'rhum', dew_point_2m_mean: 'dewp', wind_speed_10m_mean: 'wind' };
const WIND_2M = 4.87 / Math.log(67.8 * 10 - 5.42);                // as in src/engine/openmeteo.js

async function archive(lat, lon, start, end) {
  const q = new URLSearchParams({ latitude: lat.toFixed(4), longitude: lon.toFixed(4), daily: Object.keys(DAILY).join(','),
    timezone: 'GMT', wind_speed_unit: 'ms', start_date: start, end_date: end });
  const r = await fetch(`https://archive-api.open-meteo.com/v1/archive?${q}`);
  const p = await r.json();
  const recs = p.daily.time.map((date, i) => {
    const o = { date };
    for (const [api, name] of Object.entries(DAILY)) { const v = p.daily[api]?.[i]; if (Number.isFinite(v)) o[name] = name === 'wind' ? v * WIND_2M : v; }
    return o;
  });
  return tableFromRecords(recs, SRC.openmeteo);
}

const CULT = JSON.parse(fs.readFileSync(path.join(outDir, 'sims', 'cultivars.json'), 'utf8'));
const emus = { dssat: await Emulator.load('dssat-soybean-v3', '', fetcher), aquacrop: await Emulator.load('aquacrop-soybean-v3', '', fetcher) };
const VARS = ['tmax', 'tmin', 'srad', 'rain', 'dewp', 'wind'];
const stats = [], effect = [];
for (const [name, lat, lon, doy] of SITES) {
  const [power, soilRaw] = await Promise.all([fetchPower(lat, lon, dayNumber('1984-01-01'), dayNumber('2026-06-30')), fetchSoilGrids(lat, lon)]);
  const P = power.table, elev = power.elevation ?? 0;
  fillGaps(P);
  const O = await archive(lat, lon, '2015-01-01', '2025-08-31');
  // daily agreement 2015–2024
  for (const v of VARS) {
    let n = 0, s = 0, s2 = 0, sp = 0;
    for (let d = dayNumber('2015-01-01'); d <= dayNumber('2024-12-31'); d++) {
      const a = O.cols[v][d - O.t0], b = P.cols[v][d - P.t0];
      if (!Number.isFinite(a) || !Number.isFinite(b)) continue;
      n++; s += a - b; s2 += (a - b) ** 2; sp += b;
    }
    stats.push([name, v, n, (s / n).toFixed(3), Math.sqrt(s2 / n).toFixed(3), (sp / n).toFixed(3)].join(','));
  }
  // effect on the expected yield, seasons 2015–2024 (the season must end before the archive ends)
  const md = new Date((fromYMD(2001, 1, 1) + doy - 1) * 864e5);
  for (const fam of ['dssat', 'aquacrop']) {
    const emu = emus[fam], card = emu.card, n = scenarioDays(card);
    const soil = prepareSoil(soilRaw.layers, card, lat).features;
    const cultivar = Object.fromEntries(card.cultivar.map((k) => [k, CULT[name][fam][k]]));
    const records = [], index = [];
    for (let Y = 2015; Y <= 2023; Y++) {
      const sowing = fromYMD(Y, md.getUTCMonth() + 1, md.getUTCDate());
      const analogs = [];
      for (let y = 1984; y <= 2024; y++) {
        if (y === Y) continue;
        const s = fromYMD(y, md.getUTCMonth() + 1, md.getUTCDate());
        if (s - 30 >= P.t0 && s + n < P.t0 + P.n) analogs.push({ year: y, shift: sowing - s });
      }
      for (const das of [30, 60, 90]) {
        const known = sowing + das;
        for (const variant of ['power', 'last5', 'all']) {
          // a copy of the POWER table with the observed days replaced by Open-Meteo
          const T = { ...P, cols: Object.fromEntries(COLUMNS.map((c) => [c, P.cols[c].slice()])), src: P.src };
          const from = variant === 'last5' ? known - 4 : variant === 'all' ? sowing - 30 : Infinity;
          for (let d = from; d <= known; d++) for (const c of COLUMNS) { const v = O.cols[c]?.[d - O.t0]; if (Number.isFinite(v)) T.cols[c][d - T.t0] = v; }
          for (const a of analogs) {
            records.push(emu.inputs(scenarioSeries(T, lat, elev, sowing, known, a.shift, n), soil, [{ sowing, cultivar, irrigated: false, co2: NaN }])[0]);
            index.push({ Y, das, variant });
          }
        }
      }
    }
    const pred = await emu.predict(records), yk = emu.keys.yield, sc = fam === 'dssat' ? 1e-3 : 1;
    const groups = new Map();
    pred.forEach((r, i) => { const k = index[i], key = `${k.Y}|${k.das}|${k.variant}`; (groups.get(key) ?? groups.set(key, []).get(key)).push(r.outputs[yk] * sc); });
    const med = (v) => { const s = v.filter(Number.isFinite).sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
    for (let Y = 2015; Y <= 2023; Y++) for (const das of [30, 60, 90]) {
      const base = med(groups.get(`${Y}|${das}|power`));
      effect.push([name, fam, Y, das, base.toFixed(4), (med(groups.get(`${Y}|${das}|last5`)) - base).toFixed(4), (med(groups.get(`${Y}|${das}|all`)) - base).toFixed(4)].join(','));
    }
  }
  console.log(name, 'done');
}
fs.writeFileSync(path.join(outDir, 'openmeteo_power_daily.csv'), ['site,var,n,bias,rmse,mean_power', ...stats].join('\n') + '\n');
fs.writeFileSync(path.join(outDir, 'openmeteo_power_effect.csv'), ['site,model,year,das,expected_power,change_last5,change_all', ...effect].join('\n') + '\n');
console.log('wrote', outDir);
