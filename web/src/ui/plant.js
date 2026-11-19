// Animated soybean plant driven by the emulated daily curves (v3 emulators): height from the biomass,
// leaves from the leaf area (LAI or canopy cover), yellowing and wilting from the water stress and the
// senescence, flowers at flowering and pods filling with the grain. Illustrative drawing; the numbers
// shown beside it are the emulated values of each day.

import { fullDate } from '../engine/dates.js';
import { t } from '../i18n.js';
import { C } from './charts.js';
import { fmt, h } from './dom.js';

const NS = 'http://www.w3.org/2000/svg';
const W = 300, H = 260, GROUND = 228, X0 = 150;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const mix = (a, b, f) => {                       // hex colours
  const p = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
  const [x, y] = [p(a), p(b)];
  return `rgb(${x.map((v, i) => Math.round(v + (y[i] - v) * clamp(f))).join(',')})`;
};
const LEAF = '#3f8f2f', YELLOW = '#d6bf3a', BROWN = '#9b7a45', POD = '#5f9a3a', POD_DRY = '#b08a52';

function el(name, attrs = {}) {
  const e = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

/** SVG of the plant on one day. `p`: point of the curves; `ref`: season maxima and dates. */
function drawPlant(svg, p, ref) {
  svg.replaceChildren();
  const soil = el('rect', { x: -W, y: GROUND, width: 3 * W, height: H, fill: 'var(--soil, #8a6a4a)', opacity: 0.35 });
  svg.append(soil, el('line', { x1: -W, x2: 2 * W, y1: GROUND, y2: GROUND, stroke: 'currentColor', 'stroke-opacity': 0.35 }));
  const { das } = p;
  if (das < ref.emr) {                           // seed germinating
    const f = clamp(das / Math.max(ref.emr, 1));
    svg.append(el('ellipse', { cx: X0, cy: GROUND + 12, rx: 5, ry: 3.5, fill: BROWN }));
    if (f > 0.4) svg.append(el('path', { d: `M${X0},${GROUND + 10} q2,${-8 * f} 0,${-14 * f}`, stroke: LEAF, 'stroke-width': 2, fill: 'none' }));
    return;
  }
  const gb = clamp(p.biomass / Math.max(ref.bio, 1e-9));
  const leafFrac = clamp(p.leaf / Math.max(ref.leaf, 1e-9));
  const sen = das > ref.peak ? clamp(1 - leafFrac) : 0;            // share of the leaf area lost after the peak
  const height = 16 + 165 * gb ** 0.6;
  const nodes = Math.max(2, Math.round(2 + 11 * clamp(gb ** 0.5 * 1.15)));
  const fallen = Math.min(nodes - 1, Math.round(sen * nodes * 1.05));
  const yellow = clamp(0.85 * p.stress + 0.9 * sen);
  const leafColor = mix(LEAF, p.tau > 1.85 ? BROWN : YELLOW, yellow);
  const droop = 10 + 38 * p.stress;                                 // degrees below horizontal
  const stemW = 1.6 + 3 * gb;
  const top = GROUND - height;
  // stem (slight curve) and branches
  svg.append(el('path', { d: `M${X0},${GROUND} C${X0 - 4},${GROUND - height * 0.4} ${X0 + 4},${GROUND - height * 0.75} ${X0},${top}`,
    stroke: mix('#4f7d2c', BROWN, clamp((p.tau - 1.6) / 0.4)), 'stroke-width': stemW, fill: 'none', 'stroke-linecap': 'round' }));
  const size = 6 + 11 * leafFrac ** 0.7;
  const grainF = clamp(p.grain / Math.max(ref.grain, 1e-9));
  const flowering = das >= ref.flo - 2 && das <= ref.flo + 22;
  const pods = p.grain > 0 ? Math.round(3 + 16 * clamp(grainF * 1.1)) : 0;
  let podLeft = pods;
  for (let i = 0; i < nodes; i++) {
    const y = GROUND - height * ((i + 1) / (nodes + 0.4));
    const side = i % 2 ? 1 : -1;
    // petioles: long and open low on the plant, shorter and more upright near the top (bushy soybean)
    const low = 1 - i / nodes;
    const len = (16 + 46 * low) * (0.45 + 0.55 * leafFrac ** 0.5) * (0.55 + 0.45 * gb);
    const ang = ((35 + 40 * low + droop * 0.6) * Math.PI) / 180;      // from vertical
    const ex = X0 + side * len * Math.sin(ang), ey = y - len * Math.cos(ang) * 0.55;
    if (i >= fallen) {                         // petiole + trifoliate leaf
      svg.append(el('path', { d: `M${X0},${y} Q${X0 + side * len * 0.35},${y - len * 0.45} ${ex},${ey}`, stroke: leafColor, 'stroke-width': 1.3, fill: 'none' }));
      const s = size * (0.75 + 0.25 * (i / nodes)) * (1 - 0.35 * p.stress);
      for (const [dx, dy, r] of [[0, -0.15, 0], [-0.75, 0.35, -40], [0.75, 0.35, 40]]) {
        svg.append(el('ellipse', { cx: ex + side * dx * s * 0.9, cy: ey + dy * s, rx: s * 0.42, ry: s * 0.75 * (1 - 0.25 * p.stress),
          transform: `rotate(${side * (r + droop * 0.6)} ${ex + side * dx * s * 0.9} ${ey + dy * s})`, fill: leafColor, 'fill-opacity': 0.92 }));
      }
    } else {                                    // fallen leaf on the ground
      svg.append(el('ellipse', { cx: X0 + side * (18 + 9 * i), cy: GROUND + 4, rx: 5, ry: 2.2, fill: BROWN, 'fill-opacity': 0.6 }));
    }
    if (flowering && i >= nodes * 0.3) {
      svg.append(el('circle', { cx: X0 + side * 4, cy: y - 2, r: 2.4, fill: '#9b6fd0' }));
    }
    if (podLeft > 0 && i >= Math.floor(nodes * 0.25)) {   // pods in the axils
      const k = Math.min(podLeft, 2);
      for (let j = 0; j < k; j++) {             // pods hang from the axil, on both sides of the stem
        const pl = 6 + 10 * grainF, sd = j ? -side : side, px = X0 + sd * (3 + 2 * j);
        svg.append(el('path', { d: `M${px},${y + 1} q${sd * 5},${pl * 0.45} ${sd * 3},${pl}`, stroke: mix(POD, POD_DRY, clamp((p.tau - 1.55) / 0.45)),
          'stroke-width': 3.2 + 1.8 * grainF, fill: 'none', 'stroke-linecap': 'round' }));
      }
      podLeft -= k;
    }
  }
}

/** Card with the animated plant. `c`: curves of the season (season.js `curves`, emulated); `main`: the season row. */
export function plantCard(ctx, c, main) {
  const { emu } = ctx, dssat = emu.family === 'dssat', m = emu.meta, k = emu.keys;
  const pts = c.pts, last = pts.length - 1;
  const ref = { emr: c.emr, flo: c.flo, mat: c.mat, peak: c.peak, bio: Math.max(...pts.map((p) => p.bio)), leaf: Math.max(...pts.map((p) => p.canopy)),
    grain: Math.max(...pts.map((p) => p.grain)) };
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', class: 'plant-svg' });
  const slider = h('input', { type: 'range', min: 0, max: last, step: 1, value: Math.round(c.flo), 'aria-label': t('Day after sowing', 'Dia após a semeadura') });
  const play = h('button.secondary', { type: 'button' }, t('▶ Play', '▶ Animar'));
  const speed = h('select', { 'aria-label': t('Speed', 'Velocidade') }, [['1', '1×'], ['2', '2×'], ['4', '4×']].map(([v, l]) => h('option', { value: v }, l)));
  const info = h('div.plant-info');
  const stressBar = h('div.plant-bar', h('i'));
  const stage = (d) => (d < c.emr ? t('Sowing → emergence', 'Semeadura → emergência') : d < c.flo ? t('Vegetative', 'Vegetativo')
    : d < c.flo + 0.35 * (c.mat - c.flo) ? t('Flowering and pod set', 'Floração e formação de vagens') : d < c.mat ? t('Grain filling', 'Enchimento de grãos') : t('Maturity', 'Maturidade'));
  const leafLabel = dssat ? t('Leaf area index', 'Índice de área foliar') : t('Canopy cover', 'Cobertura do dossel');
  const leafUnit = dssat ? 'm²/m²' : '%';
  const show = (d) => {
    const p = pts[d];
    drawPlant(svg, { das: p.das, tau: p.tau ?? 0, leaf: p.canopy, biomass: p.bio, grain: p.grain, stress: p.stress ?? 0 }, ref);
    const sv = p.stress ?? 0;
    stressBar.firstChild.style.width = `${Math.round(100 * sv)}%`;
    stressBar.firstChild.style.background = sv < 0.2 ? C.aqua : sv < 0.5 ? C.yellow : C.red;
    info.replaceChildren(
      h('div.plant-day', h('strong', `${t('Day', 'Dia')} ${p.das}`), ' · ', fullDate(main.sowing + p.das)),
      h('div.plant-stage', stage(p.das)),
      h('dl',
        h('dt', leafLabel), h('dd', `${fmt(p.canopy, dssat ? 2 : 0)} ${leafUnit}`),
        h('dt', t('Above-ground biomass', 'Biomassa aérea')), h('dd', `${fmt(p.bio, 2)} ${m[k.biomass].unit}`),
        h('dt', t('Grain', 'Grãos')), h('dd', `${fmt(p.grain, 2)} ${m[k.yield].unit}`),
        h('dt', t('Water stress', 'Estresse hídrico')), h('dd', `${fmt(100 * sv, 0)} %`, stressBar)));
  };
  let timer = null, acc = 0, prev = 0;
  const stop = () => { if (timer) cancelAnimationFrame(timer); timer = null; play.textContent = t('▶ Play', '▶ Animar'); };
  const step = (now) => {
    if (!card.isConnected) { stop(); return; }    // the tab was redrawn
    acc += ((now - prev) / 1000) * 12 * +speed.value; prev = now;   // ~12 days per second at 1×
    if (acc >= 1) {
      const d = Math.min(last, +slider.value + Math.floor(acc)); acc %= 1;
      slider.value = d; show(d);
      if (d >= last) { stop(); return; }
    }
    timer = requestAnimationFrame(step);
  };
  play.addEventListener('click', () => {
    if (timer) { stop(); return; }
    if (+slider.value >= last) slider.value = 0;
    play.textContent = t('❚❚ Pause', '❚❚ Pausar'); prev = performance.now(); acc = 0; timer = requestAnimationFrame(step);
  });
  slider.addEventListener('input', () => { stop(); show(+slider.value); });
  show(+slider.value);
  const card = h('section.card.plant-card',
    h('h2', t('The plant through the season', 'A planta ao longo da safra')),
    h('p.hint', t('Drawn from the emulated daily curves: height follows the biomass, the leaves the leaf area, yellowing and wilting the water stress and the senescence, the pods the grain. The drawing is illustrative; the numbers are the emulated values of the day.',
      'Desenhada a partir das curvas diárias emuladas: a altura segue a biomassa, as folhas a área foliar, o amarelecimento e a murcha o estresse hídrico e a senescência, as vagens os grãos. O desenho é ilustrativo; os números são os valores emulados do dia.')),
    h('div.plant-wrap', h('div.plant-stage-box', svg), info),
    h('div.plant-controls', play, slider, speed));
  return card;
}
