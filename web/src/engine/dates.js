// Dates as integer day numbers (days since 1970-01-01, UTC): cheap arithmetic and array indexing.

export const DAY_MS = 86400000;

export const dayNumber = (iso) => Math.round(Date.parse(`${iso}T00:00:00Z`) / DAY_MS);
export const isoDate = (day) => new Date(day * DAY_MS).toISOString().slice(0, 10);
export const fromYMD = (year, month, day) => Math.round(Date.UTC(year, month - 1, day) / DAY_MS);
export const yearOf = (day) => new Date(day * DAY_MS).getUTCFullYear();
export const dayOfYear = (day) => day - fromYMD(yearOf(day), 1, 1) + 1;
export const today = () => Math.floor(Date.now() / DAY_MS);

const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
export const monthName = (m) => MONTHS[m - 1];
/** "20 out" */
export const shortDate = (day) => { const d = new Date(day * DAY_MS); return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`; };
/** "20/10/2024" */
export const brDate = (day) => { const [y, m, d] = isoDate(day).split('-'); return `${d}/${m}/${y}`; };
