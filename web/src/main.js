import './style.css';
import { fromYMD, isoDate, monthName, today, fullDate, dayOfYear } from './engine/dates.js';
import { Emulator, EMULATORS } from './engine/emulator.js';
import { readSoils, readWeather, template, templateCsv, download } from './engine/io.js';
import { aquacropCultivar, dssatCultivar, typicalMg } from './engine/season.js';
import { prepareSoil } from './engine/soil.js';
import { fetchSoilGrids } from './engine/soilgrids.js';
import { cultivarLabel } from './engine/units.js';
import { combine, completeSpan, fillGaps, fetchPower, POWER_FIRST_DAY, SRC, WeatherSeries } from './engine/weather.js';
import { $, h, fmt, auto } from './ui/dom.js';
import { TABS } from './ui/tabs.js';
import { setupMap } from './ui/map.js';
import { getLang, onLang, setLang, t, translateDom } from './i18n.js';

translateDom();

// ------------------------------------------------------------------ state
const state = {
  model: 'dssat-soybean-v1',
  emulators: {},           // name -> Emulator (loaded on demand)
  site: null,              // {lat, lon, elev, ws, table, info, profile, soilSource}
  tab: 'safra',
  variable: {},            // per family: output analysed in the multi-season tabs
  tabState: {},            // per tab: its own controls
  cache: {},               // per tab: last computed data
  userWeather: null, userSoils: null,
};

// ------------------------------------------------------------------ sidebar controls
for (let d = 1; d <= 31; d++) $('sow-day').append(h('option', { value: d }, d));
const fillMonths = () => { const v = $('sow-month').value; $('sow-month').replaceChildren(...Array.from({ length: 12 }, (_, i) => h('option', { value: i + 1 }, monthName(i + 1)))); if (v) $('sow-month').value = v; };
fillMonths();
setSowing(-1);
fillYears(1985, new Date().getUTCFullYear() - 1);

function setSowing(latSign) {
  const [d, m] = latSign < 0 ? [20, 10] : [15, 5];
  $('sow-day').value = d; $('sow-month').value = m;
}

function fillYears(first, last, keep = true) {
  const old = { year: +$('year').value, from: +$('year-from').value, to: +$('year-to').value };
  for (const id of ['year', 'year-from', 'year-to']) $(id).replaceChildren(...Array.from({ length: last - first + 1 }, (_, i) => h('option', { value: last - i }, last - i)));
  const clampY = (y, dflt) => (keep && y >= first && y <= last ? y : dflt);
  $('year').value = clampY(old.year, last);
  $('year-to').value = clampY(old.to, last);
  $('year-from').value = clampY(old.from, Math.max(first, last - 34));
}

/** Years whose season (30 days before to 130 days after sowing) the weather covers. */
function coveredYears() {
  const ws = state.site?.ws;
  if (!ws) return null;
  const d = +$('sow-day').value, m = +$('sow-month').value, out = [];
  const y0 = new Date(ws.t0 * 864e5).getUTCFullYear(), y1 = new Date((ws.t0 + ws.n) * 864e5).getUTCFullYear();
  for (let y = y0; y <= y1; y++) if (ws.covers(fromYMD(y, m, d), -30, 130)) out.push(y);
  return out;
}
function refreshYears() {
  const years = coveredYears();
  if (years?.length) fillYears(years[0], years.at(-1));
}

$('preset').addEventListener('change', (e) => {
  if (!e.target.value) return;
  const [lat, lon] = e.target.value.split(',');
  $('lat').value = lat; $('lon').value = lon;
  loadSite();
});
$('geolocate').addEventListener('click', () => {
  if (!navigator.geolocation) return setStatus('error', () => t('This browser does not provide the location.', 'Este navegador não fornece a localização.'));
  setStatus('busy', () => t('Getting the device location…', 'Obtendo a localização do dispositivo…'));
  navigator.geolocation.getCurrentPosition(
    (p) => { $('lat').value = p.coords.latitude.toFixed(4); $('lon').value = p.coords.longitude.toFixed(4); $('preset').value = ''; loadSite(); },
    (e) => setStatus('error', () => t(`Location unavailable: ${e.message}`, `Localização indisponível: ${e.message}`)), { timeout: 15000 });
});
$('load').addEventListener('click', () => loadSite());
for (const id of ['lat', 'lon']) $(id).addEventListener('keydown', (e) => { if (e.key === 'Enter') loadSite(); });

