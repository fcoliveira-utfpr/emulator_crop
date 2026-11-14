// Map picker: click (or search a place) to fill the coordinates. Leaflet and the OpenStreetMap tiles
// are loaded only when the map is first opened.

import { $, h, fmt } from './dom.js';

let L = null, map = null, marker = null, picked = null, onPick = null;

async function ensureMap() {
  if (map) return;
  L = (await import('leaflet')).default;
  await import('leaflet/dist/leaflet.css');
  map = L.map('map', { worldCopyJump: true, zoomControl: true }).setView([-15, -52], 4);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);
  // latitudes of the training data (outside: extrapolation)
  const shade = { stroke: false, fillColor: '#d03b3b', fillOpacity: 0.07, interactive: false };
  L.rectangle([[-90, -540], [-43.75, 540]], shade).addTo(map);
  L.rectangle([[62.75, -540], [90, 540]], shade).addTo(map);
  map.on('click', (e) => pick(e.latlng.lat, e.latlng.lng));
}

function wrapLon(lon) { return ((((lon + 180) % 360) + 360) % 360) - 180; }

function pick(lat, lon, label = null) {
  lon = wrapLon(lon);
  picked = { lat, lon };
  if (!marker) marker = L.circleMarker([lat, lon], { radius: 9, color: '#ffffff', weight: 3, fillColor: '#3d7010', fillOpacity: 1 }).addTo(map);
  else marker.setLatLng([lat, lon]);
  const outside = lat < -43.75 || lat > 62.75;
  $('map-picked').replaceChildren(...[h('strong', `${fmt(lat, 4)}°, ${fmt(lon, 4)}°`), label ? h('span', ` · ${label}`) : null,
    outside ? h('span.warn-text', ' · fora das latitudes do treino') : null].filter(Boolean));
  $('map-use').disabled = false;
}

async function search(query) {
  const list = $('map-results');
  list.hidden = false;
  list.replaceChildren(h('li.muted', 'Buscando…'));
  try {
    const url = new URL('https://nominatim.openstreetmap.org/search');
    url.search = new URLSearchParams({ q: query, format: 'jsonv2', limit: 6, 'accept-language': 'pt-BR' });
    const results = await (await fetch(url)).json();
    if (!results.length) { list.replaceChildren(h('li.muted', 'Nada encontrado.')); return; }
    list.replaceChildren(...results.map((r) => h('li', h('button', { type: 'button', onclick: () => {
      const lat = +r.lat, lon = +r.lon;
      map.setView([lat, lon], 9);
      pick(lat, lon, r.name || r.display_name.split(',')[0]);
      list.hidden = true;
    } }, r.display_name))));
  } catch (error) {
    list.replaceChildren(h('li.muted', `Busca indisponível (${error.message}). Clique direto no mapa.`));
  }
}

export function setupMap(handler) {
  onPick = handler;
  const modal = $('map-modal');
  const close = () => { modal.hidden = true; };
  $('open-map').addEventListener('click', async () => {
    modal.hidden = false;
    try { await ensureMap(); } catch (error) { $('map-picked').textContent = `Não foi possível abrir o mapa: ${error.message}`; return; }
    map.invalidateSize();
    const lat = Number($('lat').value), lon = Number($('lon').value);
    if ($('lat').value !== '' && $('lon').value !== '' && Number.isFinite(lat) && Number.isFinite(lon)) { map.setView([lat, lon], 7); pick(lat, lon); }
    $('map-query').focus();
  });
  $('map-close').addEventListener('click', close);
  modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden) close(); });
  $('map-search').addEventListener('submit', (e) => { e.preventDefault(); const q = $('map-query').value.trim(); if (q) search(q); });
  $('map-use').addEventListener('click', () => { if (!picked) return; close(); onPick(picked.lat, picked.lon); });
}
