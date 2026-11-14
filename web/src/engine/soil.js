// Soil hydraulics (cropemu.soil.ptf) and soil features of a profile (cropemu.features.soil_features).

const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));
function saxtonRawls(layer) {
  const S = layer.sand / 100, C = layer.clay / 100, om = Math.min(layer.soc * 1.724, 8);
  const t1500 = -0.024*S + 0.487*C + 0.006*om + 0.005*S*om - 0.013*C*om + 0.068*S*C + 0.031;
  const th1500 = t1500 + 0.14*t1500 - 0.02;
  const t33 = -0.251*S + 0.195*C + 0.011*om + 0.006*S*om - 0.027*C*om + 0.452*S*C + 0.299;
  let th33 = t33 + 1.283*t33**2 - 0.374*t33 - 0.015;
  const ts33 = 0.278*S + 0.034*C + 0.022*om - 0.018*S*om - 0.027*C*om - 0.584*S*C + 0.078;
  let thS = th33 + ts33 + 0.636*ts33 - 0.107 - 0.097*S + 0.043;
  if (Number.isFinite(layer.bdod)) { const densitySat = 1 - layer.bdod / 2.65; th33 -= 0.2 * (thS - densitySat); thS = densitySat; }
  const B = (Math.log(1500) - Math.log(33)) / (Math.log(th33) - Math.log(th1500)), lambda = 1 / B;
  return { ll: th1500, dul: th33, sat: thS, ksat: 1930 * Math.max(thS - th33, 1e-6) ** (3 - lambda) / 10 };
}

function hydraulics(layer, lat, method = 'hybrid') {
  const sr = saxtonRawls(layer);
  let ll = sr.ll, dul = sr.dul;
  if (method === 'soilgrids' && Number.isFinite(layer.wv1500) && Number.isFinite(layer.wv0033)) {
    ll = layer.wv1500; dul = layer.wv0033;
  } else if (method === 'reichert' || (method === 'hybrid' && Math.abs(lat) < 40)) {
    const weight = method === 'reichert' ? 1 : clamp((40 - Math.abs(lat)) / 10, 0, 1);
    const silt = Number.isFinite(layer.silt) ? layer.silt : 100 - layer.sand - layer.clay;
    const C = layer.clay / 100, CS = (layer.clay + silt) / 100, om = Math.min(layer.soc * 1.724, 10) / 100, bd = layer.bdod;
    const reLL = (-0.04 + 0.15*C + 0.17*CS + 0.91*om + 0.026*bd) * bd;
    const reDul = (0.268 + 0.05*C + 0.24*CS + 0.85*om - 0.127*bd) * bd;
    ll = weight * reLL + (1 - weight) * ll; dul = weight * reDul + (1 - weight) * dul;
  }
  ll = clamp(ll, 0.01, 0.6); dul = Math.max(dul, ll + 0.02);
  return { ...layer, ll, dul, sat: Math.max(sr.sat, dul + 0.02), ksat: sr.ksat };
}

/** Profile as in training (Emulator.training_soil): cut at the training depth (2 m) and with the
 * water retention of the training method unless measured `ll`/`dul` are given (measured values
 * win where present). Returns the layers (with `measured` flags) and the soil features. */
export function prepareSoil(profile, card, lat) {
  const depth = card.domain?.depth_cm?.min;
  let layers = profile.map((x) => ({ ...x }));
  if (Number.isFinite(depth) && layers.at(-1)?.bottom > depth) {
    layers = layers.filter((x) => x.top < depth).map((x) => ({ ...x, bottom: Math.min(x.bottom, depth) }));
  }
  const measured = layers.every((x) => Number.isFinite(x.ll) && Number.isFinite(x.dul));
  layers = layers.map((x) => {
    if (measured) return { ...x, measured: true };
    const estimated = hydraulics(x, lat, card.hydraulics), out = { ...estimated, measured: false };
    for (const c of ['ll', 'dul', 'sat', 'ksat']) if (Number.isFinite(x[c])) out[c] = x[c];
    out.dul = Math.max(out.dul, out.ll + 0.02);
    return out;
  });
  return { layers, features: soilFeatures(layers), measured };
}

export function soilFeatures(layers) {
  const thickness = layers.map((x) => x.bottom - x.top), paw = layers.map((x, i) => (x.dul - x.ll) * thickness[i] * 10);
  const top = layers.map((x) => Math.max(0, Math.min(x.bottom, 30) - x.top));
  const weighted = (name) => layers.reduce((sum, x, i) => sum + (x[name] ?? 0) * top[i], 0) / top.reduce((a, b) => a + b, 0);
  return { paw_mm: paw.reduce((a, b) => a + b, 0), paw30_mm: paw.reduce((sum, p, i) => sum + p * top[i] / thickness[i], 0),
    clay30: weighted('clay'), sand30: weighted('sand'), soc30: weighted('soc'), bdod30: weighted('bdod'), depth_cm: Math.max(...layers.map((x) => x.bottom)) };
}