const files = { weather: null, soil: null };     // {name, error?} of the chosen files
function fileLabels() {
  const w = files.weather, s = files.soil;
  $('weather-name').textContent = !w ? t('date, radiation, Tmax, Tmin, rain…', 'data, radiação, Tmax, Tmin, chuva…') : w.error ? `${w.name}: ${w.error}` : (() => {
    const d = state.userWeather, span = completeSpan(d.table);
    return `${w.name}: ${d.rows} ${t('days', 'dias')}${span ? `, ${fullDate(span[0])} ${t('to', 'a')} ${fullDate(span[1])}` : ''}${d.conversions.length ? ` · ${d.conversions.join('; ')}` : ''}`;
  })();
  $('soil-name').textContent = !s ? t('layers with clay, sand, carbon…', 'camadas com argila, areia, carbono…') : s.error ? `${s.name}: ${s.error}`
    : `${s.name}: ${Object.keys(state.userSoils.profiles).length} ${t('profile(s)', 'perfil(is)')}${state.userSoils.conversions.length ? ` · ${state.userSoils.conversions.join('; ')}` : ''}`;
}
fileLabels();
$('weather-file').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  state.userWeather = null; files.weather = file ? { name: file.name } : null;
  if (file) {
    try { state.userWeather = readWeather(await file.text()); } catch (error) { files.weather.error = error.message; e.target.value = ''; }
  }
  fileLabels();
});
$('soil-file').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  state.userSoils = null; $('profile-field').hidden = true; files.soil = file ? { name: file.name } : null;
  if (file) {
    try {
      state.userSoils = readSoils(await file.text());
      const names = Object.keys(state.userSoils.profiles);
      $('profile').replaceChildren(...names.map((n) => h('option', { value: n }, n)));
      $('profile-field').hidden = names.length < 2;
    } catch (error) { files.soil.error = error.message; e.target.value = ''; }
  }
  fileLabels();
});

// spreadsheet help: preview of the expected layout + template download
const popover = $('popover');
function showTemplate(name, anchor) {
  const tp = template(name);
  popover.replaceChildren(
    h('div.pop-head', h('strong', `${t('How to organise', 'Como organizar')}: ${tp.title}`), h('button.close', { type: 'button', 'aria-label': t('Close', 'Fechar'), onclick: hidePopover }, '×')),
    h('div.sheet', h('table', h('thead', h('tr', h('th.rowno', ''), tp.header.map((c, i) => h('th', String.fromCharCode(65 + i))))),
      h('tbody', h('tr.hdr', h('td.rowno', '1'), tp.header.map((c) => h('td', c))), tp.rows.map((r, k) => h('tr', h('td.rowno', k + 2), r.map((v) => h('td', v)))),
        h('tr', h('td.rowno', '…'), tp.header.map(() => h('td', '…')))))),
    h('p', tp.note),
    h('button.secondary', { type: 'button', onclick: () => download(tp.file, templateCsv(tp)) }, `${t('Download template', 'Baixar modelo')} ${tp.file}`));
  popover.hidden = false;
  const r = anchor.getBoundingClientRect();
  popover.style.top = `${Math.min(window.innerHeight - popover.offsetHeight - 8, r.top) + window.scrollY}px`;
  popover.style.left = `${Math.min(window.innerWidth - popover.offsetWidth - 8, r.right + 10)}px`;
  if (window.innerWidth < 760) { popover.style.left = '8px'; popover.style.top = `${r.bottom + window.scrollY + 6}px`; }
}
function hidePopover() { popover.hidden = true; popover.dataset.pinned = ''; }
for (const row of document.querySelectorAll('.upload-row')) {
  const name = row.dataset.template, btn = row.querySelector('.help');
  let timer;
  row.addEventListener('mouseenter', () => { clearTimeout(timer); if (!popover.dataset.pinned) timer = setTimeout(() => showTemplate(name, row), 250); });
  row.addEventListener('mouseleave', () => { clearTimeout(timer); if (!popover.dataset.pinned) timer = setTimeout(() => { if (!popover.dataset.hover) hidePopover(); }, 300); });
  btn.addEventListener('click', (e) => { e.preventDefault(); showTemplate(name, row); popover.dataset.pinned = '1'; });
}
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hidePopover(); });
document.addEventListener('click', (e) => { if (!popover.hidden && !popover.contains(e.target) && !e.target.closest('.help')) hidePopover(); });
popover.addEventListener('mouseenter', () => { popover.dataset.hover = '1'; });
popover.addEventListener('mouseleave', () => { popover.dataset.hover = ''; if (!popover.dataset.pinned) setTimeout(() => { if (!popover.dataset.hover) hidePopover(); }, 300); });

