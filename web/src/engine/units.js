// Description (English from cropemu.units, Portuguese), unit and display scale of the emulator outputs.

import { t } from '../i18n.js';
// `scale`/`unit` convert the model unit to the unit shown (e.g. kg/ha -> t/ha).

const T = { scale: 1e-3, unit: 't/ha' };
const DSSAT = {
  EDAT_dap: ["Emergence date", 'Emergência', 'dias após a semeadura', 'phenology'],
  ADAT_dap: ["Anthesis (flowering) date", 'Floração (antese)', 'dias após a semeadura', 'phenology'],
  MDAT_dap: ["Physiological maturity date", 'Maturidade fisiológica', 'dias após a semeadura', 'phenology'],
  HDAT_dap: ["Harvest date", 'Colheita', 'dias após a semeadura', 'phenology'],
  DWAP: ["Planting material weight", 'Massa do material de plantio', 'kg/ha', 'production'],
  CWAM: ["Tops (above-ground) dry weight at maturity", 'Biomassa aérea na maturidade', 'kg/ha', 'production', T],
  HWAM: ["Grain yield at maturity (dry)", 'Produtividade de grãos (seca) na maturidade', 'kg/ha', 'production', T],
  HWAH: ["Harvested grain yield (dry)", 'Produtividade de grãos colhida (seca)', 'kg/ha', 'production', T],
  PWAM: ["Pod weight at maturity", 'Massa de vagens na maturidade', 'kg/ha', 'production', T],
  HWUM: ["Unit grain weight", 'Massa unitária do grão', 'g/grão', 'production'],
  'H#AM': ["Grain number", 'Número de grãos', 'grãos/m²', 'production'],
  'H#UM': ["Grains per pod", 'Grãos por vagem', 'grãos/vagem', 'production'],
  HIAM: ["Harvest index at maturity", 'Índice de colheita', 'kg/kg', 'production'],
  LAIX: ["Maximum leaf area index", 'Índice de área foliar máximo', 'm²/m²', 'production'],
  PRCM: ["Rain, sowing to maturity", 'Chuva, semeadura à maturidade', 'mm', 'water'],
  ETCM: ["Evapotranspiration, sowing to maturity", 'Evapotranspiração, semeadura à maturidade', 'mm', 'water'],
  EPCM: ["Transpiration, sowing to maturity", 'Transpiração, semeadura à maturidade', 'mm', 'water'],
  ESCM: ["Soil evaporation, sowing to maturity", 'Evaporação do solo, semeadura à maturidade', 'mm', 'water'],
  ROCM: ["Runoff, sowing to maturity", 'Escoamento superficial, semeadura à maturidade', 'mm', 'water'],
  DRCM: ["Drainage, sowing to maturity", 'Drenagem, semeadura à maturidade', 'mm', 'water'],
  SWXM: ["Extractable soil water at maturity", 'Água extraível do solo na maturidade', 'mm', 'water'],
  CNAM: ["Tops nitrogen at maturity", 'Nitrogênio da parte aérea na maturidade', 'kg N/ha', 'nitrogen and carbon'],
  GNAM: ["Grain nitrogen at maturity", 'Nitrogênio dos grãos na maturidade', 'kg N/ha', 'nitrogen and carbon'],
  OCTAM: ["Total organic carbon at maturity", 'Carbono orgânico total na maturidade', 'kg C/ha', 'nitrogen and carbon'],
  OCAM: ["Soil organic carbon at maturity", 'Carbono orgânico do solo na maturidade', 'kg C/ha', 'nitrogen and carbon'],
  DMPEM: ["Dry matter per mm of evapotranspiration", 'Matéria seca por mm de evapotranspiração', 'kg/ha/mm', 'efficiency'],
  DMPTM: ["Dry matter per mm of transpiration", 'Matéria seca por mm de transpiração', 'kg/ha/mm', 'efficiency'],
  YPEM: ["Yield per mm of evapotranspiration", 'Produtividade por mm de evapotranspiração', 'kg/ha/mm', 'efficiency'],
  YPTM: ["Yield per mm of transpiration", 'Produtividade por mm de transpiração', 'kg/ha/mm', 'efficiency'],
  YPPM: ["Yield per mm of rain (computed from HWAM/PRCM)", 'Produtividade por mm de chuva (HWAM/PRCP)', 'kg/ha/mm', 'efficiency'],
  DMPPM: ["Dry matter per mm of rain (computed from CWAM/PRCM)", 'Matéria seca por mm de chuva (CWAM/PRCP)', 'kg/ha/mm', 'efficiency'],
  NDCH: ["Days from sowing to harvest", 'Dias da semeadura à colheita', 'd', 'phenology'],
  TMAXA: ["Mean maximum temperature, sowing to harvest", 'Temperatura máxima média, semeadura à colheita', '°C', 'cycle weather'],
  TMINA: ["Mean minimum temperature, sowing to harvest", 'Temperatura mínima média, semeadura à colheita', '°C', 'cycle weather'],
  SRADA: ["Mean solar radiation, sowing to harvest", 'Radiação solar média, semeadura à colheita', 'MJ/m²/d', 'cycle weather'],
  DAYLA: ["Mean day length, sowing to harvest", 'Fotoperíodo médio, semeadura à colheita', 'h', 'cycle weather'],
  CO2A: ["Mean CO2, sowing to harvest", 'CO₂ médio, semeadura à colheita', 'ppm', 'cycle weather'],
  PRCP: ["Rain, sowing to harvest", 'Chuva, semeadura à colheita', 'mm', 'water'],
  ETCP: ["Evapotranspiration, sowing to harvest", 'Evapotranspiração, semeadura à colheita', 'mm', 'water'],
  ESCP: ["Soil evaporation, sowing to harvest", 'Evaporação do solo, semeadura à colheita', 'mm', 'water'],
  EPCP: ["Transpiration, sowing to harvest", 'Transpiração, semeadura à colheita', 'mm', 'water'],
};

