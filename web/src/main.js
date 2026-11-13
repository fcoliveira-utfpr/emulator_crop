import { fetchPower, dateRange, mergeWeather, parseSoilCsv, parseWeatherCsv, validateWeather } from './data.js';
import * as ort from 'onnxruntime-web';
import './style.css';

const $ = (id) => document.getElementById(id);
const modelNames = { 'dssat-soybean-v1': 'DSSAT CROPGRO · soja', 'aquacrop-soybean-v1': 'AquaCrop · soja' };
let activeSession;
$('weather-file').addEventListener('change', (e) => { $('weather-name').textContent=e.target.files[0]?.name??'Tmax, Tmin, radiação e chuva por dia'; });
$('soil-file').addEventListener('change', (e) => { $('soil-name').textContent=e.target.files[0]?.name??'Camadas com textura e carbono orgânico'; });

$('estimate-form').addEventListener('submit', async (event) => {
  event.preventDefault(); const model=$('model').value, button=$('load-button'), notice=$('notice'); button.disabled=true;
  try {
    const sowing=$('sowing').value, lat=$('latitude').value, lon=$('longitude').value;
    if(!sowing) throw new Error('Informe a data de semeadura.');
    if(!lat||!lon) throw new Error('Informe latitude e longitude para buscar os dados climáticos que faltarem.');
    const dates=dateRange(sowing), userWeatherFile=$('weather-file').files[0];
    let userWeather=new Map();
    if(userWeatherFile) userWeather=parseWeatherCsv(await userWeatherFile.text()).weather;
    let merged=mergeWeather(userWeather,null,dates);
    const missingBefore=validateWeather(merged.weather);
    if(missingBefore.length){
      $('model-state').textContent='Buscando dados climáticos faltantes…';
      $('model-info').textContent='Consultando NASA POWER para preencher somente os dias e variáveis ausentes.';
      const fetched=await fetchPower(lat,lon,dates[0],dates.at(-1));
      merged=mergeWeather(userWeather,fetched.weather,dates);
    }
    const missing=validateWeather(merged.weather);
    if(missing.length) throw new Error(`Clima ainda incompleto (${missing.slice(0,3).join('; ')}${missing.length>3?'…':''}). Envie dados para essas datas ou revise a fonte.`);
    const soilFile=$('soil-file').files[0];
    if(soilFile) parseSoilCsv(await soilFile.text());
    $('model-state').textContent='Carregando modelo ONNX…'; $('model-info').textContent='Dados climáticos prontos; carregando o modelo no navegador.';
    const base=`${import.meta.env.BASE_URL}models/${model}`;
    const [cardResponse,session]=await Promise.all([fetch(`${base}/card.json`),ort.InferenceSession.create(`${base}/model.onnx`,{executionProviders:['wasm']})]);
    if(!cardResponse.ok) throw new Error(`Não foi possível carregar os metadados (${cardResponse.status}).`);
    const card=await cardResponse.json(); activeSession={card,session}; showModel(card,session,model);
    $('model-state').textContent='Clima validado · modelo carregado';
    $('model-info').textContent=`${dates.length} dias · ${Object.values(merged.filled).reduce((a,b)=>a+b,0)} valores completados pela NASA POWER · ${card.inputs.length} entradas do modelo`;
    const soilText=soilFile?'Perfil de solo CSV reconhecido.':'Solo: a integração automática com SoilGrids será implementada na próxima etapa.';
    notice.textContent=`Clima validado. ${soilText} Ainda estamos implementando o preparo das entradas para liberar o cálculo da estimativa.`;
  } catch(error) {
    $('model-state').textContent='Não foi possível preparar os dados'; $('model-info').textContent=error.message; notice.textContent='Seus arquivos e valores continuam selecionados; corrija os campos indicados e tente novamente.';
  } finally { button.disabled=false; }
});

function showModel(card,session,model){const result=$('results');$('result-title').textContent=modelNames[model];$('result-copy').textContent=`Modelo carregado. A composição das ${card.inputs.length} entradas ainda será habilitada após o preparo completo do clima e do perfil de solo.`;const acceptance=card.acceptance??{};$('outputs').replaceChildren(...card.outputs.slice(0,8).map(name=>{const item=document.createElement('div');item.className='output-item';const title=document.createElement('strong');title.textContent=name;const level=document.createElement('span');level.textContent=acceptance[name]?.level??'saída do modelo';item.append(title,level);return item;}));result.hidden=false;result.dataset.inputName=session.inputNames[0];result.dataset.outputName=session.outputNames[0];}
export function getLoadedEmulator(){return activeSession;}