// model and every setting
document.querySelectorAll('input[name=model]').forEach((r) => r.addEventListener('change', () => { state.model = r.value; onModel(); }));
for (const id of ['sow-day', 'sow-month']) $(id).addEventListener('change', () => { refreshYears(); updateCultivarHints(); schedule(); });
for (const id of ['year', 'year-from', 'year-to', 'co2', 'dt', 'rain-factor', 'mg', 'cycle-days', 'cycle-factor', 'gdd']) {
  $(id).addEventListener('change', () => { updateCultivarHints(); schedule(); });
}
document.querySelectorAll('input[name=water]').forEach((r) => r.addEventListener('change', schedule));
$('reset-coef').addEventListener('click', () => { $('coefficients').querySelectorAll('input').forEach((i) => { i.value = ''; }); updateCultivarHints(); schedule(); });

// ------------------------------------------------------------------ status
/** Status under the load button; `text` returns [message, detail?] so it can be redone in another language. */
let lastStatus = null;
function setStatus(kind, text) {
  lastStatus = { kind, text };
  const [message, detail] = [].concat(text());
  $('status').className = `status ${kind}`;
  $('status').replaceChildren(h('span.dot'), h('div', h('strong', message), detail ? h('small', detail) : null));
}

// ------------------------------------------------------------------ loading
async function emulator(name = state.model) {
  if (!state.emulators[name]) state.emulators[name] = Emulator.load(name);
  return state.emulators[name];
}

// ------------------------------------------------------------------ "running" indicator
const busyBox = h('div.busy-box', { role: 'status', 'aria-live': 'polite', hidden: true });
$('panel').before(busyBox);
/** Show what is running: a title and steps [{label, state: 'wait'|'run'|'done', done?, total?}]. */
function showBusy(title, steps = []) {
  busyBox.hidden = false;
  busyBox.replaceChildren(h('div.busy-row', h('span.spinner', { 'aria-hidden': 'true' }), h('strong', title)),
    steps.length ? h('ul.busy-steps', steps.map((st) => h(`li.${st.state}`, h('i'), h('span', st.label),
      st.total ? h('span.bar', h('b', { style: { width: `${Math.round(100 * (st.done ?? 0) / st.total)}%` } })) : null,
      st.total ? h('small', `${st.done ?? 0}/${st.total}`) : null))) : null);
}
function hideBusy() { busyBox.hidden = true; }
/** Let the browser paint the indicator before a long synchronous computation. */
const paint = () => new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0)));