const AQUACROP = {
  Rain: ["Rain, whole simulation", 'Chuva, simulação inteira', 'mm', 'water'],
  ETo: ["Reference evapotranspiration, whole simulation", 'Evapotranspiração de referência, simulação inteira', 'mm', 'water'],
  GD: ["Growing degrees, whole simulation", 'Graus-dia, simulação inteira', '°C·d', 'cycle weather'],
  CO2: ["Mean CO2", 'CO₂ médio', 'ppm', 'cycle weather'],
  Irri: ["Irrigation, whole simulation", 'Irrigação, simulação inteira', 'mm', 'water'],
  Infilt: ["Infiltration, whole simulation", 'Infiltração, simulação inteira', 'mm', 'water'],
  Runoff: ["Runoff, whole simulation", 'Escoamento superficial, simulação inteira', 'mm', 'water'],
  Drain: ["Drainage, whole simulation", 'Drenagem, simulação inteira', 'mm', 'water'],
  E: ["Soil evaporation, whole simulation", 'Evaporação do solo, simulação inteira', 'mm', 'water'],
  'E/Ex': ["Relative soil evaporation", 'Evaporação relativa do solo', '%', 'water'],
  Tr: ["Transpiration, whole simulation", 'Transpiração, simulação inteira', 'mm', 'water'],
  TrW: ["Transpiration with weed competition", 'Transpiração com competição de plantas daninhas', 'mm', 'water'],
  'Tr/Trx': ["Relative transpiration", 'Transpiração relativa', '%', 'water'],
  SaltOut: ["Salt leached out of the root zone", 'Sais lixiviados da zona radicular', 'Mg/ha', 'water'],
  Cycle: ["Length of the crop cycle", 'Duração do ciclo', 'd', 'phenology'],
  TempStr: ["Temperature stress on biomass", 'Estresse térmico na biomassa', '%', 'stresses'],
  ExpStr: ["Water stress on canopy expansion", 'Estresse hídrico na expansão do dossel', '%', 'stresses'],
  StoStr: ["Water stress on stomata", 'Estresse hídrico nos estômatos', '%', 'stresses'],
  BioMass: ["Above-ground biomass", 'Biomassa aérea', 't/ha', 'production'],
  Brelative: ["Biomass relative to the unstressed crop", 'Biomassa relativa à cultura sem estresse', '%', 'production'],
  HI: ["Harvest index", 'Índice de colheita', '%', 'production'],
  'Y(dry)': ["Grain yield (dry)", 'Produtividade de grãos (seca)', 't/ha', 'production'],
  'Y(fresh)': ["Grain yield (fresh)", 'Produtividade de grãos (úmida)', 't/ha', 'production'],
  WPet: ["Water productivity (yield per evapotranspiration)", 'Produtividade da água (grão por evapotranspiração)', 'kg/m³', 'efficiency'],
  EMR_dap: ["Emergence date", 'Emergência', 'dias após a semeadura', 'phenology'],
  FLO_dap: ["Flowering date", 'Floração', 'dias após a semeadura', 'phenology'],
  YLD_dap: ["Start of yield formation", 'Início da formação da produção', 'dias após a semeadura', 'phenology'],
  MAT_dap: ["Physiological maturity date", 'Maturidade fisiológica', 'dias após a semeadura', 'phenology'],
  Rain_crop: ["Rain, crop period", 'Chuva, ciclo da cultura', 'mm', 'water'],
  Irri_crop: ["Irrigation, crop period", 'Irrigação, ciclo da cultura', 'mm', 'water'],
  Infilt_crop: ["Infiltration, crop period", 'Infiltração, ciclo da cultura', 'mm', 'water'],
  RO_crop: ["Runoff, crop period", 'Escoamento superficial, ciclo da cultura', 'mm', 'water'],
  Drain_crop: ["Drainage, crop period", 'Drenagem, ciclo da cultura', 'mm', 'water'],
  E_crop: ["Soil evaporation, crop period", 'Evaporação do solo, ciclo da cultura', 'mm', 'water'],
  Tr_crop: ["Transpiration, crop period", 'Transpiração, ciclo da cultura', 'mm', 'water'],
  ET_crop: ["Evapotranspiration, crop period", 'Evapotranspiração, ciclo da cultura', 'mm', 'water'],
  ETo_crop: ["Reference evapotranspiration, crop period", 'Evapotranspiração de referência, ciclo da cultura', 'mm', 'water'],
  GD_crop: ["Growing degrees, crop period", 'Graus-dia, ciclo da cultura', '°C·d', 'cycle weather'],
  StExp_mean: ["Mean water stress on canopy expansion, crop period", 'Estresse hídrico médio na expansão, ciclo', '%', 'stresses'],
  StSto_mean: ["Mean water stress on stomata, crop period", 'Estresse hídrico médio nos estômatos, ciclo', '%', 'stresses'],
  StSen_mean: ["Mean water stress on senescence, crop period", 'Estresse hídrico médio na senescência, ciclo', '%', 'stresses'],
  StTr_mean: ["Mean temperature stress on transpiration, crop period", 'Estresse térmico médio na transpiração, ciclo', '%', 'stresses'],
  CC_max: ["Maximum canopy cover", 'Cobertura máxima do dossel', '%', 'production'],
  Z_max: ["Maximum rooting depth", 'Profundidade máxima das raízes', 'm', 'production'],
};

