// Times the browser engine on N seasons: node tests/time_engine.mjs [model] [N]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Emulator } from '../src/engine/emulator.js';
import { readSoils, readWeather } from '../src/engine/io.js';
import { aquacropCultivar, dssatCultivar, typicalMg } from '../src/engine/season.js';
import { prepareSoil } from '../src/engine/soil.js';
import { fillGaps, WeatherSeries } from '../src/engine/weather.js';
import { dayNumber } from '../src/engine/dates.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const data = path.join(here, '../../examples/data/your_data');
const fetcher = async (p) => { const b = fs.readFileSync(path.join(here, '../public', p)); return { json: async () => JSON.parse(b), arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.length) }; };
const [name = 'dssat-soybean-v3', n = '2000'] = process.argv.slice(2);
const { table } = readWeather(fs.readFileSync(path.join(data, 'clima_A.csv'), 'utf8'));
fillGaps(table);
const ws = new WeatherSeries(table, -23.3, 600);
const profile = readSoils(fs.readFileSync(path.join(data, 'solo.csv'), 'utf8')).profiles['Fazenda A'];
const emu = await Emulator.load(name, '', fetcher);
const soil = prepareSoil(profile, emu.card, -23.3).features;
const cultivar = emu.card.thermal ? aquacropCultivar(emu.card, { ws, sowingDoy: 245, mg: typicalMg(emu.card, -23.3), lat: -23.3 }) : dssatCultivar(emu.card, typicalMg(emu.card, -23.3));
const s0 = dayNumber('1990-09-01');
const recs = Array.from({ length: +n }, (_, i) => ({ sowing: s0 + (i % 9000), cultivar, irrigated: false, dt: 0, rainFactor: 1 }));
await emu.run(ws, soil, recs.slice(0, 50));
const t0 = performance.now();
const rows = await emu.run(ws, soil, recs);
const ms = performance.now() - t0;
console.log(name, rows.length, 'seasons', ms.toFixed(0), 'ms', (1000 * ms / rows.length).toFixed(0), 'µs/season');