let loading = 0;
async function loadSite() {
  const lat = Number($('lat').value), lon = $('lon').value === '' ? NaN : Number($('lon').value);
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) return setStatus('error', () => t('Enter the latitude (−90 to 90).', 'Informe a latitude (−90 a 90).'));
  const useUserWeather = !!state.userWeather, useUserSoil = !!state.userSoils;
  if (!Number.isFinite(lon) && !(useUserWeather && useUserSoil)) return setStatus('error', () => t('Enter the longitude to fetch weather and soil.', 'Informe a longitude para buscar clima e solo.'));
  const token = ++loading;
  $('load').disabled = true; $('load').classList.add('running'); $('load').textContent = t('Loading…', 'Carregando…');
  try {
    let soilDone = 0;
    const st = { weather: 'run', soil: useUserSoil ? 'done' : 'run', model: 'run' };
    const progress = () => {
      if (token !== loading) return;
      setStatus('busy', () => [t('Loading site data…', 'Carregando dados do local…'), `${t('Weather', 'Clima')}: NASA POWER · ${t('soil', 'solo')}: ${useUserSoil ? t('spreadsheet', 'planilha') : `SoilGrids ${soilDone}/24`}`]);
      showBusy(`${t('Loading', 'Carregando')} ${fmt(lat, 2)}°, ${Number.isFinite(lon) ? fmt(lon, 2) : '—'}°`, [
        { label: useUserWeather ? t('Daily weather: your spreadsheet, completed with NASA POWER', 'Clima diário: sua planilha, completada pela NASA POWER') : t('Daily weather since 1984 (NASA POWER)', 'Clima diário desde 1984 (NASA POWER)'), state: st.weather },
        { label: useUserSoil ? t('Soil profile: your spreadsheet', 'Perfil de solo: sua planilha') : t('Soil profile (SoilGrids, 6 layers × 4 properties)', 'Perfil de solo (SoilGrids, 6 camadas × 4 propriedades)'), state: st.soil, ...(useUserSoil ? {} : { done: soilDone, total: 24 }) },
        { label: t('Emulator (ONNX neural network)', 'Emulador (rede neural ONNX)'), state: st.model },
      ]);
    };
    progress();
    const weatherJob = (Number.isFinite(lon) ? fetchPower(lat, lon, POWER_FIRST_DAY, today()) : Promise.resolve(null)).then((r) => { st.weather = 'done'; progress(); return r; });
    const soilJob = useUserSoil
      ? Promise.resolve({ layers: state.userSoils.profiles[$('profile').value || Object.keys(state.userSoils.profiles)[0]], source: { en: `spreadsheet (${files.soil?.name ?? 'soil'})`, pt: `planilha (${files.soil?.name ?? 'solo'})` } })
      : fetchSoilGrids(lat, lon, (d) => { soilDone = d; progress(); }).then((r) => { st.soil = 'done'; progress(); return r; });
    const modelJob = emulator().then((r) => { st.model = 'done'; progress(); return r; });
    const [power, soil] = await Promise.all([weatherJob, soilJob, modelJob]);
    if (token !== loading) return;
    const { table, taken } = combine(state.userWeather?.table ?? null, power?.table ?? null);
    if (!table) throw new Error(t('no weather data', 'não há dados de clima'));
    const filled = fillGaps(table);
    const span = completeSpan(table);
    if (!span) throw new Error(t('the weather has no complete day (radiation, Tmax, Tmin and rain)', 'o clima não tem nenhum dia completo (radiação, Tmax, Tmin e chuva)'));
    const elevInput = Number($('elev').value);
    const elev = $('elev').value !== '' && Number.isFinite(elevInput) ? elevInput : power?.elevation ?? 0;
    const counts = {}; let user = 0;
    for (const c of ['tmax', 'tmin', 'srad', 'rain']) for (const s of table.src[c]) { counts[s] = (counts[s] ?? 0) + 1; if (s === SRC.user) user++; }
    state.site = {
      lat, lon, elev, table, ws: new WeatherSeries(table, lat, elev), profile: soil.layers, soilSource: soil.source,
      info: { span, filled, taken, user: user / 4, power: (counts[SRC.power] ?? 0) / 4, cell: power?.cell, elevSource: $('elev').value !== '' ? 'input' : power ? 'power' : 'default' },
    };
    state.cache = {};
    setSowing(Math.sign(lat) || 1);
    refreshYears();
    buildCoefficients();
    updateCultivarHints();
    const yrs = coveredYears();
    setStatus('ok', () => [`${t('Site loaded', 'Local carregado')}: ${fmt(lat, 2)}°, ${Number.isFinite(lon) ? fmt(lon, 2) : '—'}°`,
      t(`Weather ${fullDate(span[0])} to ${fullDate(span[1])} (${yrs?.length ?? 0} possible seasons) · elevation ${fmt(elev, 0)} m · soil: ${soil.source.en}`,
        `Clima ${fullDate(span[0])} a ${fullDate(span[1])} (${yrs?.length ?? 0} safras possíveis) · altitude ${fmt(elev, 0)} m · solo: ${soil.source.pt}`)]);
    renderTabs(); refresh();
  } catch (error) {
    if (token === loading) { hideBusy(); setStatus('error', () => [t('Could not load the site.', 'Não foi possível carregar o local.'), `${error.message}. ${t('Try again or upload your spreadsheets.', 'Tente de novo ou envie suas planilhas.')}`]); }
    console.error(error);
  } finally { if (token === loading) { $('load').disabled = false; $('load').classList.remove('running'); $('load').textContent = t('Load weather and soil', 'Carregar clima e solo'); } }
}

