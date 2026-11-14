// Small DOM and formatting helpers.

import { locale } from '../i18n.js';

export const $ = (id) => document.getElementById(id);

/** h('div.card#id', {attrs}, ...children) */
export function h(tag, attrs = {}, ...children) {
  const [, name = 'div', rest = ''] = tag.match(/^([a-z0-9]+)?(.*)$/i);
  const el = document.createElement(name);
  for (const part of rest.match(/[.#][^.#]+/g) ?? []) part[0] === '.' ? el.classList.add(part.slice(1)) : (el.id = part.slice(1));
  if (attrs instanceof Node || typeof attrs !== 'object' || Array.isArray(attrs)) { children.unshift(attrs); attrs = {}; }
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'html') el.innerHTML = v;
    else if (k === 'style' && typeof v === 'object') for (const [p, x] of Object.entries(v)) p.startsWith('--') ? el.style.setProperty(p, x) : (el.style[p] = x);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat(Infinity)) if (c != null && c !== false) el.append(c instanceof Node ? c : String(c));
  return el;
}

const nf = new Map();
/** Number in the interface locale with `d` decimals ('—' when not finite). */
export function fmt(x, d = 1) {
  if (!Number.isFinite(x)) return '—';
  const k = `${locale()}:${d}`;
  if (!nf.has(k)) nf.set(k, new Intl.NumberFormat(locale(), { minimumFractionDigits: d, maximumFractionDigits: d }));
  return nf.get(k).format(x);
}
/** Sensible decimals for a value of this magnitude. */
export const auto = (x) => fmt(x, !Number.isFinite(x) ? 0 : Math.abs(x) >= 100 ? 0 : Math.abs(x) >= 10 ? 1 : Math.abs(x) >= 1 ? 2 : 3);

export function quantile(values, q) {
  const s = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!s.length) return NaN;
  const p = (s.length - 1) * q, i = Math.floor(p);
  return i + 1 < s.length ? s[i] + (p - i) * (s[i + 1] - s[i]) : s[i];
}
export const mean = (v) => { const s = v.filter(Number.isFinite); return s.length ? s.reduce((a, b) => a + b, 0) / s.length : NaN; };
export const sd = (v) => { const s = v.filter(Number.isFinite), m = mean(s); return s.length > 1 ? Math.sqrt(s.reduce((a, b) => a + (b - m) ** 2, 0) / (s.length - 1)) : NaN; };
export function corr(a, b) {
  const p = a.map((x, i) => [x, b[i]]).filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
  if (p.length < 3) return NaN;
  const mx = mean(p.map((q) => q[0])), my = mean(p.map((q) => q[1]));
  let sxy = 0, sxx = 0, syy = 0;
  for (const [x, y] of p) { sxy += (x - mx) * (y - my); sxx += (x - mx) ** 2; syy += (y - my) ** 2; }
  return sxy / Math.sqrt(sxx * syy);
}
/** Parse a list of numbers: "4.5, 5.5 6.5" or, with decimal commas, "4,5; 5,5; 6,5". */
export function numberList(s) {
  s = String(s).trim();
  const parts = s.includes(';') ? s.split(/\s*;\s*/).map((t) => t.replace(',', '.')) : s.split(/[\s,]+/);
  return parts.map(Number).filter((x, i) => parts[i] !== '' && Number.isFinite(x));
}