/** Main outputs of each family (as in the example notebooks). */
export const KEYS = {
  dssat: { yield: 'HWAM', flowering: 'ADAT_dap', maturity: 'MDAT_dap', et: 'ETCM', rain: 'PRCM', biomass: 'CWAM', hi: 'HIAM' },
  aquacrop: { yield: 'Y(dry)', flowering: 'FLO_dap', maturity: 'MAT_dap', et: 'ET_crop', rain: 'Rain_crop', biomass: 'BioMass', hi: 'HI' },
};

/** Parameters of the sensitivity analysis (as in the example notebooks) and labels of every cultivar parameter. */
export const SENSITIVITY = {
  dssat: ['CSDL', 'PPSEN', 'LFMAX', 'SDPDV', 'SFDUR', 'WTPSD'],
  aquacrop: ['hio', 'wp', 'zmax', 'ccx', 'p_sto', 'kctr'],
};
const CULTIVAR = {
  mg: ['Maturity group', 'Grupo de maturidade'], CSDL: ['Critical short day length (h)', 'Fotoperíodo crítico (h)'],
  PPSEN: ['Photoperiod sensitivity (1/h)', 'Sensibilidade ao fotoperíodo (1/h)'],
  'EM-FL': ['Emergence to flowering (photothermal d)', 'Emergência à floração (dia fototermal)'],
  'FL-SH': ['Flowering to first pod (photothermal d)', 'Floração à 1ª vagem (dia fototermal)'],
  'FL-SD': ['Flowering to first seed (photothermal d)', 'Floração ao 1º grão (dia fototermal)'],
  'SD-PM': ['First seed to maturity (photothermal d)', 'Grão à maturidade (dia fototermal)'],
  'FL-LF': ['Flowering to end of leaf expansion (photothermal d)', 'Floração ao fim da expansão foliar (dia fototermal)'],
  LFMAX: ['Max. leaf photosynthesis (mg CO₂/m²/s)', 'Fotossíntese foliar máxima (mg CO₂/m²/s)'],
  SLAVR: ['Specific leaf area (cm²/g)', 'Área foliar específica (cm²/g)'], SIZLF: ['Max. leaf size (cm²)', 'Tamanho máximo da folha (cm²)'],
  WTPSD: ['Max. seed weight (g)', 'Massa máxima do grão (g)'], SFDUR: ['Seed filling duration (photothermal d)', 'Duração do enchimento de grãos (dia fototermal)'],
  SDPDV: ['Seeds per pod', 'Grãos por vagem'],
  cycle_factor: ['Cycle factor', 'Fator de ciclo'], gdd_maturity: ['Growing degrees to maturity (°C·d)', 'Graus-dia até a maturidade (°C·d)'],
  ccx: ['Max. canopy cover (–)', 'Cobertura máxima do dossel (–)'], cgc_gdd: ['Canopy growth factor (–)', 'Fator de crescimento do dossel (–)'],
  cdc_gdd: ['Canopy decline factor (–)', 'Fator de declínio do dossel (–)'], wp: ['Water productivity (g/m²)', 'Produtividade da água (g/m²)'],
  hio: ['Reference harvest index (%)', 'Índice de colheita de referência (%)'], zmax: ['Max. rooting depth (m)', 'Profundidade máxima das raízes (m)'],
  kctr: ['Crop coefficient (–)', 'Coeficiente de cultura (–)'], p_exp_upper: ['Upper expansion threshold (–)', 'Limite superior de expansão (–)'],
  p_exp_lower: ['Lower expansion threshold (–)', 'Limite inferior de expansão (–)'], p_sto: ['Stomatal closure threshold (–)', 'Limite de fechamento estomático (–)'],
  p_sen: ['Senescence threshold (–)', 'Limite de senescência (–)'],
};
/** Label of a cultivar parameter in the interface language. */
export const cultivarLabel = (k) => (CULTIVAR[k] ? t(...CULTIVAR[k]) : k);

