const WEATHER_ALIASES = {

  date: ['date','data','dia','day','datetime'], srad: ['srad','rs','rad','radiation','solar_radiation','radiacao','radiacao_solar','rg'],

  tmax: ['tmax','t_max','temp_max','tx','maximum_temperature','temperatura_maxima','tmaxima'],

  tmin: ['tmin','t_min','temp_min','tn','minimum_temperature','temperatura_minima','tminima'],

  rain: ['rain','prec','precip','precipitation','prcp','rainfall','chuva','precipitacao','ppt'],

  rhum: ['rhum','rh','humidity','relative_humidity','umidade','umidade_relativa','ur'],

  wind: ['wind','u2','ws','wind_speed','vento','velocidade_do_vento'], dewp: ['dewp','tdew','td','dew_point','ponto_de_orvalho','orvalho'],

};

const SOIL_ALIASES = {

  top: ['top','upper','depth_top','topo','prof_topo','profundidade_topo','prof_sup','de'],

  bottom: ['bottom','lower','depth','depth_bottom','base','prof_base','profundidade','profundidade_base','prof_inf','ate'],

  clay: ['clay','argila'], sand: ['sand','areia'], silt: ['silt','silte'],

  soc: ['soc','oc','organic_carbon','carbono','carbono_organico','c_org','cot'],

  om: ['om','som','organic_matter','materia_organica','mo'], bdod: ['bdod','bd','bulk_density','density','densidade','ds'],

  ll: ['ll','wilting_point','wp1500','pmp','ponto_de_murcha'], dul: ['dul','field_capacity','fc','cc','capacidade_de_campo'],

};

const key = (s) => s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[([{].*?[)\]}]/g,' ').replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'');

function parseRows(text) {

  const first = text.split(/\r?\n/, 1)[0] ?? '';

  const delimiter = (first.match(/;/g)||[]).length > (first.match(/,/g)||[]).length ? ';' : (first.includes('\t') ? '\t' : ',');

  const rows=[]; let row=[], value='', quoted=false;

  for(let i=0;i<text.length;i++) { const ch=text[i]; if(ch==='"' && text[i+1]==='"' && quoted){value+='"';i++;} else if(ch==='"') quoted=!quoted; else if(ch===delimiter && !quoted){row.push(value);value='';} else if((ch==='\n'||ch==='\r')&&!quoted){ if(ch==='\r'&&text[i+1]==='\n')i++; row.push(value); if(row.some(v=>v.trim()))rows.push(row); row=[];value=''; } else value+=ch; }

  row.push(value); if(row.some(v=>v.trim()))rows.push(row);

  if(rows.length<2)throw new Error('O CSV precisa ter cabeçalho e pelo menos uma linha.');

  const headers=rows[0].map(v=>v.trim().replace(/^\uFEFF/,''));

  return rows.slice(1).map((cells)=>Object.fromEntries(headers.map((h,i)=>[h,(cells[i]??'').trim()])));

}

const findCol=(headers,aliases)=>headers.find(h=>{const k=key(h);return aliases.includes(k)||aliases.some(a=>a.length>2&&k.startsWith(`${a}_`));});

function number(value,decimalComma=false){if(value==null||value==='')return null;let s=String(value).trim();if(decimalComma)s=s.replace(/\./g,'').replace(',','.');else s=s.replace(',','.');const n=Number(s);return Number.isFinite(n)?n:null;}

function parseDate(value){const s=String(value).trim();let m=s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);if(m)return `${m[1]}-${m[2].padStart(2,'0')}-${m[3].padStart(2,'0')}`;m=s.match(/^(\d{1,2})[/. -](\d{1,2})[/. -](\d{4})$/);if(m)return `${m[3]}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`;return null;}

export function parseWeatherCsv(text){const rows=parseRows(text), headers=Object.keys(rows[0]), decimalComma=(text.split(/\r?\n/,1)[0].includes(';'));const mapped={};for(const [name,aliases] of Object.entries(WEATHER_ALIASES)){const col=findCol(headers,aliases);if(col)mapped[name]=col;}if(!mapped.date)throw new Error('Clima: inclua uma coluna de data (data/date).');for(const c of ['srad','tmax','tmin','rain'])if(!mapped[c])throw new Error(`Clima: falta a coluna ${c}.`);

 const weather=new Map();for(const row of rows){const date=parseDate(row[mapped.date]);if(!date)continue;const record={date,source:'usuário'};for(const c of ['srad','tmax','tmin','rain','rhum','wind','dewp'])if(mapped[c])record[c]=number(row[mapped[c]],decimalComma);if(record.srad!=null&&record.srad>1000)record.srad*=.001;else if(record.srad!=null&&record.srad>60)record.srad*=.0864;for(const c of ['tmax','tmin','dewp'])if(record[c]!=null&&record[c]>150)record[c]-=273.15;if(record.rhum!=null&&record.rhum<=1.5)record.rhum*=100;weather.set(date,record);}if(!weather.size)throw new Error('Não encontrei datas válidas no CSV de clima.');return {weather,rows:weather.size};}

