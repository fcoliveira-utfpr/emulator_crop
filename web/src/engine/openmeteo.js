// Recent days and the weather forecast from Open-Meteo (https://open-meteo.com, CC BY 4.0), used to
// extend the NASA POWER series (a few days late) up to today and 16 days ahead in crop monitoring.

import { isoDate, today } from './dates.js';
import { SRC, tableFromRecords } from './weather.js';
import { t } from '../i18n.js';

const FORECAST_URL = 'https://api.open-meteo.com/v1/forecast';
const ARCHIVE_URL = 'https://archive-api.open-meteo.com/v1/archive';
const DAILY = { temperature_2m_max: 'tmax', temperature_2m_min: 'tmin', shortwave_radiation_sum: 'srad', precipitation_sum: 'rain',
  relative_humidity_2m_mean: 'rhum', dew_point_2m_mean: 'dewp', wind_speed_10m_mean: 'wind' };
/** Wind at 10 m to 2 m (FAO-56 eq. 47). */
const WIND_2M = 4.87 / Math.log(67.8 * 10 - 5.42);
export const FORECAST_DAYS = 16;
export const PAST_DAYS = 92;

const memo = new Map();                  // url -> promise (one request per page view and day)

async function getJson(url) {
  if (!memo.has(url)) {
    memo.set(url, fetch(url).then(async (r) => {
      if (!r.ok) throw new Error(t(`Open-Meteo answered ${r.status}`, `o Open-Meteo respondeu ${r.status}`));
      return r.json();
    }).catch((e) => { memo.delete(url); throw e; }));
  }
  return memo.get(url);
}

function records(payload, sourceOf) {
  const d = payload?.daily;
  if (!d?.time) throw new Error(t('Open-Meteo response without daily data', 'resposta do Open-Meteo sem dados diários'));
  return d.time.map((date, i) => {
    const r = { date, source: sourceOf(date) };
    for (const [api, name] of Object.entries(DAILY)) {
      const v = d[api]?.[i];
      if (Number.isFinite(v)) r[name] = name === 'wind' ? v * WIND_2M : v;
    }
    return r;
  });
}

const query = (lat, lon, extra) => new URLSearchParams({ latitude: Number(lat).toFixed(4), longitude: Number(lon).toFixed(4),
  daily: Object.keys(DAILY).join(','), timezone: 'GMT', wind_speed_unit: 'ms', ...extra });

/** Daily weather of a point: the last `PAST_DAYS` days and `FORECAST_DAYS` of forecast, plus the
 * ERA5 archive from `from` when it starts earlier. Days before today are tagged SRC.openmeteo,
 * today onwards SRC.forecast. Returns {table, forecastFrom, last}. */
export async function fetchOpenMeteo(lat, lon, from = null) {
  const now = today(), first = now - PAST_DAYS;
  const jobs = [getJson(`${FORECAST_URL}?${query(lat, lon, { past_days: PAST_DAYS, forecast_days: FORECAST_DAYS })}`)
    .then((p) => records(p, (date) => (date < isoDate(now) ? SRC.openmeteo : SRC.forecast)))];
  if (from != null && from < first) {
    jobs.push(getJson(`${ARCHIVE_URL}?${query(lat, lon, { start_date: isoDate(from), end_date: isoDate(first - 1) })}`)
      .then((p) => records(p, () => SRC.openmeteo)));
  }
  const all = (await Promise.all(jobs)).flat();
  const byDate = new Map(all.map((r) => [r.date, r]));            // forecast call wins where both exist
  const recs = [...byDate.values()];
  const table = tableFromRecords(recs, SRC.openmeteo);
  recs.forEach((r) => { if (r.source === SRC.forecast) { const i = Math.round(Date.parse(`${r.date}T00:00:00Z`) / 864e5) - table.t0; for (const c of Object.keys(table.src)) if (table.src[c][i]) table.src[c][i] = SRC.forecast; } });
  return { table, forecastFrom: now, last: table.t0 + table.n - 1 };
}

// ------------------------------------------------------------------ seasonal forecast
const SEASONAL_URL = 'https://seasonal-api.open-meteo.com/v1/seasonal';
const clampTo = (x, lo, hi) => Math.min(hi, Math.max(lo, x));

/** Monthly anomalies of the ECMWF seasonal forecast (ensemble mean minus the model's own climate,
 * from its re-forecasts), for the next 6 months. Rain and radiation become ratios to the model
 * climate (forecast / (forecast − anomaly)), bounded to 0.3–3 and 0.7–1.3. Returns
 * {months: [{month: 'YYYY-MM', dT, dDew, rain, srad, rainMean, rainNormal}], byMonth: Map}. */
export async function fetchSeasonal(lat, lon) {
  const vars = ['temperature_2m_anomaly', 'dew_point_2m_anomaly', 'precipitation_mean', 'precipitation_anomaly', 'shortwave_radiation_mean', 'shortwave_radiation_anomaly'];
  const q = new URLSearchParams({ latitude: Number(lat).toFixed(4), longitude: Number(lon).toFixed(4), monthly: vars.join(','), timezone: 'GMT' });
  const m = (await getJson(`${SEASONAL_URL}?${q}`))?.monthly;
  if (!m?.time?.length) throw new Error(t('seasonal forecast without monthly data', 'previsão sazonal sem dados mensais'));
  const ratio = (mean, anom, lo, hi) => (Number.isFinite(mean) && Number.isFinite(anom) && mean - anom > 0 ? clampTo(mean / (mean - anom), lo, hi) : 1);
  const months = m.time.map((d, i) => ({
    month: d.slice(0, 7),
    dT: Number.isFinite(m.temperature_2m_anomaly[i]) ? m.temperature_2m_anomaly[i] : 0,
    dDew: Number.isFinite(m.dew_point_2m_anomaly?.[i]) ? m.dew_point_2m_anomaly[i] : 0,
    rain: ratio(m.precipitation_mean[i], m.precipitation_anomaly[i], 0.3, 3),
    srad: ratio(m.shortwave_radiation_mean[i], m.shortwave_radiation_anomaly[i], 0.7, 1.3),
    rainMean: m.precipitation_mean[i], rainNormal: m.precipitation_mean[i] - m.precipitation_anomaly[i],
  }));
  return { months, byMonth: new Map(months.map((x) => [x.month, x])) };
}
