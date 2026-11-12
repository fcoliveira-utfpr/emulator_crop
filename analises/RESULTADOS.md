# Resultados das análises (para o artigo)

Bases: dssat_v1 e aquacrop_v1 (solo híbrido), 117.720 safras, 1.962 pontos (1.671 na área de soja, 291 fora),
5 dobras por blocos de 5°. Emulador escolhido: MLP por grupos (DSSAT) e MLP por grupos com offset térmico (AquaCrop).

## 02_error_structure.py (tabelas em analises/tables, figuras em analises/figures)
- Saídas: DSSAT 41 (5 recomendadas, 29 cautela, 7 não); R² mediano 0,932 (0,782–0,995).
  AquaCrop 44 (6 / 16 / 22); R² mediano 0,889 (−0,029–0,997).
- Produtividade por estrato (RMSE t/ha; % da média):
  - DSSAT: Köppen A 0,409 (10,6%), B 0,442 (19,6%), C 0,491 (15,1%), D 0,444 (18,3%);
    latitude 0–15° 0,388, 15–30° 0,453, 30–45° 0,507, >45° 0,335;
    sem estresse hídrico 0,383 (8,7%) vs sequeiro 0,470 (17,0%); histórico 0,430 vs perturbado 0,505;
    área de soja 0,458 vs fora 0,431; nível baixo 0,463 (52%; viés +0,143), médio 0,479, alto 0,416 (7,9%; viés −0,136).
  - AquaCrop: A 0,589 (19,7%), B 0,576 (33,2%), C 0,621 (21,8%), D 0,497 (23,5%);
    0–15° 0,720, 15–30° 0,520, 30–45° 0,610, >45° 0,460; sem estresse 0,395 (9,7%) vs sequeiro 0,618 (28,1%);
    histórico 0,540 vs perturbado 0,666; soja 0,564 vs fora 0,667; baixo 0,638 (viés +0,219), alto 0,594 (viés −0,155).
- Erro por ponto (RMSE t/ha): DSSAT mediana 0,399 (quartis 0,323–0,482; máx 2,15); AquaCrop 0,435 (0,311–0,596; máx 3,28).
- Variabilidade dentro do ponto (sequeiro, clima histórico, 1.962 pontos):
  - DSSAT: r mediano 0,935 (P10 0,787); 88,4% dos pontos com r > 0,8; razão de desvio-padrão emu/sim 0,947 (P10–P90 0,80–1,09);
    médias por ponto r 0,992, RMSE 0,176 t/ha.
  - AquaCrop: r mediano 0,931 (P10 0,626); 75,8% com r > 0,8; razão 0,956 (0,78–1,23); médias r 0,973, RMSE 0,280 t/ha.
- Resposta às perturbações (inclinações com efeito de ponto removido, 35.316 safras perturbadas; t/ha):
  - DSSAT: por °C −0,153 (sim) vs −0,152 (emu); por +10% de chuva +0,193 vs +0,182; por +100 ppm CO2 +0,271 vs +0,264.
  - AquaCrop: por °C −0,195 vs −0,189; por +10% chuva +0,136 vs +0,132; por +100 ppm +0,213 vs +0,209.
