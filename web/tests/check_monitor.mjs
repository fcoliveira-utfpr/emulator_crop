// Crop monitoring engine on NASA POWER + Open-Meteo for a real site (network): node tests/check_monitor.mjs [lat lon sowing]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Emulator } from '../src/engine/emulator.js';
import { dayNumber, isoDate, today } from '../src/engine/dates.js';
import { analogYears, lastContinuous, monitor, summary } from '../src/engine/monitor.js';
import { fetchOpenMeteo } from '../src/engine/openmeteo.js';
import { dssatCultivar, typicalMg } from '../src/engine/season.js';
import { prepareSoil } from '../src/engine/soil.js';
import { fetchSoilGrids } from '../src/engine/soilgrids.js';
import { combine, fetchPower, fillGaps, POWER_FIRST_DAY } from '../src/engine/weather.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const fetcher = async (p) => { const b = fs.readFileSync(path.join(here, '../public', p)); return { json: async () => JSON.parse(b), arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.length) }; };
const [lat = -23.19, lon = -51.18, sow = '2026-10-20'] = process.argv.slice(2);
const sowing = dayNumber(sow);
const [power, om, soil, emu] = await Promise.all([fetchPower(lat, lon, POWER_FIRST_DAY, today()), fetchOpenMeteo(lat, lon), fetchSoilGrids(lat, lon), Emulator.load('dssat-soybean-v3', '', fetcher)]);
const { table } = combine(power.table, om.table);
fillGaps(table);
const observedEnd = Math.min(lastContinuous(table, sowing - 30), today() - 1), known = lastContinuous(table, sowing - 30);
const analogs = analogYears(table, sowing, emu.card);
console.log('power last', isoDate(lastContinuous(power.table, sowing - 30)), 'observed', isoDate(observedEnd), 'known', isoDate(known), 'analogs', analogs.length);
const sf = prepareSoil(soil.layers, emu.card, +lat).features;
const t0 = performance.now();
const res = await monitor(emu, table, { lat: +lat, elev: power.elevation ?? 0, soil: sf, sowing, cultivar: dssatCultivar(emu.card, typicalMg(emu.card, +lat)), observedEnd, known, analogs });
console.log('ms', (performance.now() - t0).toFixed(0), 'seasons', res.length * analogs.length * 2);
for (const cp of res) {
  const rf = summary(cp.rainfed.map((r) => r.outputs.HWAM)), ir = summary(cp.potential.map((r) => r.outputs.HWAM));
  console.log(isoDate(cp.day), cp.forecast ? 'F' : ' ', Math.round(rf.p10), Math.round(rf.p50), Math.round(rf.p90), 'irr', Math.round(ir.p50), 'ok', cp.rainfed.filter((r) => r.ok).length);
}

// most similar years and the yield built along the cycle (% of the potential)
const { similarYears, relativeCurves } = await import('../src/engine/monitor.js');
const sim = similarYears(table, sowing, observedEnd, analogs);
console.log('most similar years', sim.slice(0, 5).map((a) => `${a.year} (${a.dist.toFixed(2)})`).join(', '), '| least', sim.at(-1).year, sim.at(-1).dist.toFixed(2));
const same = similarYears(table, sowing, observedEnd, analogs);
if (!(same.length === analogs.length)) throw new Error('similarYears dropped analogs');
const last = res.at(-1), rc = relativeCurves(emu, last, 140);
const at = (d, key) => summary(rc[key].map((s) => s[d]));
console.log('relative curves', rc.years.length, 'scenarios');
for (const d of [0, 30, 60, 90, 120, 140]) console.log(`  DAS ${d}: rainfed ${at(d, 'rainfed').p50.toFixed(0)}% (${at(d, 'rainfed').p10.toFixed(0)}-${at(d, 'rainfed').p90.toFixed(0)}) potential ${at(d, 'potential').p50.toFixed(0)}% gap ${at(d, 'gap').p50.toFixed(0)}%`);
const fin = rc.rainfed.map((s, i) => s[140]), yRf = last.rainfed.filter((r) => rc.years.includes(r.year)).map((r) => r.outputs.HWAM), yPt = last.potential.filter((r) => rc.years.includes(r.year)).map((r) => r.outputs.HWAM);
const err = Math.max(...fin.map((v, i) => Math.abs(v - 100 * Math.min(yRf[i] / yPt[i], 1))));
console.log('max |final % - yield ratio| =', err.toFixed(2), 'points');
if (err > 0.5) throw new Error('relative curves do not end at the season yields');
// the ranking in plain numbers: rain since 30 days before sowing and mean Tmax, this season vs. top and bottom years
const stats = (shift) => { let r = 0, tx = 0, n = 0; for (let d = sowing - 30; d <= observedEnd; d++) { const i = d - shift - table.t0; r += table.cols.rain[i]; tx += table.cols.tmax[i]; n++; } return `rain ${r.toFixed(0)} mm, Tmax ${(tx / n).toFixed(1)}`; };
console.log('this season:', stats(0));
for (const a of [...sim.slice(0, 3), sim.at(-1)]) console.log(`  ${a.year} (${a.dist.toFixed(2)}):`, stats(a.shift));

// projection of the expected yield after the last known day (paths = past years)
const { projection } = await import('../src/engine/monitor.js');
const matMean = last.rainfed.reduce((a, r) => a + r.outputs.MDAT_dap, 0) / last.rainfed.length;
const tp = performance.now();
const pj = await projection(emu, table, { lat: +lat, elev: power.elevation ?? 0, soil: sf, sowing, cultivar: dssatCultivar(emu.card, typicalMg(emu.card, +lat)), known, analogs, maturity: matMean });
console.log('projection', pj.days.length, 'dates x', pj.paths.length, 'paths in', (performance.now() - tp).toFixed(0), 'ms');
const finals = Object.fromEntries(last.rainfed.map((r) => [r.year, r.outputs.HWAM]));
pj.days.forEach((d, j) => { const s = summary(pj.paths.map((p) => p.values[j])); console.log('  ', isoDate(d), Math.round(s.p10), Math.round(s.p50), Math.round(s.p90)); });
const sF = summary(Object.values(finals)); console.log('   maturity', Math.round(sF.p10), Math.round(sF.p50), Math.round(sF.p90));
const p0 = summary(last.rainfed.map((r) => r.outputs.HWAM)).p50, first = summary(pj.paths.map((p) => p.values[0])).p50;
if (Math.abs(first - p0) / p0 > 0.1) throw new Error('projection does not start near the current expectation');
