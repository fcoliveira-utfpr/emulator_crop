// Spreadsheets of the user (port of cropemu.io.tables: same column names, units and conversions),
// the templates shown in the page and CSV export.

import { tableFromRecords, SRC } from './weather.js';
import { getLang, t } from '../i18n.js';

const WEATHER = {
  srad: ['srad', 'rs', 'rad', 'radiation', 'solar_radiation', 'radiacao', 'radiacao_solar', 'rg'],
  tmax: ['tmax', 't_max', 'temp_max', 'tx', 'maximum_temperature', 'temperatura_maxima', 'tmaxima'],
  tmin: ['tmin', 't_min', 'temp_min', 'tn', 'minimum_temperature', 'temperatura_minima', 'tminima'],
  rain: ['rain', 'prec', 'precip', 'precipitation', 'prcp', 'rainfall', 'chuva', 'precipitacao', 'ppt'],
  rhum: ['rhum', 'rh', 'humidity', 'relative_humidity', 'umidade', 'umidade_relativa', 'ur'],
  wind: ['wind', 'u2', 'ws', 'wind_speed', 'vento', 'velocidade_do_vento'],
  dewp: ['dewp', 'tdew', 'td', 'dew_point', 'ponto_de_orvalho', 'orvalho'],
};
const DATE = { date: ['date', 'data', 'dia', 'day', 'datetime'] };
const YMD = { year: ['year', 'ano'], doy: ['doy', 'day_of_year', 'dia_juliano', 'dia_do_ano', 'jday'], month: ['month', 'mes'], day: ['day', 'dia'] };
const SOIL = {
  profile: ['profile', 'perfil', 'site', 'local', 'farm', 'fazenda', 'id', 'solo'],
  top: ['top', 'upper', 'depth_top', 'topo', 'prof_topo', 'profundidade_topo', 'prof_sup', 'de'],
  bottom: ['bottom', 'lower', 'depth', 'depth_bottom', 'base', 'prof_base', 'profundidade', 'profundidade_base', 'prof_inf', 'ate'],
  clay: ['clay', 'argila'], sand: ['sand', 'areia'], silt: ['silt', 'silte'],
  soc: ['soc', 'oc', 'organic_carbon', 'carbono', 'carbono_organico', 'c_org', 'cot'],
  om: ['om', 'som', 'organic_matter', 'materia_organica', 'mo'],
  bdod: ['bdod', 'bd', 'bulk_density', 'density', 'densidade', 'ds', 'densidade_do_solo'],
  ll: ['ll', 'wilting_point', 'wp1500', 'pmp', 'ponto_de_murcha', 'ponto_de_murcha_permanente'],
  dul: ['dul', 'field_capacity', 'fc', 'cc', 'capacidade_de_campo'],
  sat: ['sat', 'saturation', 'saturacao', 'porosidade', 'porosity'],
  ksat: ['ksat', 'saturated_conductivity', 'condutividade_saturada', 'k0'],
};

const key = (s) => String(s).normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
  .replace(/[([].*?[)\]]/g, ' ').replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');

function match(columns, aliases) {
  const out = {};
  for (const [std, names] of Object.entries(aliases)) {
    for (const c of columns) {
      if (Object.values(out).includes(c)) continue;
      const k = key(c);
      if (names.includes(k) || names.some((n) => n.length > 2 && k.startsWith(`${n}_`))) { out[std] = c; break; }
    }
  }
  return out;
}

