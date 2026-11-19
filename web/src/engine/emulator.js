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
  'aquacrop-soybean-v3': 'AquaCrop soybean',
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
      const tr = this.card.trajectory;
      if (tr) {                                   // v3: curve shapes in phenological time (second output)
        const z = result[tr.output].data, q = tr.targets.length;
        part.forEach((r, i) => { r.shapes = Array.from(z.subarray(i * q, (i + 1) * q)); });
      }
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

  /** True when the network also predicts the daily curves (v3). */
  get hasCurves() { return !!this.card.trajectory; }

  /** v3: daily curves of a predicted season, {pts: [{das, tau, leaf, biomass, grain, stress}], emr, flo, mat},
   * from sowing to maturity (cropemu Prediction.curves): emulated shapes in phenological time
   * (0 emergence, 1 flowering, 2 maturity) times the emulated season outputs, placed on days by the
   * emulated dates. Leaf: LAI (DSSAT) or canopy cover % (AquaCrop); biomass and grain in the display
   * unit; stress 0 none to 1 full. Null for a v2 emulator or when the dates are not predicted. */
  curves(row) {
    const tr = this.card.trajectory;
    if (!tr || !row?.shapes) return null;
    const o = row.outputs, g = tr.grid, n = g.length;
    const e = o[tr.dates.emergence], a = o[tr.dates.flowering], m = o[tr.dates.maturity];
    if (![e, a, m].every(Number.isFinite) || !(e < a && a < m)) return null;
    const interp = (x, ys) => {
      if (x <= g[0]) return ys[0];
      if (x >= g[n - 1]) return ys[n - 1];
      let j = 1; while (g[j] < x) j++;
      return ys[j - 1] + (ys[j] - ys[j - 1]) * (x - g[j - 1]) / (g[j] - g[j - 1]);
    };
    const names = Object.keys(tr.curves);
    const shape = Object.fromEntries(names.map((k, i) => [k, row.shapes.slice(i * n, (i + 1) * n).map((v) => Math.max(v, 0))]));
    const stress = row.shapes.slice(names.length * n).map((v) => Math.min(1, Math.max(0, v)));
    const scale = Object.fromEntries(names.map((k) => {
      const c = tr.curves[k].scale;
      return [k, Math.max(o[c], 0) * (k === 'leaf' ? 1 : this.meta[c]?.scale ?? 1)];
    }));
    const pts = [];
    for (let d = 0; d <= Math.ceil(m); d++) {
      const tau = d <= a ? (d - e) / Math.max(a - e, 1) : 1 + (d - a) / Math.max(m - a, 1);
      const p = { das: d, tau };
      for (const k of names) p[k] = tau < 0 ? 0 : interp(tau, shape[k]) * scale[k];
      let j = 0; while (j < n - 2 && g[j + 1] <= tau) j++;
      p.stress = tau < 0 ? 0 : stress[j];
      pts.push(p);
    }
    return { pts, emr: e, flo: a, mat: m };
  }

  /** Value of an output in the display unit. */
  value(row, name) { return row.outputs[name] * this.meta[name].scale; }
}
