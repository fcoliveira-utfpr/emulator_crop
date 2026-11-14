// Pieces shared by the analysis tabs.

import { download, toCsv } from '../engine/io.js';
import { LEVELS } from '../engine/units.js';
import { h, auto } from './dom.js';

const GROUP_ORDER = ['produção', 'fenologia', 'água', 'estresses', 'eficiência', 'nitrogênio e carbono', 'clima do ciclo', 'outros'];

/** <select> of every output of the emulator, grouped; the key outputs first. */
export function variableSelect(ctx, onChange = (v) => ctx.setVariable(v)) {
  const { emu } = ctx, groups = {};
  for (const m of Object.values(emu.meta)) (groups[m.group] ??= []).push(m);
  const sel = h('select.variable', { 'aria-label': 'Variável analisada', onchange: (e) => onChange(e.target.value) },
    GROUP_ORDER.filter((g) => groups[g]).map((g) => h('optgroup', { label: g[0].toUpperCase() + g.slice(1) },
      groups[g].map((m) => h('option', { value: m.name }, `${m.label} (${m.unit})${m.level === 'not recommended' ? ' ⚠' : ''}`)))));
  sel.value = ctx.variable;
  return h('label.inline', h('span', 'Variável'), sel);
}

/** Panel header: title, lead text, controls and the CSV export. */
export function header(title, lead, controls = [], exportFn = null) {
  return h('header.panel-head',
    h('div.titles', h('h1', title), lead ? h('p.lead', lead) : null),
    h('div.controls', controls, exportFn ? h('button.secondary.export', { type: 'button', onclick: exportFn }, 'Baixar CSV') : null));
}

export const exporter = (name, rows, columns) => () => download(name, toCsv(rows, columns));

/** Level badge of an output. */
export function levelBadge(level) {
  const l = LEVELS[level] ?? LEVELS.unknown;
  return h('span.badge', { style: { '--c': l.color }, title: 'Nível de aceitação na validação por blocos espaciais de 5°' }, h('i'), l.label);
}

/** Warning when the analysed output is not reliable. */
export function levelNote(ctx, name) {
  const m = ctx.emu.meta[name];
  if (m.level === 'not recommended') return h('p.note.warn', `“${m.label}” tem nível de aceitação não recomendado na validação (R² ${auto(m.r2)}): use apenas como indicação grosseira.`);
  if (m.level === 'caution') return h('p.note', `“${m.label}” tem nível de aceitação “com cautela” na validação (RMSE ${auto(m.rmse * m.scale)} ${m.unit}).`);
  return null;
}

/** Domain flags of a set of predicted seasons. */
export function domainSummary(rows, what = 'safras') {
  const out = rows.filter((r) => r.outOfDomain?.length), rare = rows.filter((r) => !r.outOfDomain?.length && r.rare?.length), bad = rows.filter((r) => !r.ok);
  const items = [];
  if (bad.length) items.push(h('li.err', `${bad.length} ${what} sem cálculo: ${bad[0].reason}.`));
  if (out.length) {
    const names = [...new Set(out.flatMap((r) => r.outOfDomain))];
    items.push(h('li.err', `${out.length} ${what} com entradas fora do domínio de treino (${names.slice(0, 6).join(', ')}${names.length > 6 ? '…' : ''}): extrapolação, marcadas nos gráficos.`));
  }
  if (rare.length) {
    const names = [...new Set(rare.flatMap((r) => r.rare))];
    items.push(h('li.warn', `${rare.length} ${what} com entradas raras no treino (fora de 0,5–99,5 %: ${names.slice(0, 6).join(', ')}${names.length > 6 ? '…' : ''}).`));
  }
  return items.length ? h('ul.flags', items) : h('ul.flags', h('li.ok', rows.length === 1 ? 'Safra dentro do domínio de treino.' : `Todas as ${rows.length} ${what} dentro do domínio de treino.`));
}

/** Simple data table. `cols`: [[label, fn | key, align?]] */
export function table(rows, cols, cls = '') {
  return h(`div.table-wrap${cls}`, h('table.data',
    h('thead', h('tr', cols.map(([label, , align]) => h('th', { class: align ?? '' }, label)))),
    h('tbody', rows.map((r) => h('tr', cols.map(([, f, align]) => h('td', { class: align ?? '' }, typeof f === 'function' ? f(r) : r[f])))))));
}

export const grid = (...cards) => h('div.grid', cards);