/** Rows of a CSV (comma, semicolon or tab; decimal comma with semicolons). */
export function parseCsv(text) {
  text = text.replace(/^﻿/, '');
  const first = text.split(/\r?\n/, 1)[0] ?? '';
  const sep = (first.match(/;/g) || []).length > (first.match(/,/g) || []).length ? ';' : first.includes('\t') ? '\t' : ',';
  const rows = []; let row = [], value = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"' && quoted && text[i + 1] === '"') { value += '"'; i++; } else if (ch === '"') quoted = !quoted;
    else if (ch === sep && !quoted) { row.push(value); value = ''; } else if ((ch === '\n' || ch === '\r') && !quoted) {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      row.push(value); if (row.some((v) => v.trim())) rows.push(row); row = []; value = '';
    } else value += ch;
  }
  row.push(value); if (row.some((v) => v.trim())) rows.push(row);
  if (rows.length < 2) throw new Error(t('the spreadsheet needs a header and at least one row', 'a planilha precisa de um cabeçalho e pelo menos uma linha'));
  const headers = rows[0].map((h) => h.trim());
  return { headers, decimalComma: sep === ';', rows: rows.slice(1).map((cells) => Object.fromEntries(headers.map((h, i) => [h, (cells[i] ?? '').trim()]))) };
}

const num = (v, comma) => {
  if (v == null || v === '') return NaN;
  let s = String(v).trim();
  s = comma ? s.replace(/\./g, '').replace(',', '.') : s.replace(',', '.');
  const n = Number(s);
  return Number.isFinite(n) ? n : NaN;
};
const median = (xs) => { const s = xs.filter(Number.isFinite).sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : NaN; };
const max = (xs) => Math.max(...xs.filter(Number.isFinite));

