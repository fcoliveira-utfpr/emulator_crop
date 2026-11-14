// Description, unit and display scale of the emulator outputs (cropemu.units, in Portuguese).
// `scale`/`unit` convert the model unit to the unit shown (e.g. kg/ha -> t/ha).

const T = { scale: 1e-3, unit: 't/ha' };
const DSSAT = {
  EDAT_dap: ['Emergência', 'dias após a semeadura', 'fenologia'],
  ADAT_dap: ['Floração (antese)', 'dias após a semeadura', 'fenologia'],
  MDAT_dap: ['Maturidade fisiológica', 'dias após a semeadura', 'fenologia'],
  HDAT_dap: ['Colheita', 'dias após a semeadura', 'fenologia'],
  DWAP: ['Massa do material de plantio', 'kg/ha', 'produção'],
  CWAM: ['Biomassa aérea na maturidade', 'kg/ha', 'produção', T],
  HWAM: ['Produtividade de grãos (seca) na maturidade', 'kg/ha', 'produção', T],
  HWAH: ['Produtividade de grãos colhida (seca)', 'kg/ha', 'produção', T],
  PWAM: ['Massa de vagens na maturidade', 'kg/ha', 'produção', T],
  HWUM: ['Massa unitária do grão', 'g/grão', 'produção'],
  'H#AM': ['Número de grãos', 'grãos/m²', 'produção'],
  'H#UM': ['Grãos por vagem', 'grãos/vagem', 'produção'],
  HIAM: ['Índice de colheita', 'kg/kg', 'produção'],
  LAIX: ['Índice de área foliar máximo', 'm²/m²', 'produção'],
  PRCM: ['Chuva, semeadura à maturidade', 'mm', 'água'],
  ETCM: ['Evapotranspiração, semeadura à maturidade', 'mm', 'água'],
  EPCM: ['Transpiração, semeadura à maturidade', 'mm', 'água'],
  ESCM: ['Evaporação do solo, semeadura à maturidade', 'mm', 'água'],
  ROCM: ['Escoamento superficial, semeadura à maturidade', 'mm', 'água'],
  DRCM: ['Drenagem, semeadura à maturidade', 'mm', 'água'],
  SWXM: ['Água extraível do solo na maturidade', 'mm', 'água'],
  CNAM: ['Nitrogênio da parte aérea na maturidade', 'kg N/ha', 'nitrogênio e carbono'],
  GNAM: ['Nitrogênio dos grãos na maturidade', 'kg N/ha', 'nitrogênio e carbono'],
  OCTAM: ['Carbono orgânico total na maturidade', 'kg C/ha', 'nitrogênio e carbono'],
  OCAM: ['Carbono orgânico do solo na maturidade', 'kg C/ha', 'nitrogênio e carbono'],
  DMPEM: ['Matéria seca por mm de evapotranspiração', 'kg/ha/mm', 'eficiência'],
  DMPTM: ['Matéria seca por mm de transpiração', 'kg/ha/mm', 'eficiência'],
  YPEM: ['Produtividade por mm de evapotranspiração', 'kg/ha/mm', 'eficiência'],
  YPTM: ['Produtividade por mm de transpiração', 'kg/ha/mm', 'eficiência'],
  YPPM: ['Produtividade por mm de chuva (HWAM/PRCP)', 'kg/ha/mm', 'eficiência'],
  DMPPM: ['Matéria seca por mm de chuva (CWAM/PRCP)', 'kg/ha/mm', 'eficiência'],
  NDCH: ['Dias da semeadura à colheita', 'd', 'fenologia'],
  TMAXA: ['Temperatura máxima média, semeadura à colheita', '°C', 'clima do ciclo'],
  TMINA: ['Temperatura mínima média, semeadura à colheita', '°C', 'clima do ciclo'],
  SRADA: ['Radiação solar média, semeadura à colheita', 'MJ/m²/d', 'clima do ciclo'],
  DAYLA: ['Fotoperíodo médio, semeadura à colheita', 'h', 'clima do ciclo'],
  CO2A: ['CO₂ médio, semeadura à colheita', 'ppm', 'clima do ciclo'],
  PRCP: ['Chuva, semeadura à colheita', 'mm', 'água'],
  ETCP: ['Evapotranspiração, semeadura à colheita', 'mm', 'água'],
  ESCP: ['Evaporação do solo, semeadura à colheita', 'mm', 'água'],
  EPCP: ['Transpiração, semeadura à colheita', 'mm', 'água'],
};

