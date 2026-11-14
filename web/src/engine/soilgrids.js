// SoilGrids 2.0 (ISRIC, CC-BY 4.0) at a point, read in the browser.
//
// Primary source: the 1 km aggregated GeoTIFFs (data_aggregated/1000m), the maps used to build the
// training data and read by cropemu.soil.soilgrids: only the blocks around the point are downloaded
// (HTTP Range; the server allows cross-origin reads), and each value is the median of the valid
// pixels in a 3 x 3 km window. Fallback: the 250 m maps through the WCS service (3 x 3 median).

import { fromUrl, fromArrayBuffer } from 'geotiff';
import { t } from '../i18n.js';

const FILES = 'https://files.isric.org/soilgrids/latest/data_aggregated/1000m';
const WCS = 'https://maps.isric.org/mapserv';
export const DEPTHS = [[0, 5], [5, 15], [15, 30], [30, 60], [60, 100], [100, 200]];
/** Property -> factor to the cropemu units (%, %, %, g/cm³). */
const FACTORS = { clay: 0.1, sand: 0.1, soc: 0.01, bdod: 0.01 };
const NODATA = -32768;
const cache = new Map();

// ------------------------------------------------------------ Interrupted Goode Homolosine (PROJ "igh", sphere R = a)
const R = 6378137, D2R = Math.PI / 180;
const PHI_B = (40 + 44 / 60 + 11.8 / 3600) * D2R;          // sinusoidal-Mollweide boundary latitude

function mollweide(lam, phi) {
  const k = Math.PI * Math.sin(phi);
  let t = phi, i = 0;
  for (; i < 30; i++) { const v = (t + Math.sin(t) - k) / (1 + Math.cos(t)); t -= v; if (Math.abs(v) < 1e-7) break; }
  t = i === 30 ? (t < 0 ? -Math.PI / 2 : Math.PI / 2) : t / 2;
  return [2 * Math.SQRT2 / Math.PI * lam * Math.cos(t), Math.SQRT2 * Math.sin(t)];
}
const DY0 = mollweide(0, PHI_B)[1] - PHI_B;               // aligns the Mollweide and sinusoidal parts

/** Longitude/latitude (degrees) to Homolosine metres (the CRS of the SoilGrids maps). */
export function homolosine(lon, lat) {
  const phi = lat * D2R;
  let lam0;
  if (lat >= 0) lam0 = lon < -40 ? -100 : 30;
  else lam0 = lon < -100 ? -160 : lon < -20 ? -60 : lon < 80 ? 20 : 140;
  const lam = (lon - lam0) * D2R;
  let x, y;
  if (Math.abs(phi) <= PHI_B) { x = lam * Math.cos(phi); y = phi; }
  else { [x, y] = mollweide(lam, phi); y -= Math.sign(phi) * DY0; }
  return [R * (x + lam0 * D2R), R * y];
}

const median = (values) => {
  const s = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!s.length) return NaN;
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

async function retry(job, tries = 3) {
  for (let k = 0; ; k++) {
    try { return await job(); } catch (error) { if (k >= tries - 1) throw error; await new Promise((r) => setTimeout(r, 1500 * (k + 1))); }
  }
}

async function sample1km(property, top, bottom, lon, lat, radius = 1) {
  const tiff = await fromUrl(`${FILES}/${property}/${property}_${top}-${bottom}cm_mean_1000.tif`, { allowFullFile: false });
  const image = await tiff.getImage();
  const [ox, oy] = image.getOrigin(), [rx, ry] = image.getResolution();
  const [x, y] = homolosine(lon, lat);
  const col = Math.floor((x - ox) / rx), row = Math.floor((y - oy) / ry);
  const c0 = Math.max(col - radius, 0), r0 = Math.max(row - radius, 0);
  const c1 = Math.min(col + radius + 1, image.getWidth()), r1 = Math.min(row + radius + 1, image.getHeight());
  if (c1 <= c0 || r1 <= r0) return NaN;
  const [band] = await image.readRasters({ window: [c0, r0, c1, r1] });
  return median(Array.from(band).filter((v) => v !== NODATA));
}

