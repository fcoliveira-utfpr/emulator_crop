// How to read each tab: the guide of docs/guia.md (PT) and docs/guide.md (EN), the same files shown on
// GitHub, rendered here with a small Markdown reader (headings, paragraphs, lists, bold, italics, code,
// links and <a id> anchors). Each tab links to its section with "How to read this tab".

import guideEn from '../../../../docs/guide.md?raw';
import guidePt from '../../../../docs/guia.md?raw';
import { getLang, setLang, t } from '../../i18n.js';
import { h } from '../dom.js';

let pendingAnchor = null;
/** Section to show the next time the guide is drawn (a tab id, which is also the section anchor). */
export const openGuideAt = (anchor) => { pendingAnchor = anchor; };

/** Tabs with a section in the guide. */
export const GUIDE_SECTIONS = new Set(['safra', 'monitor', 'anos', 'janela', 'cultivares', 'cenarios', 'local', 'modelo']);

const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function inline(text) {
  let s = escape(text);
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  s = s.replace(/&lt;(https?:\/\/[^\s&]+)&gt;/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, href) => {
    if (href.startsWith('#')) return `<a href="${href}" data-anchor="${href.slice(1)}">${label}</a>`;
    if (/\.md$/.test(href)) return `<a href="#" data-lang-switch="${/guia/.test(href) ? 'pt' : 'en'}">${label}</a>`;
    return `<a href="${href}" target="_blank" rel="noopener">${label}</a>`;
  });
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?!\w)/g, '$1<em>$2</em>');
  return s;
}

/** Markdown of the guide to HTML (only the constructs the guide uses). */
export function renderMarkdown(md) {
  const out = [], lines = md.replace(/\r/g, '').split('\n');
  let para = [], list = null, anchor = null;
  const flushPara = () => { if (para.length) out.push(`<p>${inline(para.join(' '))}</p>`); para = []; };
  const closeLists = (depth = 0) => { while (list && list.length > depth) out.push(`</li></${list.pop()}>`); if (list && !list.length) list = null; };
  for (const raw of lines) {
    const line = raw.trimEnd();
    const a = line.match(/^<a id="([^"]+)"><\/a>$/);
    if (a) { flushPara(); closeLists(); anchor = a[1]; continue; }
    const hd = line.match(/^(#{1,3}) (.*)$/);
    if (hd) {
      flushPara(); closeLists();
      const lvl = hd[1].length;
      if (lvl > 1) out.push(`<h${lvl}${anchor ? ` id="guide-${anchor}"` : ''}>${inline(hd[2])}</h${lvl}>`);
      anchor = null; continue;
    }
    const li = line.match(/^(\s*)(-|\d+\.) (.*)$/);
    if (li) {
      flushPara();
      const depth = Math.floor(li[1].length / 2) + 1, tag = li[2] === '-' ? 'ul' : 'ol';
      list ??= [];
      if (list.length < depth) { list.push(tag); out.push(`<${tag}><li>`); }
      else { closeLists(depth); out.push('</li><li>'); }
      out.push(inline(li[3]));
      continue;
    }
    if (!line.trim()) { flushPara(); continue; }
    if (list && /^\s+/.test(raw)) {                       // paragraph inside the list item of its indentation
      closeLists(Math.max(1, Math.floor(raw.match(/^\s*/)[0].length / 2)));
      out.push(`<p>${inline(line.trim())}</p>`); continue;
    }
    closeLists();
    para.push(line.trim());
  }
  flushPara(); closeLists();
  return out.join('\n');
}

const scrollToSection = (id, smooth = true) => {
  const target = document.getElementById(`guide-${id}`);
  if (target) target.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' });
};

export const guideTab = {
  id: 'guia', needsSite: false,
  get label() { return t('Guide', 'Guia'); },
  render(_, __, el) {
    const md = getLang() === 'pt' ? guidePt : guideEn;
    const title = md.match(/^# (.*)$/m)?.[1] ?? t('Guide', 'Guia');
    const body = h('article.card.guide');
    body.innerHTML = renderMarkdown(md);
    body.addEventListener('click', (e) => {
      const a = e.target.closest('a[data-anchor], a[data-lang-switch]');
      if (!a) return;
      e.preventDefault();
      if (a.dataset.anchor) scrollToSection(a.dataset.anchor);
      else setLang(a.dataset.langSwitch);
    });
    el.append(h('header.panel-head', h('div.titles', h('h1', title),
      h('p.lead', t('What each chart and number shows, how to read it and what to keep in mind. The same guide is on GitHub.',
        'O que cada gráfico e número mostra, como lê-los e quais cuidados tomar. O mesmo guia está no GitHub.'))),
      h('div.controls', h('a.button.secondary', { href: `https://github.com/fcoliveira-utfpr/emulator_crop/blob/main/docs/${getLang() === 'pt' ? 'guia' : 'guide'}.md`, target: '_blank', rel: 'noopener' }, t('Open on GitHub', 'Abrir no GitHub')))),
    body);
    if (pendingAnchor) { const id = pendingAnchor; pendingAnchor = null; requestAnimationFrame(() => scrollToSection(id, false)); }
  },
};