export function parseSoilCsv(text){const rows=parseRows(text),headers=Object.keys(rows[0]),decimalComma=text.split(/\r?\n/,1)[0].includes(';'),mapped={};for(const [name,aliases]of Object.entries(SOIL_ALIASES)){const col=findCol(headers,aliases);if(col)mapped[name]=col;}if(!mapped.bottom||!mapped.clay||!mapped.sand||!(mapped.soc||mapped.om)||!mapped.bdod)throw new Error('Solo: informe base/profundidade, argila, areia, carbono orgânico (ou matéria orgânica) e densidade.');const profile=rows.map(row=>{const layer={};for(const c of Object.keys(mapped))layer[c]=number(row[mapped[c]],decimalComma);if(layer.top==null)layer.top=0;return layer;}).filter(r=>r.bottom!=null);profile.sort((a,b)=>a.top-b.top);if(!profile.length||profile.some(r=>r.bottom<=r.top))throw new Error('Perfil de solo inválido: confira as profundidades das camadas.');return profile;}

export function dateRange(sowing,start=-30,end=130){const date=new Date(`${sowing}T12:00:00Z`);if(Number.isNaN(date.getTime()))throw new Error('Informe a data de semeadura.');const out=[];for(let offset=start;offset<end;offset++){const d=new Date(date);d.setUTCDate(d.getUTCDate()+offset);out.push(d.toISOString().slice(0,10));}return out;}

export function mergeWeather(userWeather,remoteWeather,requiredDates){const merged=new Map(),filled={};for(const date of requiredDates){const user=userWeather?.get(date),remote=remoteWeather?.get(date);const value={date};for(const col of ['tmax','tmin','srad','rain','rhum','wind','dewp']){if(user?.[col]!=null){value[col]=user[col];value[`${col}_source`]='usuário';}else if(remote?.[col]!=null){value[col]=remote[col];value[`${col}_source`]='NASA POWER';filled[col]=(filled[col]??0)+1;}}merged.set(date,value);}return {weather:merged,filled};}

export async function fetchPower(lat,lon,start,end){const params='ALLSKY_SFC_SW_DWN,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,WS2M,T2MDEW';const url=new URL('https://power.larc.nasa.gov/api/temporal/daily/point');url.search=new URLSearchParams({parameters:params,community:'AG',latitude:Number(lat).toFixed(4),longitude:Number(lon).toFixed(4),start:start.replaceAll('-',''),end:end.replaceAll('-',''),format:'JSON'});const response=await fetch(url);if(!response.ok)throw new Error(`NASA POWER respondeu ${response.status}.`);const payload=await response.json();const p=payload?.properties?.parameter;if(!p)throw new Error('Resposta da NASA POWER sem dados diários.');const names={ALLSKY_SFC_SW_DWN:'srad',T2M_MAX:'tmax',T2M_MIN:'tmin',PRECTOTCORR:'rain',RH2M:'rhum',WS2M:'wind',T2MDEW:'dewp'};const paramObject=payload.properties.parameter;const first=Object.values(paramObject)[0];const dates=Object.keys(first??{}), weather=new Map();for(const dateKey of dates){const date=`${dateKey.slice(0,4)}-${dateKey.slice(4,6)}-${dateKey.slice(6,8)}`,record={date,source:'NASA POWER'};for(const [api,name]of Object.entries(names)){const v=paramObject[api]?.[dateKey];if(Number.isFinite(v)&&v>-900)record[name]=v;}weather.set(date,record);}return {weather,elevation:payload.geometry?.coordinates?.[2]??null};}

export function validateWeather(weather){const missing=[];for(const [date,row]of weather){for(const c of ['tmax','tmin','srad','rain'])if(!Number.isFinite(row[c]))missing.push(`${date}: ${c}`);if(Number.isFinite(row.tmax)&&Number.isFinite(row.tmin)&&row.tmin>row.tmax)missing.push(`${date}: Tmin > Tmax`);}return missing;}




