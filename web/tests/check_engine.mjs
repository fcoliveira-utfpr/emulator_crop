// Compares the browser engine with the Python cropemu (tests/reference.json from make_reference.py).
// Run: node tests/check_engine.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Emulator } from '../src/engine/emulator.js';
import { readSoils, readWeather } from '../src/engine/io.js';
import { aquacropCultivar, dssatCultivar, typicalMg } from '../src/engine/season.js';
import { prepareSoil } from '../src/engine/soil.js';
import { fillGaps, WeatherSeries } from '../src/engine/weather.js';
import { dayNumber, dayOfYear } from '../src/engine/dates.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const data = path.join(here, '../../examples/data/your_data');
const ref = JSON.parse(fs.readFileSync(path.join(here, 'reference.json')));
const fetcher = async (p) => { const b = fs.readFileSync(path.join(here, '../public', p)); return { json: async () => JSON.parse(b), arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.length) }; };

const { table } = readWeather(fs.readFileSync(path.join(data, 'clima_A.csv'), 'utf8'));
fillGaps(table);
const ws = new WeatherSeries(table, ref.lat, ref.elev);
const profile = readSoils(fs.readFileSync(path.join(data, 'solo.csv'), 'utf8')).profiles[ref.farm];
let worstIn = 0, worstOut = 0, worstCult = 0, fails = 0;
const rel = (a, b) => Math.abs(a - b) / Math.max(Math.abs(b), 1e-3);
for (const name of ['dssat-soybean-v1', 'aquacrop-soybean-v1']) {
  const emu = await Emulator.load(name, '', fetcher);
  const soil = prepareSoil(profile, emu.card, ref.lat).features;
  const cases = ref.cases.filter((c) => c.model === name);
  // cultivars computed in JS against the Python ones
  for (const c of cases) {
    const mine = emu.family === 'dssat'
      ? dssatCultivar(emu.card, c.cultivar_name === 'lat' ? typicalMg(emu.card, ref.lat) : 7.0)
      : aquacropCultivar(emu.card, { ws, sowingDoy: dayOfYear(dayNumber('2003-11-15')), cycleDays: 120, ...(c.cultivar_name === 'mg' ? { mg: 8.5, lat: ref.lat } : {}) });
    for (const k of emu.card.cultivar) worstCult = Math.max(worstCult, rel(mine[k], c.cultivar[k]));
  }
  const rows = await emu.run(ws, soil, cases.map((c) => ({ sowing: dayNumber(c.sowing), cultivar: c.cultivar, irrigated: c.irrigated, dt: c.dt, rainFactor: c.rain_factor })));
  rows.forEach((r, i) => {
    const c = cases[i];
    for (const k of emu.card.inputs) {
      const e = rel(r.inputs[k], c.inputs[k]);
      if (e > 1e-3) { fails++; if (fails < 15) console.log('input', name, c.sowing, c.dt, c.rain_factor, k, r.inputs[k], c.inputs[k]); }
      worstIn = Math.max(worstIn, e);
    }
    for (const k of Object.keys(c.outputs)) {
      const e = Math.abs(r.outputs[k] - c.outputs[k]) / Math.max(Math.abs(c.outputs[k]), 1);
      if (e > 1e-3) { fails++; if (fails < 15) console.log('output', name, c.sowing, k, r.outputs[k], c.outputs[k]); }
      worstOut = Math.max(worstOut, e);
    }
  });
  console.log(name, cases.length, 'cases');
}
console.log({ worstCultivar: worstCult, worstInput: worstIn, worstOutput: worstOut, fails });
process.exit(fails ? 1 : 0);