function parseDate(s, dayFirst) {
  s = String(s).trim();
  let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (m) return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`;
  m = s.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/);
  if (m) { const [d, mo] = dayFirst ? [m[1], m[2]] : [m[2], m[1]]; return `${m[3]}-${mo.padStart(2, '0')}-${d.padStart(2, '0')}`; }
  return null;
}

/** Daily weather from a CSV: `{table, rows, conversions, first, last}`. */
export function readWeather(text) {
  const { headers, rows, decimalComma } = parseCsv(text);
  const m = match(headers, WEATHER);
  const missing = ['srad', 'tmax', 'tmin', 'rain'].filter((c) => !m[c]);
  if (missing.length) throw new Error(t(`weather: columns not found: ${missing.join(', ')} (columns: ${headers.join(', ')})`, `clima: não encontrei as colunas ${missing.join(', ')} (colunas: ${headers.join(', ')})`));
  let dates;
  const ymd = match(headers, YMD), d = match(headers, DATE);
  if (ymd.year && ymd.doy) dates = rows.map((r) => { const t = new Date(Date.UTC(+r[ymd.year], 0, +r[ymd.doy])); return t.toISOString().slice(0, 10); });
  else if (ymd.year && ymd.month && ymd.day) dates = rows.map((r) => `${r[ymd.year]}-${String(r[ymd.month]).padStart(2, '0')}-${String(r[ymd.day]).padStart(2, '0')}`);
  else if (d.date) {
    const dayFirst = rows.every((r) => /^\d{1,2}[/.-]\d{1,2}[/.-]\d{4}$/.test(r[d.date]));
    dates = rows.map((r) => parseDate(r[d.date], dayFirst));
  } else throw new Error(t('weather: include a date column (date/data) or year + day of year', 'clima: inclua uma coluna de data (data/date) ou ano + dia do ano'));
  const cols = Object.fromEntries(Object.entries(m).map(([std, c]) => [std, rows.map((r) => num(r[c], decimalComma))]));
  const conversions = [], convert = (c, cond, f, off, msg) => {
    if (cols[c] && cols[c].some(Number.isFinite) && cond(cols[c])) { cols[c] = cols[c].map((v) => v * f + off); conversions.push(`${c}: ${msg}`); }
  };
  convert('srad', (v) => median(v) > 1000, 1e-3, 0, 'kJ/m²/d → MJ/m²/d');
  convert('srad', (v) => median(v) > 60, 0.0864, 0, 'W/m² → MJ/m²/d');
  for (const c of ['tmax', 'tmin', 'dewp']) convert(c, (v) => median(v) > 150, 1, -273.15, 'K → °C');
  convert('rhum', (v) => max(v) <= 1.5, 100, 0, t('fraction → %', 'fração → %'));
  const records = dates.map((date, i) => date && Object.fromEntries([['date', date], ...Object.keys(cols).map((c) => [c, cols[c][i]])])).filter(Boolean);
  if (!records.length) throw new Error(t('weather: no valid date', 'clima: nenhuma data válida'));
  return { table: tableFromRecords(records, SRC.user), rows: records.length, conversions, columns: Object.keys(cols) };
}

/** Soil profiles from a CSV, one row per layer: `{profiles: {name: layers}, conversions}`. */
export function readSoils(text) {
  const { headers, rows, decimalComma } = parseCsv(text);
  const m = match(headers, SOIL);
  if (!m.bottom) throw new Error(t('soil: the layer depth is missing (bottom/depth)', 'solo: falta a profundidade das camadas (base/profundidade)'));
  const cols = Object.fromEntries(Object.entries(m).filter(([s]) => s !== 'profile').map(([s, c]) => [s, rows.map((r) => num(r[c], decimalComma))]));
  const conversions = [], convert = (c, cond, f, msg) => {
    if (cols[c] && cols[c].some(Number.isFinite) && cond(cols[c])) { cols[c] = cols[c].map((v) => v * f); conversions.push(`${c}: ${msg}`); }
  };
  for (const c of ['clay', 'sand', 'silt']) { convert(c, (v) => max(v) <= 1, 100, t('fraction → %', 'fração → %')); convert(c, (v) => max(v) > 100, 0.1, 'g/kg → %'); }
  convert('soc', (v) => max(v) > 15, 0.1, 'g/kg → %');
  if (cols.om) {
    convert('om', (v) => max(v) > 25, 0.1, 'g/kg → %');
    if (!cols.soc || !cols.soc.some(Number.isFinite)) { cols.soc = cols.om.map((v) => v / 1.724); conversions.push(t('organic matter → organic carbon (÷1.724)', 'matéria orgânica → carbono orgânico (÷1,724)')); }
    delete cols.om;
  }
  convert('bdod', (v) => median(v) > 100, 1e-3, 'kg/m³ → g/cm³');
  for (const c of ['ll', 'dul', 'sat']) convert(c, (v) => max(v) > 1, 0.01, '% → cm³/cm³');
  if (!cols.sand && cols.clay && cols.silt) cols.sand = cols.clay.map((c, i) => 100 - c - cols.silt[i]);
  if (!cols.silt && cols.clay && cols.sand) cols.silt = cols.clay.map((c, i) => 100 - c - cols.sand[i]);
  const profiles = {};
  rows.forEach((r, i) => {
    const name = m.profile ? r[m.profile] || t('profile', 'perfil') : t('profile', 'perfil');
    const layer = Object.fromEntries(Object.keys(cols).map((c) => [c, cols[c][i]]));
    if (Number.isFinite(layer.bottom)) (profiles[name] ??= []).push(layer);
  });
  for (const [name, layers] of Object.entries(profiles)) {
    layers.sort((a, b) => a.bottom - b.bottom);
    layers.forEach((l, i) => { if (!Number.isFinite(l.top)) l.top = i ? layers[i - 1].bottom : 0; });
    const lack = ['clay', 'sand', 'soc', 'bdod'].filter((c) => layers.some((l) => !Number.isFinite(l[c])));
    if (lack.length) throw new Error(t(`soil (${name}): missing ${lack.join(', ')} in some layer`, `solo (${name}): faltam valores de ${lack.join(', ')} em alguma camada`));
    if (layers.some((l) => l.bottom <= l.top)) throw new Error(t(`soil (${name}): check the layer depths`, `solo (${name}): confira as profundidades das camadas`));
  }
  if (!Object.keys(profiles).length) throw new Error(t('soil: no valid layer', 'solo: nenhuma camada válida'));
  return { profiles, conversions };
}

// ------------------------------------------------------------ templates (cropemu.io.write_templates, lang "en" / "pt")
const TEMPLATE_TEXT = {
  weather: {
    en: { file: 'weather.csv', title: 'Daily weather', header: ['date', 'srad (MJ/m2/d)', 'tmax (C)', 'tmin (C)', 'rain (mm)', 'rhum (%)', 'wind (m/s)'],
      note: 'One row per day. Required: date, solar radiation, Tmax, Tmin and rain. Optional: relative humidity, wind (at 2 m) or dew point. Missing days and columns are completed with NASA POWER; your values always take precedence. Comma or semicolon separated, decimal point or comma, dates as YYYY-MM-DD or DD/MM/YYYY. Portuguese headers are accepted too.' },
    pt: { file: 'clima.csv', title: 'Clima diário', header: ['data', 'radiacao (MJ/m2/d)', 'tmax (C)', 'tmin (C)', 'chuva (mm)', 'umidade (%)', 'vento (m/s)'],
      note: 'Uma linha por dia. Obrigatórias: data, radiação, Tmax, Tmin e chuva. Opcionais: umidade, vento (a 2 m) ou ponto de orvalho. Dias e colunas que faltarem são completados pela NASA POWER; seus valores têm sempre precedência. Aceita vírgula ou ponto e vírgula, decimal com ponto ou vírgula, data AAAA-MM-DD ou DD/MM/AAAA. Cabeçalhos em inglês também são aceitos.' },
    rows: [['2023-10-01', '22.5', '31.2', '18.4', '0.0', '65', '2.1'], ['2023-10-02', '18.1', '29.0', '19.2', '12.4', '78', '1.8'], ['2023-10-03', '24.9', '32.5', '18.9', '0.0', '61', '2.4']],
  },
  soil: {
    en: { file: 'soil.csv', title: 'Soil profile', header: ['profile', 'top (cm)', 'bottom (cm)', 'clay (%)', 'sand (%)', 'silt (%)', 'soc (%)', 'bdod (g/cm3)', 'll (cm3/cm3)', 'dul (cm3/cm3)'],
      note: 'One row per layer (down to 2 m). Required: layer bottom (cm), clay and sand (%), organic carbon (%) or organic matter, bulk density (g/cm³). Wilting point (ll) and field capacity (dul) in cm³/cm³ are optional: without them they are estimated as in training. Several profiles in one sheet: use the profile column.' },
    pt: { file: 'solo.csv', title: 'Perfil de solo', header: ['perfil', 'topo (cm)', 'base (cm)', 'argila (%)', 'areia (%)', 'silte (%)', 'carbono (%)', 'densidade (g/cm3)', 'pmp (cm3/cm3)', 'cc (cm3/cm3)'],
      note: 'Uma linha por camada (até 2 m). Obrigatórias: base da camada (cm), argila e areia (%), carbono orgânico (%) ou matéria orgânica, densidade (g/cm³). Ponto de murcha (pmp) e capacidade de campo (cc) em cm³/cm³ são opcionais: sem eles, são estimados como no treino. Vários perfis na mesma planilha: use a coluna perfil.' },
    rows: [['A', '0', '20', '55', '25', '20', '1.6', '1.2', '', ''], ['A', '20', '60', '60', '20', '20', '0.9', '1.25', '', ''], ['A', '60', '200', '62', '18', '20', '0.4', '1.3', '', '']],
  },
};
/** Template of a spreadsheet ('weather' or 'soil') in the interface language. */
export const template = (name) => ({ ...TEMPLATE_TEXT[name][getLang()], rows: TEMPLATE_TEXT[name].rows });
export const templateCsv = (t) => [t.header, ...t.rows].map((r) => r.join(',')).join('\n') + '\n';

// ------------------------------------------------------------ export
const cell = (v) => {
  if (v == null || (typeof v === 'number' && !Number.isFinite(v))) return '';
  if (typeof v === 'number') return String(Math.round(v * 1e4) / 1e4);
  const s = String(v);
  return /[",\n;]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
};
export const toCsv = (rows, columns = Object.keys(rows[0] ?? {})) => [columns.join(','), ...rows.map((r) => columns.map((c) => cell(r[c])).join(','))].join('\n') + '\n';

export function download(name, text, type = 'text/csv') {
  const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
  const a = Object.assign(document.createElement('a'), { href: url, download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