// ------------------------------------------------------------------ cultivar
const family = () => (state.model.includes('aquacrop') ? 'aquacrop' : 'dssat');
const SEPARATE = { dssat: ['mg'], aquacrop: ['cycle_factor', 'gdd_maturity'] };

function buildCoefficients() {
  const emu = state.emulators[state.model];
  if (!(emu instanceof Emulator)) return;
  const card = emu.card, fam = emu.family;
  const old = Object.fromEntries([...$('coefficients').querySelectorAll('input')].map((i) => [i.dataset.k, i.value]));
  $('coefficients').replaceChildren(h('div.coef-grid', card.cultivar.filter((k) => !SEPARATE[fam].includes(k)).map((k) => {
    const d = card.domain[k];
    return h('label.coef-row', h('span.coef-name', { title: k }, cultivarLabel(k), h('code', k)),
      h('input', { type: 'number', step: 'any', 'data-k': k, value: card.model === $('coefficients').dataset.model ? old[k] ?? '' : '', onchange: () => { updateCultivarHints(); schedule(); } }),
      h('small.range', `${auto(d.min)}–${auto(d.max)}`));
  })));
  $('coefficients').dataset.model = card.model;
}

/** Cultivar parameters for the current settings (for AquaCrop the cycle uses the sowing day of year). */
function cultivar(emu, { mg = null, factor = null } = {}) {
  const site = state.site, card = emu.card;
  const overrides = Object.fromEntries([...$('coefficients').querySelectorAll('input')].filter((i) => i.value !== '' && Number.isFinite(+i.value)).map((i) => [i.dataset.k, +i.value]));
  if (emu.family === 'dssat') {
    const g = mg ?? ($('mg').value !== '' ? +$('mg').value : typicalMg(card, site?.lat ?? 0));
    return { ...dssatCultivar(card, g), ...overrides, mg: g };
  }
  const f = factor ?? (+$('cycle-factor').value || 1);
  const gddIn = +$('gdd').value;
  const sowingDoy = dayOfYear(fromYMD(2001, +$('sow-month').value, +$('sow-day').value));
  const base = $('gdd').value !== '' && gddIn > 0 ? gddIn : site.ws.seasonGdd(sowingDoy, +$('cycle-days').value || 120);
  return { ...aquacropCultivar(card, { ws: site.ws, sowingDoy, gddMaturity: base * f, cycleFactor: f }), ...overrides };
}

