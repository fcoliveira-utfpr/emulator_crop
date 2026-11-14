// Interface language: English (default) or Portuguese. Texts are written in place as t(english, portuguese).

const KEY = 'cropemu-lang';
const fromUrl = () => { try { return new URLSearchParams(globalThis.location?.search ?? '').get('lang'); } catch { return null; } };
const stored = () => { try { return globalThis.localStorage?.getItem(KEY); } catch { return null; } };

let lang = [fromUrl(), stored()].find((l) => l === 'en' || l === 'pt') ?? 'en';
const listeners = new Set();

export const getLang = () => lang;
export const locale = () => (lang === 'pt' ? 'pt-BR' : 'en-US');
/** The text in the current language. */
export const t = (en, pt) => (lang === 'pt' ? pt : en);

export function setLang(next) {
  if (next !== 'en' && next !== 'pt') return;
  lang = next;
  try { globalThis.localStorage?.setItem(KEY, lang); } catch { /* optional */ }
  try {
    const url = new URL(globalThis.location.href);
    if (lang === 'en') url.searchParams.delete('lang'); else url.searchParams.set('lang', lang);
    globalThis.history?.replaceState(null, '', url);
  } catch { /* optional */ }
  for (const f of listeners) f(lang);
}
export const onLang = (f) => listeners.add(f);

/** Static HTML: elements carry the English text and a `data-pt` (and `data-pt-placeholder`,
 * `data-pt-aria-label`, `data-pt-title`) attribute with the Portuguese one. */
export function translateDom(root = document) {
  const pt = lang === 'pt';
  root.documentElement && (root.documentElement.lang = pt ? 'pt-BR' : 'en');
  for (const el of root.querySelectorAll('[data-pt]')) {
    if (el.dataset.en === undefined) el.dataset.en = el.innerHTML;
    el.innerHTML = pt ? el.dataset.pt : el.dataset.en;
  }
  for (const attr of ['placeholder', 'aria-label', 'title']) {
    for (const el of root.querySelectorAll(`[data-pt-${attr}]`)) {
      const k = `en${attr.replace(/(^|-)(\w)/g, (_, __, c) => c.toUpperCase())}`;
      if (el.dataset[k] === undefined) el.dataset[k] = el.getAttribute(attr) ?? '';
      el.setAttribute(attr, pt ? el.getAttribute(`data-pt-${attr}`) : el.dataset[k]);
    }
  }
}