async function sampleWcs(property, top, bottom, lon, lat) {
  const url = new URL(WCS);
  const crs = 'http://www.opengis.net/def/crs/EPSG/0/4326';
  Object.entries({ map: `/map/${property}.map`, SERVICE: 'WCS', VERSION: '2.0.1', REQUEST: 'GetCoverage',
    COVERAGEID: `${property}_${top}-${bottom}cm_mean`, FORMAT: 'GEOTIFF_INT16', SUBSETTINGCRS: crs, OUTPUTCRS: crs })
    .forEach(([k, v]) => url.searchParams.set(k, v));
  url.searchParams.append('SUBSET', `Lat(${lat - 0.01},${lat + 0.01})`);
  url.searchParams.append('SUBSET', `Long(${lon - 0.01},${lon + 0.01})`);
  const response = await fetch(url);
  if (!response.ok) throw new Error(`WCS ${response.status}`);
  const image = await (await fromArrayBuffer(await response.arrayBuffer())).getImage();
  const [ox, oy] = image.getOrigin(), [rx, ry] = image.getResolution();
  const col = Math.round((lon - ox) / rx - 0.5), row = Math.round((lat - oy) / ry - 0.5);
  const window = [Math.max(0, col - 1), Math.max(0, row - 1), Math.min(image.getWidth(), col + 2), Math.min(image.getHeight(), row + 2)];
  const [band] = await image.readRasters({ window });
  return median(Array.from(band).filter((v) => v !== NODATA && v !== -9999));
}

async function profileFrom(sampler, lat, lon, onProgress) {
  const jobs = DEPTHS.flatMap(([top, bottom]) => Object.keys(FACTORS).map((property) => ({ top, bottom, property })));
  const layers = DEPTHS.map(([top, bottom]) => ({ top, bottom }));
  let done = 0;
  for (let k = 0; k < jobs.length; k += 12) {                       // 12 maps at a time
    await Promise.all(jobs.slice(k, k + 12).map(async ({ top, bottom, property }) => {
      const v = await retry(() => sampler(property, top, bottom, lon, lat));
      layers.find((l) => l.top === top)[property] = v * FACTORS[property];
      onProgress(++done, jobs.length);
    }));
  }
  if (layers.some((l) => Object.keys(FACTORS).some((p) => !Number.isFinite(l[p])))) {
    throw Object.assign(new Error(t('SoilGrids has no soil data at this point (water, urban area or outside the maps)', 'o SoilGrids não tem dados de solo neste ponto (água, área urbana ou fora dos mapas)')), { noData: true });
  }
  for (const l of layers) l.silt = 100 - l.clay - l.sand;
  return layers;
}

/** Soil profile (6 layers to 2 m) of a point. Returns `{layers, source}`. */
export async function fetchSoilGrids(lat, lon, onProgress = () => {}) {
  lat = Number(lat); lon = Number(lon);
  const key = `${lat.toFixed(4)},${lon.toFixed(4)}`;
  if (cache.has(key)) return structuredClone(cache.get(key));
  let result;
  try {
    result = { layers: await profileFrom(sample1km, lat, lon, onProgress), source: { en: 'SoilGrids 2.0, 1 km maps (3×3 km median, as in training)', pt: 'SoilGrids 2.0, mapas de 1 km (mediana 3×3 km, como no treino)' } };
  } catch (error) {
    if (error.noData) throw error;
    console.warn('SoilGrids 1 km falhou; usando o WCS 250 m', error);
    result = { layers: await profileFrom(sampleWcs, lat, lon, onProgress), source: { en: 'SoilGrids 2.0, 250 m maps via WCS (fallback; differs slightly from training)', pt: 'SoilGrids 2.0, mapas de 250 m via WCS (reserva; difere um pouco do treino)' } };
  }
  cache.set(key, result);
  return structuredClone(result);
}