function updateCultivarHints() {
  const emu = state.emulators[state.model];
  if (!(emu instanceof Emulator)) return;
  const lat = state.site?.lat;
  if (emu.family === 'dssat') {
    const g = Number.isFinite(lat) ? typicalMg(emu.card, lat) : null;
    $('mg').placeholder = g != null ? `${t('typical of the latitude', 'típico da latitude')}: ${fmt(g, 1)}` : t('typical of the latitude', 'típico da latitude');
    $('mg-hint').textContent = g != null
      ? t(`Blank: MG ${fmt(g, 1)}, typical of ${fmt(Math.abs(lat), 1)}° latitude. The 13 coefficients follow the MG (CROPGRO cultivar file).`, `Vazio: GM ${fmt(g, 1)}, típico de ${fmt(Math.abs(lat), 1)}° de latitude. Os 13 coeficientes seguem o GM (arquivo de cultivares do CROPGRO).`)
      : t('Blank: typical MG of the latitude.', 'Vazio: GM típico da latitude.');
  } else if (state.site) {
    try {
      const c = cultivar(emu);
      $('gdd').placeholder = `${t('estimated', 'estimado')}: ${fmt(c.gdd_maturity, 0)}`;
      $('gdd-hint').textContent = t(`Blank: mean growing degrees of the ${$('cycle-days').value} days after sowing at this site (base 5 °C, upper 30 °C) × cycle factor = ${fmt(c.gdd_maturity, 0)} °C·d.`,
        `Vazio: graus-dia médios dos ${$('cycle-days').value} dias após a semeadura neste local (base 5 °C, teto 30 °C) × fator de ciclo = ${fmt(c.gdd_maturity, 0)} °C·d.`);
    } catch (error) { $('gdd-hint').textContent = error.message; }
  }
  // placeholders = default values of the current cultivar, before overrides
  if (!state.site && emu.family === 'aquacrop') return;
  const defaults = emu.family === 'dssat' ? dssatCultivar(emu.card, $('mg').value !== '' ? +$('mg').value : typicalMg(emu.card, lat ?? 0)) : { ...emu.card.cultivar_defaults };
  for (const input of $('coefficients').querySelectorAll('input')) {
    const k = input.dataset.k, d = emu.card.domain[k], v = input.value !== '' ? +input.value : defaults[k];
    input.placeholder = auto(defaults[k]);
    const row = input.closest('.coef-row');
    row.classList.toggle('out', v < d.min || v > d.max);
    row.classList.toggle('rare', !(v < d.min || v > d.max) && (v < d.q005 || v > d.q995));
  }
}

async function onModel() {
  document.querySelectorAll('[data-family]').forEach((el) => { el.hidden = el.dataset.family !== family(); });
  state.cache = {};
  try { await emulator(); } catch (error) { setStatus('error', () => [t('Could not load the model.', 'Não foi possível carregar o modelo.'), error.message]); return; }
  buildCoefficients(); updateCultivarHints(); renderTabs(); refresh();
}

// ------------------------------------------------------------------ analysis context for the tabs
function settings() {
  const v = (id) => $(id).value, n = (id) => Number($(id).value);
  return {
    day: n('sow-day'), month: n('sow-month'), year: n('year'),
    yearFrom: Math.min(n('year-from'), n('year-to')), yearTo: Math.max(n('year-from'), n('year-to')),
    irrigated: document.querySelector('input[name=water]:checked').value === 'irrigated',
    co2: v('co2') === '' ? NaN : n('co2'), dt: n('dt') || 0, rainFactor: v('rain-factor') === '' ? 1 : n('rain-factor'),
  };
}

