// The emulator: what it was trained on, validation of every output, training domain.

import { LEVEL_COLORS, LEVEL_KEYS, levelLabel } from '../../engine/units.js';
import { t } from '../../i18n.js';
import { draw, figure, Plot, C } from '../charts.js';
import { header, levelBadge, table } from '../common.js';
import { auto, fmt, h } from '../dom.js';

export const modelTab = {
  id: 'modelo', needsSite: false,
  get label() { return t('About the model', 'Sobre o modelo'); },
  render(ctx, _, el) {
    const { emu } = ctx, card = emu.card, tr = card.training;
    const outputs = Object.values(emu.meta).filter((m) => Number.isFinite(m.r2)).sort((a, b) => b.r2 - a.r2);
    el.append(header(card.model.replace(' (official executable)', ''),
      t(`Neural network trained on ${fmt(tr.seasons, 0)} seasons simulated with the official executable at ${fmt(tr.points, 0)} points of the world soybean area. Weather: ${tr.weather}. Soil: ${tr.soil}. Validation: ${card.validation}.`,
        `Rede neural treinada com ${fmt(tr.seasons, 0)} safras simuladas pelo executável oficial em ${fmt(tr.points, 0)} pontos da área mundial de soja. Clima: ${tr.weather}. Solo: ${tr.soil}. Validação: ${card.validation}.`)));
    el.append(h('div.tiles',
      h('div.tile', h('span.t-label', t('Inputs', 'Entradas')), h('span.t-value', card.inputs.length), h('span.t-sub', t('weather in 5 windows, soil, site, cultivar, management', 'clima em 5 janelas, solo, local, cultivar, manejo'))),
      h('div.tile', h('span.t-label', t('Outputs', 'Saídas')), h('span.t-value', Object.keys(emu.meta).length), h('span.t-sub', LEVEL_KEYS.map((k) => `${outputs.filter((o) => o.level === k).length} ${levelLabel(k)}`).join(' · '))),
      h('div.tile', h('span.t-label', 'Cultivar'), h('span.t-value', card.cultivar.length, h('small', ` ${t('parameters', 'parâmetros')}`)),
        h('span.t-sub', emu.family === 'dssat' ? t('CROPGRO coefficients by maturity group', 'coeficientes do CROPGRO por grupo de maturidade') : t('AquaCrop crop parameters + cycle in growing degrees', 'parâmetros de cultura do AquaCrop + ciclo em graus-dia')))));

    const f = figure(t('Quality of each output in the spatial validation', 'Qualidade de cada saída na validação espacial'),
      t('R² on 5° blocks the network did not see in training. Colour: acceptance level (recommended: dates with error ≤ 5 days, other outputs with error < 0.25 of the within-site SD; caution: relative error < 0.5).',
        'R² com blocos de 5° que a rede não viu no treino. Cor: nível de aceitação (recomendada: datas com erro ≤ 5 dias, demais com erro < 0,25 do desvio entre anos no local; com cautela: erro relativo < 0,5).'),
      { wide: true, legend: LEVEL_KEYS.map((k) => [levelLabel(k), LEVEL_COLORS[k], 'dot']) });
    el.append(f.card);
    const ylab = (o) => `${o.label} (${o.name})`;
    draw(f.body, { height: Math.max(300, outputs.length * 16 + 40), marginLeft: 300, x: { label: t('R² in the validation', 'R² na validação'), domain: [0, 1.02], grid: true }, y: { label: null, domain: outputs.map(ylab), grid: false }, marks: [
      Plot.ruleY(outputs, { y: ylab, x1: 0, x2: (o) => Math.max(0, o.r2), stroke: 'currentColor', strokeOpacity: 0.15 }),
      Plot.dot(outputs, { y: ylab, x: (o) => Math.max(0, o.r2), r: 5, fill: (o) => LEVEL_COLORS[o.level], stroke: 'var(--surface)', strokeWidth: 1.5,
        tip: true, title: (o) => `${o.label}\nR² ${fmt(o.r2, 3)} · RMSE ${auto(o.rmse * o.scale)} ${o.unit}\n${levelLabel(o.level)} (${o.criterion ?? ''})` }),
    ] });

    el.append(h('section.card', h('h2', t('Outputs, units and validation error', 'Saídas, unidades e erro de validação')), table(Object.values(emu.meta), [
      [t('Code', 'Código'), (m) => h('code', m.name)], [t('Description', 'Descrição'), 'label'], [t('Unit', 'Unidade'), 'unit'], [t('Acceptance', 'Aceitação'), (m) => levelBadge(m.level)],
      ['RMSE', (m) => (Number.isFinite(m.rmse) ? auto(m.rmse * m.scale) : '—'), 'num'], ['R²', (m) => (Number.isFinite(m.r2) ? fmt(m.r2, 3) : '—'), 'num']])));

    // where the last single season sits in the training domain
    const last = ctx.cached?.('safra');
    const f2 = figure(t('Where your season sits in the training domain', 'Onde a sua safra está no domínio de treino'), last?.main?.inputs
      ? t('Position of each input of the last season computed (tab “One season”) in the training range: 0 = minimum, 1 = maximum. Blue band: 0.5–99.5 % of the training seasons.', 'Posição de cada entrada da última safra calculada (aba “Uma safra”) na faixa do treino: 0 = mínimo, 1 = máximo. Faixa azul: 0,5–99,5 % das safras de treino.')
      : t('Compute a season in the “One season” tab to see the position of each input.', 'Calcule uma safra na aba “Uma safra” para ver a posição de cada entrada.'), { wide: true });
    el.append(f2.card);
    if (last?.main?.inputs) {
      const pos = card.inputs.map((name) => {
        const d = card.domain[name], x = last.main.inputs[name], w = d.max - d.min || 1;
        return { name, x, p: d.max === d.min ? 0.5 : (x - d.min) / w, q0: (d.q005 - d.min) / w, q1: (d.q995 - d.min) / w, fixed: d.max === d.min, d };
      }).filter((r) => !r.fixed);
      draw(f2.body, { height: pos.length * 13 + 40, marginLeft: 110, x: { label: t('position in the training range', 'posição na faixa de treino'), domain: [-0.1, 1.1], grid: true }, y: { label: null, domain: pos.map((r) => r.name), grid: false, tickSize: 0 }, marks: [
        Plot.ruleY(pos, { y: 'name', x1: 0, x2: 1, stroke: 'currentColor', strokeOpacity: 0.12, strokeWidth: 6 }),
        Plot.ruleY(pos, { y: 'name', x1: 'q0', x2: 'q1', stroke: C.blue, strokeOpacity: 0.35, strokeWidth: 6 }),
        Plot.dot(pos, { y: 'name', x: (r) => Math.max(-0.1, Math.min(1.1, r.p)), r: 3.5, fill: (r) => (r.p < 0 || r.p > 1 ? C.red : r.p < r.q0 || r.p > r.q1 ? C.yellow : 'currentColor'),
          tip: true, title: (r) => `${r.name} = ${auto(r.x)}\n${t('training', 'treino')}: ${auto(r.d.min)} ${t('to', 'a')} ${auto(r.d.max)} (0.5–99.5 %: ${auto(r.d.q005)} ${t('to', 'a')} ${auto(r.d.q995)})` }),
      ] });
    }
    el.append(h('section.card', h('h2', t('What the emulator does not know', 'O que o emulador não sabe')), h('ul.plain',
      h('li', t('It reproduces the crop model, not the field: the errors of DSSAT/AquaCrop are inherited and the model was not calibrated for each site.', 'Reproduz o modelo de cultura, não a lavoura: os erros do DSSAT/AquaCrop são herdados e o modelo não foi calibrado para cada local.')),
      h('li', t('Fixed in training: 30 plants/m², 50 cm rows, no nitrogen stress, half of the available water 30 days before sowing. Pests, diseases and weeds are not included.', 'Fixos no treino: 30 plantas/m², 50 cm entre linhas, sem estresse de nitrogênio, metade da água disponível 30 dias antes da semeadura. Pragas, doenças e plantas daninhas não entram.')),
      h('li', t('“No water stress” is the water balance switched off, not an irrigation amount.', '“Sem estresse hídrico” é o balanço de água desligado, não uma lâmina de irrigação.')),
      h('li', t('Check the seasons outside the domain and prefer the recommended or caution outputs.', 'Confira as safras fora do domínio e prefira as saídas recomendadas ou com cautela.')))));
  },
};
