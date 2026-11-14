// Dates as integer day numbers (days since 1970-01-01, UTC): cheap arithmetic and array indexing.

import { getLang } from '../i18n.js';

export const DAY_MS = 86400000;

export const dayNumber = (iso) => Math.round(Date.parse(`${iso}T00:00:00Z`) / DAY_MS);
export const isoDate = (day) => new Date(day * DAY_MS).toISOString().slice(0, 10);
export const fromYMD = (year, month, day) => Math.round(Date.UTC(year, month - 1, day) / DAY_MS);
export const yearOf = (day) => new Date(day * DAY_MS).getUTCFullYear();
export const dayOfYear = (day) => day - fromYMD(yearOf(day), 1, 1) + 1;
export const today = () => Math.floor(Date.now() / DAY_MS);


const MONTHS = {
  pt: ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'],
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
};
export const monthName = (m) => MONTHS[getLang()][m - 1];
/** "20 Oct" / "20 out" */
export const shortDate = (day) => { const d = new Date(day * DAY_MS); return `${d.getUTCDate()} ${monthName(d.getUTCMonth() + 1)}`; };
/** "20 Oct 2024" / "20/10/2024" */
export const fullDate = (day) => {
  const [y, m, d] = isoDate(day).split('-');
  return getLang() === 'pt' ? `${d}/${m}/${y}` : `${+d} ${monthName(+m)} ${y}`;
};
