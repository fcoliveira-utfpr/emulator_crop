# CropEmu guide to reading each tab

[CropEmu](https://fcoliveira-utfpr.github.io/emulator_crop/) simulates soybean seasons with emulators of two crop models, DSSAT CROPGRO-Soybean and FAO AquaCrop 7.3. This guide explains, tab by tab, what each chart and number shows, how to read it and what to keep in mind.

One rule applies to every tab: **the result is what the crop model would simulate for that weather, soil and cultivar, not a measurement of the field**. Pests, diseases, weeds, nitrogen and the actual management are outside it. Use CropEmu to compare options (dates, cultivars, years, scenarios) and to understand risk, not to predict the exact yield of a field.

[Versão em português](guia.md)

**Contents**

- [Getting started](#inicio)
- [One season](#safra)
- [Crop monitoring](#monitor)
- [Many years](#anos)
- [Sowing window](#janela)
- [Cultivars](#cultivares)
- [Climate scenarios](#cenarios)
- [Site](#local)
- [About the model](#modelo)
- [Terms used in the app](#termos)
- [Frequently asked questions](#faq)

<a id="inicio"></a>

## Getting started

The sidebar defines the season; the tabs show different analyses of the same setup.

1. **Model.** DSSAT or AquaCrop. They simulate soybean in different ways:
   - DSSAT simulates photosynthesis, photoperiod and maturity groups;
   - AquaCrop is driven by transpiration and canopy cover, with the cycle in growing degrees.

   The difference between them is a measure of the uncertainty of the crop models themselves. When both agree, the conclusion is more robust.
2. **Site and data.**
   - **Where to choose the site:** an example site, a point on the map, the coordinates or your location.
   - **Default data sources:** the daily weather comes from NASA POWER (since 1984) and the soil from SoilGrids 2.0, the same sources used in training.
   - **Your data:** under *Use my data*, you can upload a daily weather spreadsheet and a soil profile. Your values take precedence, and NASA POWER only fills the missing days and columns.
   - **Point without soil in SoilGrids:** over water, urban areas and outside its maps, SoilGrids has no soil. The app says so and opens *Use my data* with the soil profile field highlighted; once the spreadsheet is uploaded, the site loads again. Another way out is to pick a nearby point, outside the city or the water.
3. **Sowing and period.** Day and month of sowing, the season year (*One season* tab) and the period of years (*Many years*, *Sowing window*, *Cultivars* and *Climate scenarios* tabs).
4. **Cultivar.** The default is the typical cultivar of the latitude (maturity group in DSSAT, cycle length in AquaCrop). Under *All cultivar parameters*, each coefficient can be changed within the training range.
5. **Management and scenario.**
   - **Water:** *Rainfed* (rain only) or *No water stress* (unlimited water, like a perfect irrigation).
   - **CO₂:** blank uses the value observed at Mauna Loa in that year.
   - **ΔT:** adds degrees to the maximum and minimum temperatures.
   - **Rain ×:** multiplies the rain.
   - **Plant population:** plants per m², from 15 to 50 (the training range); blank uses 30. In both crop models more plants raise the yield a little (in DSSAT, about +60 kg/ha per 10 plants/m² in rainfed seasons and +125 kg/ha without water stress).

**Training ranges:** ΔT from −1 to +4 °C, rain from ×0.7 to ×1.3 and CO₂ from 350 to 800 ppm. Outside them, the emulator extrapolates.

**In every tab:**
- **Download CSV** exports the numbers of the tab.
- Hovering over a chart shows the values of each point.
- The **How to read this tab** button opens the matching section of this guide.

<a id="safra"></a>

## One season

All the outputs of a single season: the year chosen in *Season year*, sown on the day and month of the sidebar.

**Top tiles**
- **Grain yield:** dry grain at the end of the cycle. With *No water stress*, the line below gives the rainfed yield for comparison, and vice versa. The difference between them is the water yield gap of the season (see [Terms](#termos)).
- **Flowering and Maturity:** predicted date and days after sowing.
- **Above-ground biomass:** total above-ground dry matter at maturity (leaves, stems, pods and grain).
- **Rain in the cycle and Evapotranspiration:** water received and water used by the crop (transpiration plus soil evaporation) from sowing to maturity. Evapotranspiration well below the demand indicates a lack of water.

**Reliability.** Says whether any input of the season (weather, soil, cultivar) is outside the training range or among its 0.5 % most extreme values. Outside the domain, the result is an extrapolation and should not be used; rare inputs call for more caution.

**Above-ground biomass and grain through the cycle.**
- **Lines:** the daily curves predicted by the emulator. A second network predicts the shape of each curve in phenological time (sowing, emergence, flowering, maturity), scaled to the season values; in the block validation the shapes reach R² 0.95–0.99 for biomass and grain.
- **Points:** the season values (biomass and grain at maturity). The dashed gray line is the biomass without water stress.
- **How to read it:** compare the final rainfed height with the no-stress height to see how much water limited the crop.

**Leaf area index (DSSAT) or Canopy cover (AquaCrop) through the cycle.**
- **Line:** the daily leaf area index or canopy cover predicted by the emulator. **Point:** the predicted maximum.
- **Reference values:** a maximum LAI above 3–4 indicates a closed canopy; low values indicate stress or a short cycle.

**Water stress through the cycle.**
- **What it shows:** the emulated water stress, from 0 (none) to 1 (full): stress on photosynthesis (WSPD) in DSSAT, stomatal stress (StSto) in AquaCrop, as the mean of each stretch of the cycle.
- **How to read it:** stress around flowering and grain filling costs the most yield. The validation R² is 0.80 (DSSAT) and 0.66 (AquaCrop): trust the pattern, not the exact days.

**The plant through the season.** An illustrative drawing driven by the emulated curves: the height follows the biomass, the leaves follow the leaf area or canopy cover, flowers appear at flowering, pods fill with the grain, and the leaves droop and turn yellow with water stress and fall at senescence. Move the slider or press *Play* to follow the cycle day by day; the panel beside it gives the stage and the emulated values of the day.

**Weather of the cycle.** These are the data that went into the calculation, from 30 days before sowing to after maturity:
- **Daily temperature (Tmax, Tmin):** days above 35 °C at flowering and grain filling reduce yield.
- **Daily rain:** look for long dry spells, especially around flowering.
- **Rain and demand accumulated since sowing:**
  - what it shows: accumulated rain (blue) against accumulated reference evapotranspiration (ETo, green), which is the water demand of the atmosphere;
  - how to read it: when the ETo line rises far above the rain, the crop depends on the water stored in the soil; if that lasts for weeks, there is a water deficit.
- **Solar radiation, Vapour pressure deficit and Growing degrees:**
  - high radiation favours photosynthesis;
  - a high VPD (dry air) raises the water demand;
  - growing degrees (base 5 °C, upper 30 °C) show how fast the cycle advances.

**All model outputs.** The table of every output (42 in DSSAT, 44 in AquaCrop). For each output it shows:
- the value and unit;
- the **acceptance level** and the validation error.

Use the *recommended* ones first; the *caution* ones are for comparing and aggregating; ignore the *not recommended* ones.

**The inputs computed for the network.** Lists the numbers the emulator received: weather summaries in windows, soil water, cultivar, CO₂. Next to each one is the training range, which helps to understand a domain warning.

<a id="monitor"></a>

## Crop monitoring

Follows the **season in progress**, sown in the current year. The weather is only known up to today, so the rest of the cycle is filled by scenarios:

- **Observed weather:** NASA POWER up to its last available day (3 to 5 days ago) and Open-Meteo for the most recent days.
- **Weather forecast:** the next 16 days (Open-Meteo).
- **Rest of the cycle:** the weather of **each past year** on the same dates, which gives one scenario per year.
- **Rest of the cycle** (selector at the top):
  - *Seasonal forecast (ECMWF)*: the past years are shifted month by month by the anomalies of the seasonal forecast (warmer, wetter and so on);
  - *Past years*: uses the years as they were.

Soil and cultivar stay fixed; only the weather changes between scenarios. The season is re-run **every 7 days** since sowing, each time with the weather known up to that date. That is why you can see how the expectation changed along the season.

**Top tiles**
- **Expected yield:** the median of the scenarios, rainfed. The line below gives the 80 % range: the spread of the scenarios (the weather still to come) widened by the error of the emulator (its validation RMSE), so that it is an 80 % range of what the crop model would simulate. The narrower it is, the less the result depends on the weather still to come. In tests on past seasons (hindcast), the expectation was close to the climatology at sowing and became reliable from about 30–45 days after sowing in AquaCrop and 60–90 days in DSSAT.
- **Most similar year so far:** the past year whose weather, from 30 days before sowing to the last observed day, was closest to this season's. The comparison is week by week: rain of the week, rain accumulated and mean Tmax and Tmin, each measured against the spread between the years, with more weight on the recent weeks. The text gives the yield of the scenario whose rest of the cycle follows that year, in t/ha and in % of the potential (no water stress), and the next two years of the ranking. It is the **most likely scenario** only in the sense of "the season looks like that year so far"; the future can still take another path. In the hindcast, this scenario missed the final yield more than the median of all the scenarios did, at every date: use it to picture the season, and the median and the 80 % range to estimate the yield.
- **Change since sowing:** how much the expectation rose or fell compared with the one at the sowing date. A fall means the weather so far was worse than that of the past years in those weeks.
- **Yield gap (water):** the median, across the scenarios, of *no water stress − rainfed*. It is the yield the model attributes to the lack of water. Near zero, water is not limiting.
- **Crop stage:** days after sowing and the expected stage (vegetative, reproductive, maturity), from the mean of the scenarios.

**Expected yield along the season.**
- **Horizontal axis:** the date when the season was re-run.
- **Blue line:** the rainfed median.
- **Blue band:** the 80 % range (scenarios widened by the emulator error). It narrows as the season advances, because more days are known, but not below the emulator error.
- **Dashed gray line:** the yield without water stress.
- **Red area:** the yield gap.
- **Dashed segment:** the estimate that already uses the 16-day forecast.
- **Violet diamond with a bar:** the estimate with the seasonal forecast and its 80 % range.
- **Projection until maturity (after today):** each past year in turn is taken as the weather to come (a "path"); every 2 weeks, the season is re-run with the weather that would be known on that date and the other years for the rest. **Dashed blue line:** the median of the paths; **light band:** 80 % of the paths, opening up to maturity, where it shows the final yields; **dashed orange line:** the path of the most similar year, ending at that year's final yield. The projection uses the past years as they were (no seasonal forecast) and is computed after the rest of the tab (a few seconds).
- **Vertical line:** today.

How to read it: a line that falls week after week means the weather is hurting the season. A diamond below the line means the seasonal forecast is less favourable than the average of the past years.

**Yield gap along the season.** The yield gap at each date. A rise shows when the lack of water started to matter.

**Final yield in each scenario.**
- **Blue dots:** rainfed, one per past year ("the rest of the cycle like year X").
- **Gray circles:** no water stress.
- **Orange circle:** the most similar year.
- **How to read it:** the distance between the two is the yield gap of that scenario. Years well below the others show the risk of a dry or hot rest of the season.

**Rain accumulated since sowing.**
- **Blue line:** this season (dashed, the forecast).
- **Dashed gray line and band:** median and 80 % of the past years on the same days.
- **Violet line:** the rain expected until maturity in the chosen mode.
- **Thin orange line:** the rain of the most similar year, from sowing to today (to compare with this season's).
- **Dashed orange line:** this season completed with the rain of the most similar year.
- **Vertical lines:** expected flowering and maturity.

How to read it: below the gray band, the season is drier than almost every year.

**Yield built along the cycle, % of the potential.** The grain accumulated day by day in each scenario (the emulator's daily curves), as % of the same scenario's yield without water stress.
- **Dashed gray line:** no water stress, reaching 100 % at maturity.
- **Blue line and band:** rainfed, median and 80 % of the scenarios. At maturity, the value is the relative yield (rainfed ÷ potential).
- **Orange line:** the most similar year.
- Grain starts to grow around seed filling (after flowering); before that the curves stay at zero.

**Yield gap along the cycle, % of the potential.** The grain lost to the lack of water up to each day (no water stress − rainfed), as % of the potential; at maturity it is the final yield gap of each scenario. Same reading: median, 80 % band and most similar year. The two curves are compared at the same crop stage (drought shortens the rainfed cycle by a few days).

**Daily temperature.**
- **Tmax and Tmin:** of this season; faded, the forecast days.
- **Gray line:** the median Tmax of the past years.
- **Violet line:** the Tmax expected with the seasonal forecast.

**ECMWF seasonal forecast used.** The table shows, for each month:
- the anomaly of temperature and dew point (added to the weather of the past years);
- the anomaly of rain and radiation (multiplied);
- the forecast rain against the normal of the forecast model itself.

Caveats about the seasonal forecast:
- it says whether a month tends to be warmer or wetter than normal, **not the weather of each day**;
- its skill varies by region and season, and has not yet been evaluated for this use.

**The season so far.**
- **Rain since sowing:** compared with the past years.
- **Days with Tmax ≥ 35 °C:** counted since sowing.
- **Water stress over the last 14 days:** a simple index from the soil water bucket, from 0 (no stress) to 1 (severe).
- **Forecast rain for the next 15 days.**

**Caveats**
- Early in the cycle, the band is wide and the result says more about the typical weather of the site than about this season.
- The yield gap is only the effect of water. Pests, diseases and nutrition are not included.
- The 16-day and seasonal forecasts can be wrong. Compare the *Seasonal forecast* mode with the *Past years* mode to see how much the conclusion depends on them.

<a id="anos"></a>

## Many years

The same season (same sowing day and month, same cultivar and management) repeated in **every year of the chosen period**. It shows the variability caused by the weather alone.

**Variable.** The selector at the top picks the output shown in the charts (yield, biomass, evapotranspiration, dates and so on).

**Top tiles**
- **Mean, rainfed:** the mean and median across the years.
- **Year-to-year variability:**
  - what it shows: the coefficient of variation (CV, standard deviation as a % of the mean);
  - how to read it: a yield CV above 20–25 % indicates a season with high climate risk.
- **Poor / good years:** the value below which 10 % of the years fall and the value above which 10 % fall.
- **No water stress:** the mean with unlimited water and the mean difference from rainfed.

**Variable by year.**
- **Points and line:** rainfed.
- **Gray line:** no water stress.
- **Red area:** the difference attributed to the lack of water.
- **Red rings:** seasons with inputs outside the training domain; disregard them.

**Rain and evapotranspiration in the cycle.** Bars of rain and a line of evapotranspiration, from sowing to maturity, rainfed. Years with little rain and low evapotranspiration are usually the lowest-yielding ones.

**Phenology.** Days to flowering and to maturity in each year. The variation comes from temperature and, in DSSAT, also from photoperiod.

**Variable × rain in the cycle and Variable × evapotranspiration.** Each point is a year.
- A strong rising relation means water is the main driver of the year-to-year variation at the site.
- Points off the trend mean another factor mattered, such as heat or the distribution of the rain.

**Distribution across the years.**
- **Vertical axis:** the probability of a value lower than or equal to the one on the horizontal axis.
- **How to read it:** at 0.2, for example, is the yield that is not reached in 20 % of the years. It is the curve to think about risk and insurance.

**Summary across the years.** Minimum, 10th, 50th and 90th percentiles and maximum of each output.

<a id="janela"></a>

## Sowing window

Simulates **many sowing dates in every year** of the period. It answers when to sow for higher yield and lower risk.

**Controls.** Start and end of the window, the step between dates (days), the variable and the risk threshold (a fixed value or a percentile, by default the 20th of all seasons).

**Top tiles**
- **Best median:** the date with the highest median across the years and its 10–90 % range.
- **Lowest risk:** the date with the smallest share of years below the threshold.
- **Maturity at the best date:** the cycle length and the approximate harvest date.

**Variable by year and sowing date** (colour map).
- **Rows and columns:** each row is a year and each column a sowing date; each cell is one season.
- **How to read it:** dark or light horizontal stripes are good or poor years for any date; vertical stripes show dates that are consistently better or worse.
- **Dots:** inputs outside the domain.

**Median and bands across the years.**
- **Line:** the median for each date.
- **Bands:** 25–75 % and 10–90 % of the years.
- **Dashed line:** the best median.
- **How to read it:** prefer dates with a high median **and** a narrow band. A date with a slightly lower median and a much narrower band may be the safer choice.

**Risk.** Share of the years with the variable below the threshold, for each date. The lower it is, the safer the date.

**Cycle length.** Median days from sowing to maturity for each date. Late sowings usually shorten the cycle, because of temperature and, in DSSAT, photoperiod, which affects the planning of the next crop.

**Table by sowing date.** The numbers of all the charts.

<a id="cultivares"></a>

## Cultivars

Compares cultivars sown on the same date in every year of the period, and shows the sensitivity to each cultivar parameter.

**Variants.**
- **In DSSAT:** maturity groups (MG). Later MGs flower and mature later because they respond to photoperiod.
- **In AquaCrop:** cycle factors on the growing degrees to maturity, from 0.75 (shorter) to 1.25 (longer).

**Box plots** (variable, flowering and maturity by variant).
- **Box:** 25 to 75 % of the years.
- **Inner line:** the median.
- **Whiskers and dots:** the extreme years.
- **How to read it:** compare the position of the boxes (which yields more) and their height (which varies more between years).

**Summary by cultivar.** Median flowering and maturity, the 10th, 50th and 90th percentiles of the variable and the number of seasons outside the domain.

**Sensitivity to each parameter.**
- **What it does:** varies one parameter at a time, within the training range, with the others fixed.
- **Line:** the median across the years.
- **Band:** 25–75 %.
- **Dashed line:** the current value of the cultivar.
- **How to read it:** steep curves mark important parameters, worth calibrating with field data; flat curves mark parameters that barely change the result at the site.

<a id="cenarios"></a>

## Climate scenarios

Applies to the observed weather the same perturbations used in training and shows the **change of the mean** across the years relative to the observed weather. The perturbations are:
- **ΔT:** degrees added to the maximum and minimum temperatures;
- **Rain:** multiplied by a factor;
- **CO₂:** fixed at a value.

The ΔT, rain and CO₂ fields of the sidebar do not apply to this tab; the values tested are set in the fields at the top.

**Mean with the observed weather.** The reference for the comparisons.

**Variable: warming × CO₂** (colour map).
- **Colour of each cell:** the change for one combination of ΔT and CO₂.
- **How to read it:** warming usually reduces yield and CO₂ usually increases it (fertilisation effect). The map shows how much CO₂ offsets each degree of warming.
- **Cells with a border:** outside the training range.

**Warming with the observed CO₂.** Change for each ΔT without changing CO₂. It shows the effect of warming alone.

**Rain.** Change for each rain factor (training: ×0.7 to ×1.3). Rainfed, it shows the dependence on rain; without water stress, it should be small.

**Caveat.** The scenarios change every day by the same amount. They do not change the frequency of droughts or heat waves, as projections of climate models would.

<a id="local"></a>

## Site

The weather and soil of the site, to understand the results of the other tabs.

**Top tiles**
- **Mean annual rain.**
- **Soil available water:**
  - what it shows: the water the profile holds between field capacity and the wilting point, to 2 m and in the top 30 cm;
  - how to read it: low values (below 100 mm) make the crop more sensitive to dry spells.
- **Texture and organic carbon in the top 30 cm.**

**Mean monthly rain and Mean monthly temperature.** The climatology of the site, which shows the rainy season and the hottest time of the year.

**Annual rain.** Total of each complete year; very dry or wet years show up here.

**Water retention of the profile.**
- **What it shows:** the water content at saturation, field capacity and wilting point, by layer.
- **How to read it:** the space between field capacity and wilting point is the water available to the plant.
- **Estimated values:** come from pedotransfer functions of texture, carbon and bulk density, the same as in training. When your profile has these values measured, they are used as given.

**Soil profile.** The table of the layers. Profiles deeper than 2 m are cut at 2 m, like all the training profiles.

**Source of the weather data.**
- **What it shows:** how many days of each variable came from your spreadsheet, from NASA POWER or were filled.
- **Gap filling:** gaps of up to 5 days are interpolated, with zero rain on those days.
- **No humidity:** the dew point is taken equal to Tmin.
- **No wind:** 2 m/s is used.

<a id="modelo"></a>

## About the model

**Quality of each output in the spatial validation.**
- **What it shows:** the R² of each output when the emulator was tested on 5° × 5° blocks it did not see in training.
- **Colour:** the acceptance level.
- **How to read it:** the closer to 1, the better the emulator reproduces the crop model in new regions.

**Outputs, units and validation error.**
- **What it shows:** the list of outputs with the unit, the error (RMSE) and the level.
- **Reference values:** the yield error of DSSAT v3 is about 343 kg/ha and that of AquaCrop v3 is 0.51 t/ha (slightly above v2, 335 kg/ha and 0.50 t/ha, because v3 also learns the plant population).

**Where your season sits in the training domain.** Each input of the last computed season is shown over the training range. Inputs near or beyond the edges explain warnings and call for caution.

**What the emulator does not know.** The limits of the method: what was fixed in training and what is left out.

The **About CropEmu** tab gives the purpose of the tool, a summary of the method, the data sources and the link to the code.

<a id="termos"></a>

## Terms used in the app

- **Emulator:** a neural network trained to reproduce the results of a crop model. It computes a season in less than a millisecond, against up to one second for the original model.
- **Rainfed:** the crop receives only the rain.
- **No water stress:** the crop has all the water it needs, as with a perfect irrigation. It shows the potential of the weather, soil and cultivar.
- **Yield gap (water):** yield without water stress minus rainfed yield. It is the loss the model attributes to the lack of water. It does not include losses to pests, diseases, nutrition or management.
- **Acceptance level:** the rating of each output in the spatial validation.
  - *recommended*: dates with an error up to 5 days; other outputs with an error below 25 % of the year-to-year variation at the site;
  - *caution*: error below 50 % of that variation;
  - *not recommended*: the rest.
- **Outside the domain:** an input outside the range seen in training. The result is an extrapolation and is not reliable.
- **Rare input:** within the range, but among the 0.5 % most extreme values of training. The result deserves more caution.
- **80 % range and percentiles:**
  - the 80 % range goes from the 10th to the 90th percentile: it leaves out the lowest 10 % and the highest 10 % of the values;
  - the median is the 50th percentile.
- **Days after sowing (DAS):** how the app counts the dates of the cycle.
- **ETo:** reference evapotranspiration, the water demand of the atmosphere, computed with the FAO-56 Penman-Monteith method.
- **VPD:** vapour pressure deficit, which shows how dry the air is.
- **Growing degrees:** the daily sum of the mean temperature above 5 °C (capped at 30 °C). It measures the progress of the cycle by heat.
- **Maturity group (MG):** the class of a soybean cultivar by cycle length and photoperiod response; higher MGs are later.
- **Seasonal forecast:** a forecast of monthly anomalies (warmer, wetter) for the next months. It does not predict the weather of each day.

<a id="faq"></a>

## Frequently asked questions

**The yield in the app is very different from my field. Is it wrong?**
Not necessarily. The app shows what DSSAT or AquaCrop would simulate with the given cultivar and soil, without pests, diseases or nitrogen limitation, and without calibration to your field. Use it to compare options. To get closer to the field, upload your weather and soil and adjust the cultivar.

**DSSAT or AquaCrop: which one should I use?**
- DSSAT represents the maturity group and photoperiod better.
- AquaCrop is simpler and focused on water.
- Running both and comparing is the best practice. If the conclusion is the same in both, it is more reliable.

**Why are some seasons flagged or missing from the charts?**
- **Flagged:** they have an input outside the training domain.
- **Missing:** the weather of the period was incomplete. In both cases, the *Site* tab shows where the data came from.

**Do my data go to a server?**
No. Everything is computed in your browser. Only the coordinates of the site go to the public weather, soil, forecast and map services.

**Why did the seasonal forecast change from one month to the next?**
ECMWF updates the seasonal forecast every month (around the 5th). The monitoring always uses the latest one.

**How do I cite CropEmu?**
Cite the repository (<https://github.com/fcoliveira-utfpr/emulator_crop>) and the version of the `cropemu` library. A paper is in preparation.
