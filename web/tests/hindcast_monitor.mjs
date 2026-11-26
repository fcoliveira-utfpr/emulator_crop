// Hindcast of the crop monitoring: past seasons replayed as if they were in progress.
// For each independent site, target year Y and day k after sowing, the weather of Y is known up to k
// and the rest of the cycle comes from every other year (leave-one-year-out), exactly as the app does
// (monitor.js). The reference is the same emulator run with the complete weather of Y, so the error
// measures the scenario method (the unknown weather), not the emulation.
//   node tests/hindcast_monitor.mjs [out.csv]
// NASA POWER responses are cached on disk (~/.cache/cropemu/power_js) so reruns are offline.
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Emulator } from '../src/engine/emulator.js';
import { dayNumber, fromYMD } from '../src/engine/dates.js';
import { scenarioDays, scenarioSeries, similarYears } from '../src/engine/monitor.js';
import { aquacropCultivar, dssatCultivar, typicalMg } from '../src/engine/season.js';
import { prepareSoil } from '../src/engine/soil.js';
import { fetchSoilGrids } from '../src/engine/soilgrids.js';
import { fetchPower, fillGaps, WeatherSeries } from '../src/engine/weather.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const out = process.argv[2] ?? path.join(here, '../../data/hindcast/hindcast_monitor.csv');
const cultivarFile = path.join(here, '../../data/hindcast/sims/cultivars.json');
const CULTIVARS = fs.existsSync(cultivarFile) ? JSON.parse(fs.readFileSync(cultivarFile, 'utf8')) : null;
console.log('cultivars', CULTIVARS ? cultivarFile : 'app defaults');

// ---- disk cache for NASA POWER (one large request per site)
const cacheDir = path.join(os.homedir(), '.cache', 'cropemu', 'power_js');
fs.mkdirSync(cacheDir, { recursive: true });
const netFetch = globalThis.fetch;
globalThis.fetch = async (url, init) => {
  const u = String(url);
  if (!u.includes('power.larc.nasa.gov')) return netFetch(url, init);
  const f = path.join(cacheDir, crypto.createHash('sha1').update(u).digest('hex') + '.json');
  if (!fs.existsSync(f)) {
    const r = await netFetch(url, init);
    if (!r.ok) return r;
    fs.writeFileSync(f, await r.text());
  }
  const text = fs.readFileSync(f, 'utf8');
  return new Response(text, { status: 200, headers: { 'content-type': 'application/json' } });
};

const fetcher = async (p) => { const b = fs.readFileSync(path.join(here, '../public', p)); return { json: async () => JSON.parse(b), arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.length) }; };

// independent sites (benchmark/validate_sites.py) and GGCMI Phase 3 rainfed planting day of year
const SITES = [
  ['Londrina-PR', -23.19, -51.18, 304], ['Rio Verde-GO', -17.80, -50.92, 319], ['Sorriso-MT', -12.55, -55.71, 304],
  ['Passo Fundo-RS', -28.26, -52.41, 334], ['Pergamino-AR', -33.89, -60.57, 334], ['Ames-IA', 42.03, -93.62, 123],
  ['Harbin-CN', 46.20, 126.50, 122]];
const YEARS = Array.from({ length: 30 }, (_, i) => 1995 + i);          // target seasons 1995–2024
const DAS = [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150];          // days after sowing known
const MODELS = ['dssat-soybean-v3', 'aquacrop-soybean-v3'];

const emus = Object.fromEntries(await Promise.all(MODELS.map(async (m) => [m, await Emulator.load(m, '', fetcher)])));
const rows = [['site', 'model', 'year', 'das', 'truth_rf', 'truth_p', 'truth_mat', 'analog', 'rf', 'p', 'sim_rank', 'sim_dist'].join(',')];

const complete = (table, a, b) => a >= table.t0 && b < table.t0 + table.n
  && ['tmax', 'tmin', 'srad', 'rain'].every((c) => { for (let d = a; d <= b; d++) if (!Number.isFinite(table.cols[c][d - table.t0])) return false; return true; });