const AQUACROP = {
  Rain: ['Chuva, simulação inteira', 'mm', 'água'],
  ETo: ['Evapotranspiração de referência, simulação inteira', 'mm', 'água'],
  GD: ['Graus-dia, simulação inteira', '°C·d', 'clima do ciclo'],
  CO2: ['CO₂ médio', 'ppm', 'clima do ciclo'],
  Irri: ['Irrigação, simulação inteira', 'mm', 'água'],
  Infilt: ['Infiltração, simulação inteira', 'mm', 'água'],
  Runoff: ['Escoamento superficial, simulação inteira', 'mm', 'água'],
  Drain: ['Drenagem, simulação inteira', 'mm', 'água'],
  E: ['Evaporação do solo, simulação inteira', 'mm', 'água'],
  'E/Ex': ['Evaporação relativa do solo', '%', 'água'],
  Tr: ['Transpiração, simulação inteira', 'mm', 'água'],
  TrW: ['Transpiração com competição de plantas daninhas', 'mm', 'água'],
  'Tr/Trx': ['Transpiração relativa', '%', 'água'],
  SaltOut: ['Sais lixiviados da zona radicular', 'Mg/ha', 'água'],
  Cycle: ['Duração do ciclo', 'd', 'fenologia'],
  TempStr: ['Estresse térmico na biomassa', '%', 'estresses'],
  ExpStr: ['Estresse hídrico na expansão do dossel', '%', 'estresses'],
  StoStr: ['Estresse hídrico nos estômatos', '%', 'estresses'],
  BioMass: ['Biomassa aérea', 't/ha', 'produção'],
  Brelative: ['Biomassa relativa à cultura sem estresse', '%', 'produção'],
  HI: ['Índice de colheita', '%', 'produção'],
  'Y(dry)': ['Produtividade de grãos (seca)', 't/ha', 'produção'],
  'Y(fresh)': ['Produtividade de grãos (úmida)', 't/ha', 'produção'],
  WPet: ['Produtividade da água (grão por evapotranspiração)', 'kg/m³', 'eficiência'],
  EMR_dap: ['Emergência', 'dias após a semeadura', 'fenologia'],
  FLO_dap: ['Floração', 'dias após a semeadura', 'fenologia'],
  YLD_dap: ['Início da formação da produção', 'dias após a semeadura', 'fenologia'],
  MAT_dap: ['Maturidade fisiológica', 'dias após a semeadura', 'fenologia'],
  Rain_crop: ['Chuva, ciclo da cultura', 'mm', 'água'],
  Irri_crop: ['Irrigação, ciclo da cultura', 'mm', 'água'],
  Infilt_crop: ['Infiltração, ciclo da cultura', 'mm', 'água'],
  RO_crop: ['Escoamento superficial, ciclo da cultura', 'mm', 'água'],
  Drain_crop: ['Drenagem, ciclo da cultura', 'mm', 'água'],
  E_crop: ['Evaporação do solo, ciclo da cultura', 'mm', 'água'],
  Tr_crop: ['Transpiração, ciclo da cultura', 'mm', 'água'],
  ET_crop: ['Evapotranspiração, ciclo da cultura', 'mm', 'água'],
  ETo_crop: ['Evapotranspiração de referência, ciclo da cultura', 'mm', 'água'],
  GD_crop: ['Graus-dia, ciclo da cultura', '°C·d', 'clima do ciclo'],
  StExp_mean: ['Estresse hídrico médio na expansão, ciclo', '%', 'estresses'],
  StSto_mean: ['Estresse hídrico médio nos estômatos, ciclo', '%', 'estresses'],
  StSen_mean: ['Estresse hídrico médio na senescência, ciclo', '%', 'estresses'],
  StTr_mean: ['Estresse térmico médio na transpiração, ciclo', '%', 'estresses'],
  CC_max: ['Cobertura máxima do dossel', '%', 'produção'],
  Z_max: ['Profundidade máxima das raízes', 'm', 'produção'],
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
export const CULTIVAR_LABELS = {
  mg: 'Grupo de maturidade', CSDL: 'Fotoperíodo crítico (h)', PPSEN: 'Sensibilidade ao fotoperíodo (1/h)',
  'EM-FL': 'Emergência à floração (dia fototermal)', 'FL-SH': 'Floração à 1ª vagem (dia fototermal)',
  'FL-SD': 'Floração ao 1º grão (dia fototermal)', 'SD-PM': 'Grão à maturidade (dia fototermal)',
  'FL-LF': 'Floração ao fim da expansão foliar (dia fototermal)', LFMAX: 'Fotossíntese foliar máxima (mg CO₂/m²/s)',
  SLAVR: 'Área foliar específica (cm²/g)', SIZLF: 'Tamanho máximo da folha (cm²)', WTPSD: 'Massa máxima do grão (g)',
  SFDUR: 'Duração do enchimento de grãos (dia fototermal)', SDPDV: 'Grãos por vagem',
  cycle_factor: 'Fator de ciclo', gdd_maturity: 'Graus-dia até a maturidade (°C·d)', ccx: 'Cobertura máxima do dossel (–)',
  cgc_gdd: 'Fator de crescimento do dossel (–)', cdc_gdd: 'Fator de declínio do dossel (–)', wp: 'Produtividade da água (g/m²)',
  hio: 'Índice de colheita de referência (%)', zmax: 'Profundidade máxima das raízes (m)', kctr: 'Coeficiente de cultura (–)',
  p_exp_upper: 'Limite superior de expansão (–)', p_exp_lower: 'Limite inferior de expansão (–)',
  p_sto: 'Limite de fechamento estomático (–)', p_sen: 'Limite de senescência (–)',
};

export const LEVELS = {
  recommended: { label: 'recomendada', color: '#0ca30c' },
  caution: { label: 'com cautela', color: '#d99a00' },
  'not recommended': { label: 'não recomendada', color: '#d03b3b' },
  unknown: { label: '—', color: '#999' },
};

/** Metadata of every output of a card: {name: {label, unit, group, scale, level, rmse, r2}}. */
export function outputMeta(card, family) {
  const table = family === 'aquacrop' ? AQUACROP : DSSAT;
  const names = [...card.outputs, ...Object.keys(card.derived ?? {})];
  return Object.fromEntries(names.map((name) => {
    const [label = name, modelUnit = '', group = 'outros', display] = table[name] ?? [];
    const a = card.acceptance?.[name] ?? {};
    return [name, { name, label, modelUnit, group, scale: display?.scale ?? 1, unit: display?.unit ?? modelUnit,
      level: a.level ?? 'unknown', rmse: a.rmse, r2: a.r2, criterion: a.criterion }];
  }));
}
