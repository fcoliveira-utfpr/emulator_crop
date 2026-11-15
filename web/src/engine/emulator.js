// An exported emulator in the browser: card.json + model.onnx run with ONNX Runtime Web (cropemu.emulator).

import * as ort from 'onnxruntime-web/wasm';
import { co2At } from './co2.js';
import { seasonInputs } from './season.js';
import { KEYS, outputMeta } from './units.js';
import { getLang, t } from '../i18n.js';

ort.env.wasm.numThreads = 1;              // no cross-origin isolation needed (GitHub Pages)
const BATCH = 2048;                       // rows per run (the v2 sequence input is 1809 floats per row)

export const EMULATORS = {
  'dssat-soybean-v2': 'DSSAT CROPGRO-Soybean',
  'aquacrop-soybean-v2': 'AquaCrop soybean',
};

export class Emulator {
  constructor(card, session) {
    this.card = card; this.session = session;
    this.family = String(card.model).toLowerCase().includes('aquacrop') ? 'aquacrop' : 'dssat';
    this.keys = KEYS[this.family];
    this.outputs = Object.keys(outputMeta(card, this.family));
    this.fixed = Object.fromEntries(card.inputs.filter((k) => card.domain[k]?.min === card.domain[k]?.max).map((k) => [k, card.domain[k].min]));
    this.lo = card.inputs.map((k) => card.domain[k].min); this.hi = card.inputs.map((k) => card.domain[k].max);
    this.qlo = card.inputs.map((k) => card.domain[k].q005); this.qhi = card.inputs.map((k) => card.domain[k].q995);
  }

  /** Output metadata in the current interface language. */
  get meta() {
    const lang = getLang();
    if (this._metaLang !== lang) { this._meta = outputMeta(this.card, this.family); this._metaLang = lang; }
    return this._meta;
  }

  static async load(name, base = import.meta.env?.BASE_URL ?? '/', fetcher = fetch) {
    const dir = `${base}models/${name}`;
    const card = await (await fetcher(`${dir}/card.json`)).json();
    const bytes = new Uint8Array(await (await fetcher(`${dir}/model.onnx`)).arrayBuffer());
    return new Emulator(card, await ort.InferenceSession.create(bytes, { executionProviders: ['wasm'] }));
  }

  /** Inputs of many seasons. `seasons`: [{sowing (day number), cultivar, irrigated, co2?, dt?, rainFactor?, ...tags}].
   * CO₂ defaults to Mauna Loa 60 days after sowing, as in training. */
  inputs(ws, soil, seasons) {
    return seasons.map((s) => {
      const co2 = Number.isFinite(s.co2) ? s.co2 : co2At(s.sowing + 60);
      const rec = seasonInputs(this.card, ws, soil, s.sowing, s.cultivar, { irrigated: s.irrigated, co2, dt: s.dt ?? 0, rainFactor: s.rainFactor ?? 1 });
      if (!rec) return rec;
      if (this.card.sequence) {                  // daily weather read by the convolutional network (v2)
        const seq = ws.sequence(s.sowing, soil.paw_mm, s.dt ?? 0, s.rainFactor ?? 1, this.card.initial_water ?? 0.5, this.card.sequence.days);
        Object.defineProperty(rec, 'sequence', { value: seq, enumerable: false });
      }
      return Object.assign(rec, this.fixed);
    });
  }

  /** Run the network on input records (null: not computable). Returns one row per record:
   * {ok, outputs: {name: value}, outOfDomain: [names], rare: [names]}. */
  async predict(records) {
    const n = this.card.inputs.length;
    const rows = records.map((rec) => {
      if (!rec) return { ok: false, outputs: {}, outOfDomain: [], rare: [], reason: t('not enough weather for the season', 'clima insuficiente para a safra') };
      const x = this.card.inputs.map((k) => rec[k]);
      const outOfDomain = [], rare = [];
      x.forEach((v, j) => {
        if (!Number.isFinite(v) || v < this.lo[j] || v > this.hi[j]) outOfDomain.push(this.card.inputs[j]);
        else if (v < this.qlo[j] || v > this.qhi[j]) rare.push(this.card.inputs[j]);
      });
      const ok = x.every(Number.isFinite) && (!this.card.sequence || !!rec.sequence);
      return { ok, x, seq: rec.sequence, outputs: {}, outOfDomain, rare, reason: ok ? null : t('incomplete inputs (missing weather)', 'entradas incompletas (falta clima)') };
    });
    const good = rows.filter((r) => r.ok);
    for (let k = 0; k < good.length; k += BATCH) {
      const part = good.slice(k, k + BATCH), data = new Float32Array(part.length * n);
      part.forEach((r, i) => data.set(r.x, i * n));
      const feeds = { [this.card.onnx.input]: new ort.Tensor('float32', data, [part.length, n]) };
      if (this.card.sequence) {
        const c = this.card.sequence.channels.length, d = this.card.sequence.days[1] - this.card.sequence.days[0] + 1;
        const sq = new Float32Array(part.length * c * d);
        part.forEach((r, i) => sq.set(r.seq, i * c * d));
        feeds[this.card.onnx.sequence_input] = new ort.Tensor('float32', sq, [part.length, c, d]);
      }
      const result = await this.session.run(feeds);
      const y = result[this.card.onnx.output].data, m = this.card.outputs.length;
      part.forEach((r, i) => { this.card.outputs.forEach((name, j) => { r.outputs[name] = y[i * m + j]; }); });
    }
    for (const r of rows) {
      if (!r.ok) { for (const name of this.outputs) r.outputs[name] = NaN; continue; }
      for (const [name, [num, den, f, floor]] of Object.entries(this.card.derived ?? {})) {
        r.outputs[name] = f * Math.max(r.outputs[num], 0) / Math.max(r.outputs[den], floor);
      }
      delete r.x; delete r.seq;
    }
    return rows;
  }

  /** Inputs + prediction of seasons; each result row keeps the season's fields. */
  async run(ws, soil, seasons) {
    const records = this.inputs(ws, soil, seasons);
    const rows = await this.predict(records);
    return rows.map((r, i) => ({ ...seasons[i], ...r, inputs: records[i] }));
  }

  /** Value of an output in the display unit. */
  value(row, name) { return row.outputs[name] * this.meta[name].scale; }
}
