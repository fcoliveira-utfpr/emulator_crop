// Emulator inputs of one season (cropemu.features.season_inputs) and the cultivars of an emulator.

import { dayOfYear } from './dates.js';
import { daylength } from './weather.js';

export const WINDOWS = [[-30, 0], [0, 30], [30, 60], [60, 90], [90, 130]];
const VARIABLES = ['tmax', 'tmin', 'srad', 'rain', 'vpd', 'dayl', 'hot32', 'hot35'];

/** Thermal requirements of the AquaCrop soybean (FAO SoybeanGDD scaled to gdd_maturity). */
function aquacropThermal(cultivar) {
  const f = cultivar.gdd_maturity / 2700;
  return [{ td_emergence: 200, td_flowering: 1500 * f, td_senescence: 2200 * f, td_maturity: cultivar.gdd_maturity }, 5, 30];
}
const THERMAL = { aquacrop_soybean: aquacropThermal };

/** Days of weather needed after sowing by an emulator. */
export const daysAfter = (card) => (card.thermal ? 600 : 130);

/** Every input of one season; `null` when the weather does not cover the season windows.
 * `ws`: WeatherSeries; `soil`: soil features; `sowing`: day number. */
export function seasonInputs(card, ws, soil, sowing, cultivar, { irrigated = false, co2, dt = 0, rainFactor = 1 } = {}) {
  if (!ws.covers(sowing, WINDOWS[0][0], WINDOWS.at(-1)[1])) return null;
  const rec = { lat: ws.lat, abs_lat: Math.abs(ws.lat), elev: ws.elev, ...soil };
  for (const [a, b] of WINDOWS) {
    const w = ws.window(sowing, a, b, dt, rainFactor);
    for (const v of VARIABLES) rec[`${v}_${a}_${b}`] = w[v];
  }
  if (card.water_balance ?? true) {
    const s0 = WINDOWS[0][0], s1 = WINDOWS.at(-1)[1];
    const { eto, stress } = ws.bucketStress(sowing, soil.paw_mm, card.initial_water ?? 0.5, s0, s1, dt, rainFactor);
    for (const [a, b] of WINDOWS) {
      let e = 0, s = 0;
      for (let k = a - s0; k < b - s0; k++) { e += eto[k]; s += stress[k]; }
      rec[`eto_${a}_${b}`] = e; rec[`wstr_${a}_${b}`] = s / (b - a);
    }
  }
  const doy = dayOfYear(sowing);
  rec.dayl_sowing = daylength(ws.lat, doy);
  rec.sowing_sin = Math.sin(2 * Math.PI * doy / 365.25);
  rec.sowing_cos = Math.cos(2 * Math.PI * doy / 365.25);
  for (const k of card.cultivar) rec[k] = Number(cultivar[k]);
  rec.water = irrigated ? 0 : 1;
  rec.co2 = co2;
  if (card.thermal) {
    const [req, tbase, tupper] = THERMAL[card.thermal](cultivar);
    Object.assign(rec, ws.thermalDays(sowing, req, tbase, tupper, dt));
  }
  return rec;
}

// ------------------------------------------------------------ cultivars
const interp = (x, xs, ys) => {
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i++) if (x <= xs[i]) return ys[i - 1] + (x - xs[i - 1]) * (ys[i] - ys[i - 1]) / (xs[i] - xs[i - 1]);
  return ys.at(-1);
};

/** Typical soybean maturity group at a latitude (centre of the training design). */
export const typicalMg = (card, lat) => interp(Math.abs(lat), card.mg_by_lat.map((p) => p[0]), card.mg_by_lat.map((p) => p[1]));

/** DSSAT: default coefficients of a maturity group (CROPGRO-Soybean cultivar file). */
export function dssatCultivar(card, mg) {
  const t = card.cultivar_by_mg;
  return Object.fromEntries(card.cultivar.map((k) => [k, k === 'mg' ? Number(mg) : interp(mg, t.mg, t[k])]));
}

/** DSSAT: maturity group whose default critical short day length is `csdl`. */
export function mgFromCsdl(card, csdl) {
  const t = card.cultivar_by_mg;
  return interp(-csdl, t.CSDL.map((v) => -v), t.mg);
}

/** AquaCrop: middle of the training range of the crop parameters; the cycle `gdd_maturity`
 * is given or computed from the weather (mean GDD of `cycleDays` days after the sowing day of
 * year), scaled by the cycle factor (+12.5 % per MG above the typical MG of the latitude). */
export function aquacropCultivar(card, { ws, sowingDoy, cycleDays = 120, mg = null, lat = null, gddMaturity = null, cycleFactor = null }) {
  const out = { ...card.cultivar_defaults };
  if (mg != null && lat != null) out.cycle_factor = 1 + 0.125 * Math.min(2, Math.max(-2, mg - typicalMg(card, lat)));
  if (cycleFactor != null) out.cycle_factor = cycleFactor;
  out.gdd_maturity = gddMaturity ?? ws.seasonGdd(sowingDoy, cycleDays) * out.cycle_factor;
  return Object.fromEntries(card.cultivar.map((k) => [k, out[k]]));
}

/** Each cultivar parameter against its training range. */
export function cultivarDomain(card, cultivar) {
  return card.cultivar.map((k) => {
    const d = card.domain[k], v = cultivar[k];
    const status = v < d.min || v > d.max ? 'fora' : v < d.q005 || v > d.q995 ? 'raro' : 'ok';
    return { parameter: k, value: v, ...d, status };
  });
}