function context(emu) {
  const s = settings(), site = state.site;
  const soil = site ? prepareSoil(site.profile, emu.card, site.lat) : null;
  const covered = coveredYears() ?? [];
  const ctx = {
    emu, site, s, soil: soil?.features, soilLayers: soil?.layers, soilMeasured: soil?.measured,
    years: covered.filter((y) => y >= s.yearFrom && y <= s.yearTo),
    covered,
    sowing: (year, day = s.day, month = s.month) => fromYMD(year, month, day),
    cultivar: (opts) => cultivar(emu, opts),
    /** One season with the current management (override any field). */
    season: (year, extra = {}) => ({ year, sowing: fromYMD(year, s.month, s.day), cultivar: ctx.cultivar(), irrigated: s.irrigated, co2: s.co2, dt: s.dt, rainFactor: s.rainFactor, ...extra }),
    run: (seasons) => emu.run(site.ws, soil.features, seasons),
    variable: state.variable[emu.family] ?? emu.keys.yield,
    setVariable: (name) => { state.variable[emu.family] = name; redraw(); },
    tabState: (id, defaults) => (state.tabState[`${id}:${emu.family}`] ??= { ...defaults }),
    refresh, redraw,
    cached: (id) => (state.cache[id]?.family === emu.family ? state.cache[id].data : null),
    isoDate, fullDate,
  };
  return ctx;
}

// ------------------------------------------------------------------ tabs
function renderTabs() {
  $('tabs').replaceChildren(...TABS.map((t) => h(`button.tab${t.id === state.tab ? '.active' : ''}`, {
    type: 'button', role: 'tab', 'aria-selected': t.id === state.tab,
    onclick: () => { state.tab = t.id; renderTabs(); refresh(); },
  }, t.label)));
}

let timer = null, run = 0;
function schedule() { clearTimeout(timer); timer = setTimeout(refresh, 250); }

async function refresh() {
  const token = ++run, tab = TABS.find((t) => t.id === state.tab), panel = $('panel');
  let emu;
  try { emu = await emulator(); } catch (error) { panel.replaceChildren(h('div.empty', h('h2', t('Model unavailable', 'Modelo indisponível')), h('p', error.message))); return; }
  if (token !== run) return;
  if (tab.needsSite && !state.site) { panel.replaceChildren(emptyState()); return; }
  const ctx = context(emu);
  panel.classList.add('busy');
  if (tab.compute) {
    const m = emu.family === 'dssat' ? 'DSSAT' : 'AquaCrop';
    showBusy(`${t('Computing', 'Calculando')}: ${tab.label.toLowerCase()}`, [{ label: t(`${m} running in your browser — weather, soil and cultivar become the network inputs and the emulator predicts each season`, `${m} rodando no seu navegador — clima, solo e cultivar viram as entradas da rede e o emulador prevê cada safra`), state: 'run' }]);
    await paint();
    if (token !== run) return;
  }
  try {
    const data = tab.compute ? await tab.compute(ctx) : null;
    if (token !== run) return;
    state.cache[tab.id] = { data, family: emu.family };
    panel.replaceChildren();
    tab.render(ctx, data, panel);
  } catch (error) {
    console.error(error);
    if (token === run) panel.replaceChildren(h('div.empty.error', h('h2', t('Could not compute', 'Não foi possível calcular')), h('p', error.message)));
  } finally { if (token === run) { panel.classList.remove('busy'); hideBusy(); } }
}

/** Redraw the current tab from its cached data (variable or layout changes). */
async function redraw() {
  const tab = TABS.find((t) => t.id === state.tab), cached = state.cache[tab.id], emu = await emulator();
  if (!cached || cached.family !== emu.family || (tab.needsSite && !state.site)) return refresh();
  const panel = $('panel');
  panel.replaceChildren();
  tab.render(context(emu), cached.data, panel);
}

let lastWidth = window.innerWidth;
window.addEventListener('resize', () => { if (Math.abs(window.innerWidth - lastWidth) > 40) { lastWidth = window.innerWidth; clearTimeout(timer); timer = setTimeout(redraw, 200); } });