const LEVEL_TEXT = { recommended: ['recommended', 'recomendada'], caution: ['caution', 'com cautela'], 'not recommended': ['not recommended', 'não recomendada'], unknown: ['—', '—'] };
export const LEVEL_COLORS = { recommended: '#0ca30c', caution: '#d99a00', 'not recommended': '#d03b3b', unknown: '#999' };
export const LEVEL_KEYS = ['recommended', 'caution', 'not recommended'];
export const levelLabel = (k) => t(...(LEVEL_TEXT[k] ?? LEVEL_TEXT.unknown));

const GROUPS = { production: 'produção', phenology: 'fenologia', water: 'água', stresses: 'estresses', efficiency: 'eficiência', 'nitrogen and carbon': 'nitrogênio e carbono', 'cycle weather': 'clima do ciclo', other: 'outros' };
export const GROUP_ORDER = Object.keys(GROUPS);
export const groupLabel = (g) => { const s = t(g, GROUPS[g] ?? g); return s[0].toUpperCase() + s.slice(1); };
const DAS = 'dias após a semeadura';

/** Metadata of every output of a card in the interface language: {name: {label, unit, group, scale, level, rmse, r2}}. */
export function outputMeta(card, family) {
  const table = family === 'aquacrop' ? AQUACROP : DSSAT;
  const names = [...card.outputs, ...Object.keys(card.derived ?? {})];
  return Object.fromEntries(names.map((name) => {
    const [en = name, pt = name, modelUnit = '', group = 'other', display] = table[name] ?? [];
    const unit = display?.unit ?? modelUnit;
    const a = card.acceptance?.[name] ?? {};
    return [name, { name, label: t(en, pt), modelUnit, group, scale: display?.scale ?? 1, unit: unit === DAS ? t('days after sowing', DAS) : unit,
      level: a.level ?? 'unknown', rmse: a.rmse, r2: a.r2, criterion: a.criterion }];
  }));
}
