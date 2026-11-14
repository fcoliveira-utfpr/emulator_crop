// Cultivars: maturity groups (DSSAT) or cycle lengths (AquaCrop), and one-at-a-time parameter sensitivity.

import { typicalMg } from '../../engine/season.js';
import { CULTIVAR_LABELS, SENSITIVITY } from '../../engine/units.js';
import { C, draw, figure, Plot, SERIES } from '../charts.js';
import { exporter, grid, header, levelNote, table, variableSelect } from '../common.js';
import { auto, fmt, h, numberList, quantile } from '../dom.js';

const POINTS = 9;

export const cultivarsTab = {
  id: 'cultivares', label: 'Cultivares', needsSite: true,
  defaults(ctx) {
    if (ctx.emu.family === 'dssat') {
      const mg = Math.round(typicalMg(ctx.emu.card, ctx.site.lat) * 2) / 2;
      return { variants: [-2, -1, 0, 1, 2].map((d) => mg + d).filter((g) => g >= -2 && g <= 10).join(' '), params: [...SENSITIVITY.dssat] };
    }
    return { variants: '0.8 0.9 1 1.1 1.2', params: [...SENSITIVITY.aquacrop] };
  },

  async compute(ctx) {
    const st = ctx.tabState('cultivares', this.defaults(ctx)), dssat = ctx.emu.family === 'dssat', card = ctx.emu.card;
    if (!ctx.years.length) throw new Error('Nenhum ano do período tem clima completo.');
    const variants = numberList(st.variants).slice(0, 8);
    if (!variants.length) throw new Error(dssat ? 'Informe ao menos um grupo de maturidade.' : 'Informe ao menos um fator de ciclo.');
    const vSeasons = variants.flatMap((v, i) => {
      const cultivar = dssat ? ctx.cultivar({ mg: v }) : ctx.cultivar({ factor: v });
      return ctx.years.map((y) => ctx.season(y, { cultivar, variant: i }));
    });
    const base = ctx.cultivar();
    const sens = st.params.filter((p) => card.cultivar.includes(p)).flatMap((p) => {
      const d = card.domain[p];
      return Array.from({ length: POINTS }, (_, i) => d.q005 + (d.q995 - d.q005) * i / (POINTS - 1))
        .flatMap((x) => ctx.years.map((y) => ctx.season(y, { cultivar: { ...base, [p]: x }, param: p, x })));
    });
    const rows = await ctx.run([...vSeasons, ...sens]);
    return { variants, rows: rows.slice(0, vSeasons.length), sens: rows.slice(vSeasons.length), base, st };
  },

  render(ctx, { variants, rows, sens, base, st }, el) {
    const { emu } = ctx, meta = emu.meta, k = emu.keys, V = ctx.variable, mv = meta[V], dssat = emu.family === 'dssat';
    const name = (v) => (dssat ? `GM ${fmt(v, 1)}` : `ciclo ×${fmt(v, 2)}`);
    const names = variants.map(name);
    const data = rows.map((r) => ({ variant: names[r.variant], year: r.year, flo: r.outputs[k.flowering], mat: r.outputs[k.maturity], v: r.outputs[V] * mv.scale, ood: r.outOfDomain.length > 0 }));
    const s = ctx.tabState('cultivares');
    const variantsInput = h('label.inline', h('span', dssat ? 'Grupos de maturidade' : 'Fatores de ciclo'),
      h('input', { type: 'text', value: st.variants, style: { width: '13em' }, onchange: (e) => { s.variants = e.target.value; ctx.refresh(); } }));
    el.append(header('Cultivares',
      dssat ? `Grupos de maturidade semeados na mesma data, ${ctx.years[0]}–${ctx.years.at(-1)}. Cada GM usa os coeficientes padrão do CROPGRO (com os seus ajustes de parâmetros, se houver). GMs maiores florescem e amadurecem mais tarde (fotoperíodo).`
        : `Ciclos mais curtos ou longos (fator sobre os graus-dia até a maturidade; treino: 0,75–1,25), semeados na mesma data, ${ctx.years[0]}–${ctx.years.at(-1)}.`,
      [variantsInput, variableSelect(ctx)],
      exporter(`cultivares_${emu.card.name}.csv`, [...rows.map((r) => ({ analise: 'variante', variante: names[r.variant], ano: r.year, ...Object.fromEntries(Object.keys(meta).map((n) => [n, r.outputs[n] * meta[n].scale])) })),
        ...sens.map((r) => ({ analise: 'sensibilidade', parametro: r.param, valor: r.x, ano: r.year, ...Object.fromEntries(Object.keys(meta).map((n) => [n, r.outputs[n] * meta[n].scale])) }))])));
    const note = levelNote(ctx, V); if (note) el.append(note);

    const colors = names.map((_, i) => SERIES[i % SERIES.length]);
    const box = (title, key, unit) => {
      const f = figure(title, null);
      draw(f.body, { x: { label: null, domain: names }, y: { label: unit, grid: true }, color: { domain: names, range: colors }, marks: [
        Plot.boxY(data.filter((d) => Number.isFinite(d[key])), { x: 'variant', y: key, fill: 'variant', fillOpacity: 0.35, stroke: 'variant', r: 2.5 }),
        Plot.tip(data, Plot.pointer({ x: 'variant', y: key, title: (d) => `${d.variant}, ${d.year}\n${auto(d[key])} ${unit}` })),
      ] });
      return f.card;
    };
    el.append(grid(box('Floração', 'flo', 'dias após a semeadura'), box('Maturidade', 'mat', 'dias após a semeadura'), box(mv.label, 'v', mv.unit)));

    const summary = names.map((n) => {
      const d = data.filter((x) => x.variant === n), v = d.map((x) => x.v);
      return { n, flo: quantile(d.map((x) => x.flo), 0.5), mat: quantile(d.map((x) => x.mat), 0.5), p10: quantile(v, 0.1), p50: quantile(v, 0.5), p90: quantile(v, 0.9), ood: d.filter((x) => x.ood).length };
    });
    el.append(h('section.card', h('h2', 'Resumo por cultivar'), table(summary, [
      ['Cultivar', 'n'], ['Floração (d)', (r) => fmt(r.flo, 0), 'num'], ['Maturidade (d)', (r) => fmt(r.mat, 0), 'num'],
      [`${mv.label}: 10 %`, (r) => auto(r.p10), 'num'], ['mediana', (r) => auto(r.p50), 'num'], ['90 %', (r) => auto(r.p90), 'num'], ['Safras fora do domínio', 'ood', 'num'],
    ])));

    // sensitivity
    const params = emu.card.cultivar.filter((p) => !(dssat && p === 'mg'));
    const picker = h('div.param-picker', params.map((p) => h('label.check', h('input', { type: 'checkbox', checked: st.params.includes(p), onchange: (e) => {
      s.params = e.target.checked ? [...new Set([...s.params, p])] : s.params.filter((x) => x !== p); ctx.refresh();
    } }), h('span', { title: CULTIVAR_LABELS[p] }, p))));
    const sec = h('section.card', h('h2', 'Sensibilidade a cada parâmetro'),
      h('p.hint', `Um parâmetro por vez ao longo da faixa de 0,5–99,5 % do treino (${POINTS} valores), os demais no valor atual; linha: mediana dos ${ctx.years.length} anos; faixa: 25–75 %. Tracejado: valor atual do cultivar.`), picker);
    const box2 = h('div.small-multiples');
    sec.append(box2);
    el.append(sec);
    const curves = st.params.filter((p) => emu.card.cultivar.includes(p)).map((p) => {
      const xs = [...new Set(sens.filter((r) => r.param === p).map((r) => r.x))];
      return { p, pts: xs.map((x) => { const v = sens.filter((r) => r.param === p && r.x === x).map((r) => r.outputs[V] * mv.scale); return { x, p25: quantile(v, 0.25), p50: quantile(v, 0.5), p75: quantile(v, 0.75) }; }) };
    });
    const all = curves.flatMap((c) => c.pts.flatMap((q) => [q.p25, q.p75])).filter(Number.isFinite);
    const yDomain = all.length ? [Math.min(...all), Math.max(...all)] : undefined;
    for (const { p, pts } of curves) {
      const f = figure(CULTIVAR_LABELS[p] ?? p, null);
      box2.append(f.card);
      draw(f.body, { height: 200, marginLeft: 44, x: { label: p, ticks: 4 }, y: { label: mv.unit, domain: yDomain, ticks: 4 }, marks: [
        Plot.areaY(pts, { x: 'x', y1: 'p25', y2: 'p75', fill: C.blue, fillOpacity: 0.2 }),
        Plot.lineY(pts, { x: 'x', y: 'p50', stroke: C.blue, strokeWidth: 2 }),
        Plot.ruleX([base[p]], { stroke: 'currentColor', strokeOpacity: 0.5, strokeDasharray: '4,3' }),
        Plot.tip(pts, Plot.pointerX({ x: 'x', y: 'p50', title: (d) => `${p} = ${auto(d.x)}\nmediana ${auto(d.p50)} ${mv.unit}\n25–75 %: ${auto(d.p25)}–${auto(d.p75)}` })),
      ] });
    }
    if (!curves.length) box2.append(h('p.hint', 'Marque ao menos um parâmetro.'));
  },
};
