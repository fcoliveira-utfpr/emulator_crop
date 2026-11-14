// Chart helpers on Observable Plot: one look for every figure (recessive grid, thin marks,
// fixed categorical order, hover tips), and the card that holds a figure.

import * as Plot from '@observablehq/plot';
import { h } from './dom.js';

export { Plot };

/** Categorical slots, fixed order (validated palette; same order as the example notebooks). */
export const C = { blue: '#2a78d6', orange: '#eb6834', aqua: '#1baf7a', yellow: '#eda100', magenta: '#e87ba4', green: '#008300', violet: '#6250d6', red: '#e34948', gray: '#8a8a85', rain: '#86b6ef' };
export const SERIES = [C.blue, C.orange, C.aqua, C.yellow, C.magenta, C.green, C.violet, C.red];

/** A figure card: title, optional note, chart area and legend. Returns {card, body}. */
export function figure(title, note, { wide = false, legend = null } = {}) {
  const body = h('div.chart');
  const card = h(`figure.fig${wide ? '.wide' : ''}`, h('figcaption', h('h3', title), note ? h('p', note) : null),
    legend ? h('div.legend', legend.map(([label, color, kind = 'line']) => h('span', h(`i.key.${kind.replaceAll(" ", ".")}`, { style: { '--c': color } }), label))) : null, body);
  return { card, body };
}

const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const nf = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 });
/** Default tick labels in Portuguese: dates as months (year on January), numbers with pt-BR separators. */
export const ptTick = (v) => {
  if (v instanceof Date) {
    const m = v.getUTCMonth(), d = v.getUTCDate();
    return d === 1 || d <= 7 ? (m === 0 ? `jan\n${v.getUTCFullYear()}` : MONTHS[m]) : `${d} ${MONTHS[m]}`;
  }
  return typeof v === 'number' ? nf.format(v) : v;
};

/** Render a Plot into `el`, sized to its width. */
export function draw(el, options) {
  const width = Math.max(280, el.clientWidth || el.parentElement?.clientWidth || 600);
  const fig = Plot.plot({
    width, height: options.height ?? Math.round(Math.min(340, Math.max(220, width * 0.42))),
    marginLeft: 52, marginBottom: 36, marginRight: 14, inset: 4,
    style: { fontFamily: 'inherit', fontSize: '11.5px', background: 'transparent', overflow: 'visible' },
    ...options,
    x: { labelAnchor: 'center', labelArrow: 'none', tickFormat: ptTick, ...options.x },
    y: { grid: true, labelArrow: 'none', tickFormat: ptTick, ...options.y },
  });
  el.replaceChildren(fig);
  return fig;
}

/** Default hover tip style. */
export const tip = (channels = {}, extra = {}) => ({ tip: { fill: 'var(--surface)', stroke: 'var(--line)', ...extra }, channels });