for (const [name, lat, lon, doy] of SITES) {
  const t0 = Date.now();
  const [power, soilRaw] = await Promise.all([fetchPower(lat, lon, dayNumber('1984-01-01'), dayNumber('2026-06-30')), fetchSoilGrids(lat, lon)]);
  const table = power.table, elev = power.elevation ?? 0;
  fillGaps(table);
  const wsAll = new WeatherSeries(table, lat, elev);
  const md = new Date((fromYMD(2001, 1, 1) + doy - 1) * 864e5);          // same day and month every year
  const sowOf = (y) => fromYMD(y, md.getUTCMonth() + 1, md.getUTCDate());
  for (const model of MODELS) {
    const emu = emus[model], card = emu.card, n = scenarioDays(card);
    const soil = prepareSoil(soilRaw.layers, card, lat).features;
    const pop = card.cultivar.includes('population') ? { population: card.population_default ?? 30 } : {};
    // cultivar of the crop model runs (benchmark/hindcast_sims.py) when available, so the emulator and the
    // crop models receive the same inputs; otherwise the app defaults
    const given = CULTIVARS?.[name]?.[emu.family];
    const cultivar = given ? Object.fromEntries(card.cultivar.map((k) => [k, given[k]]))
      : emu.family === 'dssat'
        ? { ...dssatCultivar(card, typicalMg(card, lat)), ...pop }
        : { ...aquacropCultivar(card, { ws: wsAll, sowingDoy: doy, cycleDays: 120 }), ...pop };
    if (given && card.cultivar.some((k) => !Number.isFinite(cultivar[k]))) throw new Error(`cultivar of ${name} misses ${card.cultivar}`);
    // every year whose season (30 days before sowing to n days after) is complete
    const all = [];
    for (let y = 1984; y <= 2025; y++) { const s = sowOf(y); if (complete(table, s - 30, s + n)) all.push({ year: y, s }); }
    const records = [], index = [];
    for (const Y of YEARS) {
      const tgt = all.find((a) => a.year === Y);
      if (!tgt) continue;
      const sowing = tgt.s;
      const analogs = all.filter((a) => a.year !== Y).map((a) => ({ year: a.year, shift: sowing - a.s }));
      // reference: the season with its own complete weather
      for (const irrigated of [false, true]) {
        records.push(emu.inputs(scenarioSeries(table, lat, elev, sowing, sowing + n, 0, n), soil, [{ sowing, cultivar, irrigated, co2: NaN }])[0]);
        index.push({ Y, das: -1, analog: Y, irrigated, rank: 0, dist: 0 });
      }
      for (const das of DAS) {
        const known = sowing + das;
        const ranked = similarYears(table, sowing, known, analogs);
        const rank = new Map(ranked.map((a, i) => [a.year, [i + 1, a.dist]]));
        for (const a of analogs) {
          const ws = scenarioSeries(table, lat, elev, sowing, known, a.shift, n);
          const seasons = [false, true].map((irrigated) => ({ sowing, cultivar, irrigated, co2: NaN }));
          emu.inputs(ws, soil, seasons).forEach((rec, j) => {
            records.push(rec);
            const [r, d] = rank.get(a.year) ?? [NaN, NaN];
            index.push({ Y, das, analog: a.year, irrigated: seasons[j].irrigated, rank: r, dist: d });
          });
        }
      }
    }
    const pred = await emu.predict(records), y = emu.keys.yield, mat = emu.keys.maturity;
    // group: (Y, das, analog) -> rf, p
    const ref = new Map(), sc = new Map();
    pred.forEach((r, i) => {
      const k = index[i], v = r.ok ? r.outputs[y] : NaN;
      if (k.das < 0) {
        const e = ref.get(k.Y) ?? {}; e[k.irrigated ? 'p' : 'rf'] = v; if (!k.irrigated) e.mat = r.ok ? r.outputs[mat] : NaN; ref.set(k.Y, e);
      } else {
        const key = `${k.Y}|${k.das}|${k.analog}`, e = sc.get(key) ?? { ...k }; e[k.irrigated ? 'p' : 'rf'] = v; sc.set(key, e);
      }
    });
    for (const e of sc.values()) {
      const t = ref.get(e.Y);
      rows.push([name, emu.family, e.Y, e.das, t.rf, t.p, t.mat, e.analog, e.rf, e.p, e.rank, Number.isFinite(e.dist) ? e.dist.toFixed(4) : ''].join(','));
    }
    console.log(name, model, 'targets', YEARS.length, 'analog years', all.length - 1, 'seasons', records.length, 's', ((Date.now() - t0) / 1000).toFixed(0));
  }
}
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, rows.join('\n') + '\n');
console.log('wrote', out, rows.length - 1, 'rows');
