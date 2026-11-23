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