function emptyState() {
  const chips = [['-23.19,-51.18', 'Londrina, BR'], ['42.03,-93.62', 'Ames, Iowa'], ['-12.55,-55.71', 'Sorriso, BR'], ['-32.95,-60.65', 'Rosario, AR']];
  return h('div.empty',
    h('p.eyebrow', t('START WITH THE SITE', 'COMECE PELO LOCAL')),
    h('h2', t('Choose a site and load its weather and soil', 'Escolha um local e carregue o clima e o solo')),
    h('p', t('Use an example site, pick a point on the map or enter latitude and longitude — anywhere in the world. The daily weather since 1984 comes from NASA POWER and the soil profile from SoilGrids, the same sources used to train the emulators. Your spreadsheets, if uploaded, take precedence.',
      'Use um local de exemplo, escolha um ponto no mapa ou informe latitude e longitude — em qualquer lugar do mundo. O clima diário desde 1984 vem da NASA POWER e o perfil de solo do SoilGrids, as mesmas fontes usadas no treino dos emuladores. Suas planilhas, se enviadas, têm precedência.')),
    h('div.chips', chips.map(([value, name]) => h('button.chip', { type: 'button', onclick: () => { $('preset').value = value; $('preset').dispatchEvent(new Event('change')); } }, name)),
      h('button.chip', { type: 'button', onclick: () => $('open-map').click() }, t('Pick on the map…', 'Escolher no mapa…'))),
    h('ul.features',
      h('li', h('strong', t('One season', 'Uma safra')), t(' — every model output (phenology, yield, biomass, water balance), domain warnings, growth curves and the weather of the cycle.', ' — todas as saídas do modelo (fenologia, produtividade, biomassa, balanço hídrico), avisos de domínio, curvas de crescimento e o clima do ciclo.')),
      h('li', h('strong', t('Many years', 'Série de anos')), t(' — year-to-year variability, rainfed vs. no water stress, rain and evapotranspiration.', ' — variabilidade entre anos, sequeiro × sem estresse hídrico, chuva e evapotranspiração.')),
      h('li', h('strong', t('Sowing window', 'Janela de semeadura')), t(' — year × date map, median, risk bands and best date.', ' — mapa ano × data, mediana, faixas de risco e melhor data.')),
      h('li', h('strong', t('Cultivars', 'Cultivares')), t(' — maturity groups or cycle lengths and the sensitivity to each parameter.', ' — grupos de maturidade ou ciclos e sensibilidade a cada parâmetro.')),
      h('li', h('strong', t('Climate scenarios', 'Cenários climáticos')), t(' — warming, CO₂ and rain, as in training.', ' — aquecimento, CO₂ e chuva, como no treino.'))));
}

// ------------------------------------------------------------------ start
setupMap((lat, lon) => { $('lat').value = lat.toFixed(4); $('lon').value = lon.toFixed(4); $('preset').value = ''; loadSite(); });
renderTabs();
onModel();
setStatus('idle', () => [t('No site loaded.', 'Nenhum local carregado.'), t('Choose an example site, pick one on the map or enter coordinates.', 'Escolha um local de exemplo, use o mapa ou informe as coordenadas.')]);

// language switch: everything is redrawn in place (no reload, the loaded data are kept)
function markLang() { document.querySelectorAll('.lang button').forEach((b) => b.classList.toggle('active', b.dataset.lang === getLang())); }
document.querySelectorAll('.lang button').forEach((b) => b.addEventListener('click', () => setLang(b.dataset.lang)));
onLang(() => {
  translateDom(); markLang(); fillMonths(); fileLabels(); buildCoefficients(); updateCultivarHints();
  if (lastStatus) setStatus(lastStatus.kind, lastStatus.text);
  hidePopover(); renderTabs(); redraw();
});
markLang();
export { state, EMULATORS };
