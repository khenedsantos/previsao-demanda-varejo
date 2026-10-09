# Fase 6 — Forecast uncertainty & stockout-aware demand risk

## Objetivo e limites de uso

Caracterização empírica de 1.400.000 erros ETS A/N/A já produzidos: 50.000 séries × quatro folds × sete dias. **Nenhum ajuste foi executado, nenhum point forecast alterado e nenhum arquivo raw aberto pela Fase 6.** Eval permanece fechado. Target é venda observada normalizada, não demanda latente, unidades físicas ou receita. Não se estimam lost sales, intervalos probabilísticos, safety stock, reorder point ou compra.

**Corte dos perfis: 25/06/2024; disponíveis a partir de 26/06/2024.** Os forecasts continuam sendo os backtests prospectivos da Fase 5. Para o diagnóstico desta fase, seus erros são agrupados pelas classes finais da Fase 3, conhecidas em 25/06, sem recalcular ABC, XYZ, exposição ou flag de censura. Essa é uma descrição retrospectiva para uma decisão futura: **não é uma reavaliação prospectiva dos folds**, e os perfis não podem ser usados em origens anteriores. Por isso, tabelas segmentadas podem diferir da Fase 5, que usava rótulos diferentes em cada origem; o agregado global e o erro de cada série são iguais.

## Inputs e integridade

| Origem | Mart verificado | SHA-256 |
|---|---|---|
| phase5 | data/processed/mart_forecast_statistical.parquet | e37cbec4f5b04c1da503dd459f3fbb9f41eeeed4bfdbfab762d3177e5d96631f |
| phase3 | data/processed/mart_operational_profile.parquet | c5df94df59df6420f58b4997a5259ed002c14d08df4cb9d45a0c9b9c7c3ee059 |
| phase2 | data/processed/mart_demand_profile.parquet | 2f8a9da452f6d00f762d0c736eb343c8ae45303919ae2cc44073202f2bce077e |

Os SHA-256 dos marts são verificados contra os resumos das fases aprovadas. Os resumos têm seu escopo/fonte conferidos contra a identidade train do manifesto, e seus hashes são registrados para proveniência. A fase lê apenas esses marts/resumos e o manifesto; não precisa de raw, staging, eval ou novo fitting. Os campos `source_split`, `as_of`, `available_from` e `analysis_view` documentam o limite temporal dos perfis.

## Fórmulas e perfil de erro

Preserva-se `error = forecast − actual`. Subprevisão: error<0; superprevisão: error>0; erro exatamente zero é contado separadamente. `underforecast_amount=max(actual−forecast,0)` é derivada, não substitui error. MAE=Σ|error|/N; RMSE=√(Σerror²/N); WAPE=Σ|error|/Σactual; bias=Σerror/N; bias_pct=Σerror/Σactual. WAPE/bias_pct ficam nulos se D=0. A média do underforecast positivo é nula quando não há dia subprevisto. Não há MAPE nem preenchimento de percentuais indefinidos com zero.

`error_std` e `absolute_error_std` são desvios amostrais (`ddof=1`). Quantis usam interpolação linear tipo 7: p50/p90/p95 de |error| e q10/q25/q50/q75/q90 do erro assinado. Cada perfil tem 28 forecasts, actual_total/forecast_total, dias/taxas de sub e superprevisão e total/média positiva de underforecast. As agregações de segmentos usam as observações originais, nunca médias de WAPEs, RMSEs, desvios ou quantis por série.

| Séries | Previsões | D actual | MAE | RMSE | WAPE | Bias | Bias % | Desvio erro | p90 absoluto | p95 absoluto | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 50000 | 1400000 | 1518029.667000 | 0.390632 | 0.672312 | 36.03% | -0.023541 | -2.17% | 0.671900 | 0.837832 | 1.222739 | 50.22% |

## Distribuições por série

| Métrica | Válidos | Mínimo | p05 | p25 | Mediana | p75 | p95 | Máximo |
|---|---|---|---|---|---|---|---|---|
| bias | 50000 | -3.935013 | -0.309542 | -0.093001 | -0.013751 | 0.054383 | 0.203816 | 2.575401 |
| bias_pct | 50000 | -0.817989 | -0.238565 | -0.108788 | -0.018717 | 0.080277 | 0.294336 | 3.262596 |
| error_std | 50000 | 0.070603 | 0.183606 | 0.255446 | 0.352702 | 0.550570 | 1.201622 | 7.764284 |
| rmse | 50000 | 0.072015 | 0.187106 | 0.260504 | 0.360194 | 0.567010 | 1.257660 | 7.790901 |
| p90_absolute_error | 50000 | 0.112531 | 0.292404 | 0.407686 | 0.562807 | 0.883176 | 2.018109 | 12.332535 |
| p95_absolute_error | 50000 | 0.117909 | 0.338479 | 0.476838 | 0.664517 | 1.055403 | 2.431322 | 17.042135 |
| underforecast_rate | 50000 | 0.035714 | 0.285714 | 0.428571 | 0.500000 | 0.607143 | 0.714286 | 0.964286 |
| actual_total | 50000 | 1.100000 | 10.130000 | 14.370000 | 19.700000 | 31.800000 | 81.500000 | 866.700000 |

Bias negativo em **27,663 séries (55.326%)**. Os quantis acima dão peso igual a cada série; não equivalem à distribuição dos 1,4 milhão de erros agrupados. Bias negativo, sozinho, não demonstra ruptura, demanda perdida ou estoque insuficiente: pode refletir nível, ruído, promoção, erro do modelo ou censura, entre outras explicações.

## Persistência temporal do bias

Regra solicitada e preservada após diagnóstico: **bias consolidado <0 E bias negativo em pelo menos três dos quatro folds**. Não há score ponderado. Cada fold tem sete previsões, sem pesos desiguais. Um fold com bias zero não conta como negativo. A condição consolidada evita classificar séries cuja superprevisão em uma janela supera as subprevisões das outras.

| Folds negativos | Séries | Persistentes | Venda normalizada train |
|---|---|---|---|
| 0 | 3587 | 0 | 388182.104000 |
| 1 | 11432 | 0 | 971308.501000 |
| 2 | 17593 | 0 | 1534537.448000 |
| 3 | 13020 | 12161 | 1201469.775000 |
| 4 | 4368 | 4368 | 398162.959000 |

São **16,529 séries persistentes (33.058%)**. Das 13.020 séries com três folds negativos, 12.161 também têm bias consolidado negativo; as 4.368 com quatro folds negativos cumprem ambos os critérios. Isso é persistência observada, não previsão de persistência futura.

Sensibilidade ao número de folds, sem substituir a regra oficial:

| Mínimo folds negativos | Séries | Participação | Com flag censura | Venda train |
|---|---|---|---|---|
| 2 | 26322 | 52.64% | 1544 | 53.85% |
| 3 | 16529 | 33.06% | 1028 | 34.02% |
| 4 | 4368 | 8.74% | 281 | 8.86% |

## Medidas candidatas de incerteza

Desvio do erro mede dispersão ao redor do bias; RMSE incorpora dispersão e deslocamento sistemático. Para N=28, error_std² = 28/27 × (RMSE² − bias²). Quantis absolutos descrevem magnitude de cauda, mas perdem direção; os quantis assinados e underforecast_amount preservam essa informação. Nenhuma dessas medidas é intervalo de previsão, probabilidade calibrada, erro acumulado de lead time ou fórmula de estoque de segurança. Preservar as quatro como entradas candidatas, com bias separado.

| Medida 1 | Medida 2 | Spearman | Séries |
|---|---|---|---|
| error_std | rmse | 0.994420 | 50000 |
| error_std | p90_absolute_error | 0.966960 | 50000 |
| error_std | p95_absolute_error | 0.967706 | 50000 |
| rmse | p90_absolute_error | 0.973650 | 50000 |
| rmse | p95_absolute_error | 0.974517 | 50000 |
| p90_absolute_error | p95_absolute_error | 0.977702 | 50000 |

As medidas são fortemente associadas (Spearman desvio/RMSE ≈0,994), sem equivalência de significado. **28 observações por série são insuficientes para estabilizar caudas**: no tipo 7, p90 depende sobretudo das posições 25–26 e p95 das posições 26–27 na ordenação de 28 erros. As amostras agregadas aumentam o número de observações, mas misturam escalas e dependências de loja/produto/calendário; não são observações independentes.

## Calibração descritiva por ABC

| ABC | Séries | Previsões | D actual | MAE | RMSE | WAPE | Bias | Bias % | Desvio erro | p90 absoluto | p95 absoluto | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 33379 | 934612 | 1228443.057000 | 0.448073 | 0.765851 | 34.09% | -0.031838 | -2.42% | 0.765190 | 0.976425 | 1.422056 | 51.07% |
| B | 12160 | 340480 | 216252.346000 | 0.279906 | 0.438950 | 44.07% | -0.008289 | -1.31% | 0.438872 | 0.578782 | 0.791545 | 48.63% |
| C | 4461 | 124908 | 73334.264000 | 0.262655 | 0.390289 | 44.74% | -0.003030 | -0.52% | 0.390278 | 0.555062 | 0.745505 | 48.17% |

## Calibração descritiva por XYZ

| XYZ | Séries | Previsões | D actual | MAE | RMSE | WAPE | Bias | Bias % | Desvio erro | p90 absoluto | p95 absoluto | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| X | 13117 | 367276 | 408983.220000 | 0.346427 | 0.578448 | 31.11% | -0.018303 | -1.64% | 0.578159 | 0.734499 | 1.090060 | 50.21% |
| Y | 15677 | 438956 | 462181.090000 | 0.368448 | 0.607471 | 34.99% | -0.018857 | -1.79% | 0.607179 | 0.786193 | 1.141667 | 50.44% |
| Z | 21206 | 593768 | 646865.357000 | 0.434375 | 0.765486 | 39.87% | -0.030244 | -2.78% | 0.764889 | 0.934109 | 1.348123 | 50.06% |

## Calibração descritiva por ABC × XYZ

| ABC | XYZ | Séries | Previsões | D actual | MAE | RMSE | WAPE | Bias | Bias % | Desvio erro | p90 absoluto | p95 absoluto | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | X | 9012 | 252336 | 332652.151000 | 0.401599 | 0.662309 | 30.46% | -0.025389 | -1.93% | 0.661824 | 0.875046 | 1.300019 | 50.59% |
| A | Y | 10557 | 295596 | 376081.523000 | 0.427677 | 0.698189 | 33.61% | -0.026602 | -2.09% | 0.697683 | 0.933337 | 1.356462 | 51.32% |
| A | Z | 13810 | 386680 | 519709.383000 | 0.493993 | 0.871064 | 36.75% | -0.040051 | -2.98% | 0.870144 | 1.067877 | 1.537562 | 51.19% |
| B | X | 2966 | 83048 | 56682.234000 | 0.227120 | 0.324984 | 33.28% | -0.003239 | -0.47% | 0.324970 | 0.465720 | 0.599964 | 49.65% |
| B | Y | 3805 | 106540 | 65455.313000 | 0.248284 | 0.359247 | 40.41% | -0.004398 | -0.72% | 0.359222 | 0.510320 | 0.664177 | 48.81% |
| B | Z | 5389 | 150892 | 94114.799000 | 0.331285 | 0.534334 | 53.11% | -0.013817 | -2.22% | 0.534158 | 0.705814 | 0.983314 | 47.95% |
| C | X | 1139 | 31892 | 19648.835000 | 0.220582 | 0.328057 | 35.80% | -0.001464 | -0.24% | 0.328059 | 0.449993 | 0.592984 | 48.65% |
| C | Y | 1315 | 36820 | 20644.254000 | 0.240643 | 0.335349 | 42.92% | 0.001486 | 0.26% | 0.335350 | 0.504136 | 0.653098 | 48.04% |
| C | Z | 2007 | 56196 | 33041.175000 | 0.300955 | 0.451460 | 51.19% | -0.006878 | -1.17% | 0.451412 | 0.647085 | 0.870015 | 47.99% |

## Calibração descritiva por Exposição à ruptura

| Exposição | Séries | Previsões | D actual | MAE | RMSE | WAPE | Bias | Bias % | Desvio erro | p90 absoluto | p95 absoluto | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HIGH | 12606 | 352968 | 569302.883000 | 0.510700 | 0.937686 | 31.66% | -0.070067 | -4.34% | 0.935065 | 1.150834 | 1.724194 | 52.57% |
| LOW | 13591 | 380548 | 306420.310000 | 0.347263 | 0.521192 | 43.13% | -0.004483 | -0.56% | 0.521173 | 0.746230 | 1.021837 | 48.02% |
| MEDIUM | 23803 | 666484 | 642306.474000 | 0.351807 | 0.573338 | 36.50% | -0.009783 | -1.02% | 0.573255 | 0.746229 | 1.076371 | 50.23% |

## Calibração descritiva por Flag de possível censura

| Flag | Séries | Previsões | D actual | MAE | RMSE | WAPE | Bias | Bias % | Desvio erro | p90 absoluto | p95 absoluto | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| False | 47349 | 1325772 | 1432387.313000 | 0.381458 | 0.656461 | 35.31% | -0.021502 | -1.99% | 0.656109 | 0.812279 | 1.190008 | 50.23% |
| True | 2651 | 74228 | 85642.354000 | 0.554488 | 0.910059 | 48.06% | -0.059960 | -5.20% | 0.908087 | 1.203697 | 1.664039 | 50.09% |

## Calibração descritiva por ABC × XYZ × exposição

| ABC | XYZ | Exposição | Séries | Previsões | D actual | MAE | RMSE | WAPE | Bias | Bias % | Desvio erro | p90 absoluto | p95 absoluto | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | X | HIGH | 3127 | 87556 | 144947.947000 | 0.483600 | 0.810033 | 29.21% | -0.041959 | -2.53% | 0.808950 | 1.119680 | 1.700358 | 51.19% |
| A | X | LOW | 1650 | 46200 | 45336.220000 | 0.331832 | 0.469811 | 33.82% | -0.012801 | -1.30% | 0.469642 | 0.706017 | 0.931708 | 49.87% |
| A | X | MEDIUM | 4235 | 118580 | 142367.984000 | 0.368234 | 0.602467 | 30.67% | -0.018058 | -1.50% | 0.602198 | 0.791488 | 1.162736 | 50.43% |
| A | Y | HIGH | 2692 | 75376 | 137962.244000 | 0.570289 | 0.946028 | 31.16% | -0.059706 | -3.26% | 0.944148 | 1.333981 | 1.950183 | 53.55% |
| A | Y | LOW | 2544 | 71232 | 69634.458000 | 0.371537 | 0.533003 | 38.01% | -0.022441 | -2.30% | 0.532534 | 0.794163 | 1.068798 | 50.16% |
| A | Y | MEDIUM | 5321 | 148988 | 168484.821000 | 0.382368 | 0.615256 | 33.81% | -0.011843 | -1.05% | 0.615144 | 0.819423 | 1.176414 | 50.75% |
| A | Z | HIGH | 3779 | 105812 | 226244.278000 | 0.668497 | 1.265425 | 31.26% | -0.132760 | -6.21% | 1.258448 | 1.448435 | 2.193215 | 54.17% |
| A | Z | LOW | 3614 | 101192 | 94972.081000 | 0.436331 | 0.643120 | 46.49% | -0.014595 | -1.56% | 0.642957 | 0.962998 | 1.304623 | 48.86% |
| A | Z | MEDIUM | 6417 | 179676 | 198493.024000 | 0.423702 | 0.675987 | 38.35% | 0.000210 | 0.02% | 0.675989 | 0.915926 | 1.312549 | 50.74% |
| B | X | HIGH | 591 | 16548 | 13098.163000 | 0.213834 | 0.300322 | 27.02% | -0.014039 | -1.77% | 0.300003 | 0.458338 | 0.599808 | 52.28% |
| B | X | LOW | 885 | 24780 | 16038.479000 | 0.233440 | 0.332129 | 36.07% | 0.010823 | 1.67% | 0.331959 | 0.472727 | 0.603639 | 47.34% |
| B | X | MEDIUM | 1490 | 41720 | 27545.592000 | 0.228636 | 0.330065 | 34.63% | -0.007307 | -1.11% | 0.329988 | 0.463717 | 0.594013 | 49.98% |
| B | Y | HIGH | 576 | 16128 | 11198.915000 | 0.253611 | 0.379568 | 36.52% | -0.027388 | -3.94% | 0.378591 | 0.533331 | 0.723651 | 52.27% |
| B | Y | LOW | 1321 | 36988 | 22472.917000 | 0.259697 | 0.370796 | 42.74% | 0.010074 | 1.66% | 0.370664 | 0.536753 | 0.693250 | 46.72% |
| B | Y | MEDIUM | 1908 | 53424 | 31783.481000 | 0.238774 | 0.344512 | 40.13% | -0.007477 | -1.26% | 0.344434 | 0.488874 | 0.624998 | 49.21% |
| B | Z | HIGH | 1102 | 30856 | 23781.096000 | 0.386633 | 0.568659 | 50.17% | -0.051439 | -6.67% | 0.566336 | 0.880339 | 1.188338 | 50.71% |
| B | Z | LOW | 1791 | 50148 | 27836.146000 | 0.314387 | 0.515333 | 56.64% | 0.018729 | 3.37% | 0.514997 | 0.662594 | 0.908596 | 44.43% |
| B | Z | MEDIUM | 2496 | 69888 | 42497.557000 | 0.318975 | 0.532081 | 52.46% | -0.020560 | -3.38% | 0.531687 | 0.656065 | 0.917566 | 49.27% |
| C | X | HIGH | 215 | 6020 | 3583.390000 | 0.188420 | 0.283898 | 31.65% | -0.002037 | -0.34% | 0.283915 | 0.394536 | 0.509481 | 48.69% |
| C | X | LOW | 359 | 10052 | 6835.487000 | 0.257596 | 0.384056 | 37.88% | 0.006045 | 0.89% | 0.384027 | 0.531936 | 0.707239 | 47.64% |
| C | X | MEDIUM | 565 | 15820 | 9229.958000 | 0.209302 | 0.304247 | 35.87% | -0.006017 | -1.03% | 0.304197 | 0.423084 | 0.544717 | 49.27% |
| C | Y | HIGH | 224 | 6272 | 3279.640000 | 0.200767 | 0.275421 | 38.39% | 0.005213 | 1.00% | 0.275394 | 0.423938 | 0.528748 | 47.67% |
| C | Y | LOW | 516 | 14448 | 8393.725000 | 0.272826 | 0.374630 | 46.96% | 0.005510 | 0.95% | 0.374603 | 0.572613 | 0.752679 | 47.31% |
| C | Y | MEDIUM | 575 | 16100 | 8970.889000 | 0.227296 | 0.318889 | 40.79% | -0.003578 | -0.64% | 0.318878 | 0.472744 | 0.609099 | 48.84% |
| C | Z | HIGH | 300 | 8400 | 5207.210000 | 0.267303 | 0.385369 | 43.12% | -0.032005 | -5.16% | 0.384061 | 0.581536 | 0.773056 | 52.29% |
| C | Z | LOW | 911 | 25508 | 14900.797000 | 0.333769 | 0.502390 | 57.14% | 0.009429 | 1.61% | 0.502311 | 0.717115 | 0.960282 | 45.52% |
| C | Z | MEDIUM | 796 | 22288 | 12933.168000 | 0.276083 | 0.411172 | 47.58% | -0.016071 | -2.77% | 0.410867 | 0.588025 | 0.788886 | 49.21% |

As 27 células ABC×XYZ×exposição têm no mínimo 215 séries e 6020 forecasts. Todas superam o critério operacional descritivo declarado de 100 séries. Esse critério serve para não interpretar uma célula minúscula; não garante independência, precisão probabilística ou transferibilidade. Não foram criadas combinações adicionais.

### Interpretação de disponibilidade e escala

HIGH tem MAE 0,5107, RMSE 0,9377 e desvio 0,9351, superiores a LOW (0,3473; 0,5212; 0,5212). Seu bias é mais negativo (−0,0701 contra −0,0045), e a frequência de subprevisão é 52,57% contra 48,02%. Apesar disso, seu WAPE é menor (31,66% contra 43,13%), por diferenças no denominador/escala. Não se conclui que HIGH é intrinsecamente mais previsível ou que ruptura causou os erros.

Flag=True tem RMSE 0,9101, desvio 0,9081 e bias −0,0600, contra 0,6565, 0,6561 e −0,0215 sem flag. **A frequência de subprevisão é praticamente igual, ligeiramente menor com flag: 50,09% contra 50,23%.** A diferença de bias não deve ser descrita como maior número de dias subprevistos; frequência e magnitude são distintas. A definição da flag de censura da Fase 3 foi preservada integralmente.

## Matriz transparente de dois sinais

`demand_observation_risk_cell` combina censoring_risk_flag e persistent_underforecast_flag: NEITHER, UNDERFORECAST_ONLY, CENSORING_ONLY, CENSORING_AND_UNDERFORECAST. NEITHER significa ausência desses dois sinais específicos; pode haver bias negativo não persistente, incerteza ou ruptura observada. A flag de censura não comprova lost sales. As diferenças de bias entre células são parcialmente mecânicas, pois bias integra sua definição; não validam de maneira independente poder preditivo ou causalidade.

Participação de venda principal = soma da venda normalizada dos 90 dias de train na célula / total train. A coluna de participação dos actuals do backtest usa os 28 dias; os denominadores não se confundem.

| Célula | % séries | Venda train | Venda backtest | Séries | Previsões | D actual | MAE | RMSE | WAPE | Bias | Bias % | Desvio erro | p90 absoluto | p95 absoluto | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CENSORING_AND_UNDERFORECAST | 2.06% | 1.98% | 2.64% | 1028 | 28784 | 40036.657000 | 0.549224 | 0.961878 | 39.49% | -0.234056 | -16.83% | 0.932983 | 1.193510 | 1.643641 | 61.00% |
| CENSORING_ONLY | 3.25% | 3.09% | 3.00% | 1623 | 45444 | 45605.697000 | 0.557823 | 0.875651 | 55.58% | 0.050312 | 5.01% | 0.874214 | 1.212039 | 1.681237 | 43.18% |
| NEITHER | 63.70% | 62.89% | 57.52% | 31848 | 891744 | 873104.629000 | 0.372671 | 0.635601 | 38.06% | 0.050387 | 5.15% | 0.633601 | 0.788257 | 1.155289 | 44.39% |
| UNDERFORECAST_ONLY | 31.00% | 32.04% | 36.84% | 15501 | 434028 | 559282.684000 | 0.399511 | 0.697363 | 31.00% | -0.169205 | -13.13% | 0.676525 | 0.866666 | 1.255463 | 62.22% |

## Matriz e prioridade ABC

| Célula | ABC | Venda train | Venda backtest | Séries | Previsões | D actual | MAE | RMSE | WAPE | Bias | Bias % | Desvio erro | p90 absoluto | p95 absoluto | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CENSORING_AND_UNDERFORECAST | A | 1.64% | 2.17% | 706 | 19768 | 32867.410000 | 0.603232 | 1.078815 | 36.28% | -0.249991 | -15.04% | 1.049477 | 1.299995 | 1.788510 | 61.39% |
| CENSORING_ONLY | A | 2.43% | 2.30% | 1071 | 29988 | 34947.188000 | 0.621964 | 0.983401 | 53.37% | 0.059665 | 5.12% | 0.981605 | 1.362687 | 1.902900 | 43.43% |
| NEITHER | A | 49.25% | 45.32% | 20732 | 580496 | 687975.339000 | 0.428804 | 0.725245 | 36.18% | 0.059246 | 5.00% | 0.722822 | 0.922225 | 1.358658 | 44.92% |
| UNDERFORECAST_ONLY | A | 26.72% | 31.14% | 10870 | 304360 | 472653.120000 | 0.457615 | 0.791844 | 29.47% | -0.200409 | -12.91% | 0.766065 | 1.006075 | 1.445455 | 62.88% |
| CENSORING_AND_UNDERFORECAST | B | 0.29% | 0.39% | 258 | 7224 | 5875.827000 | 0.458351 | 0.675967 | 56.35% | -0.210883 | -25.93% | 0.642274 | 1.033207 | 1.379520 | 58.72% |
| CENSORING_ONLY | B | 0.58% | 0.62% | 470 | 13160 | 9348.099000 | 0.450992 | 0.636065 | 63.49% | 0.033580 | 4.73% | 0.635202 | 1.007804 | 1.311113 | 42.37% |
| NEITHER | B | 10.19% | 9.08% | 8051 | 225428 | 137908.132000 | 0.271285 | 0.432903 | 44.34% | 0.033652 | 5.50% | 0.431594 | 0.554018 | 0.750000 | 43.46% |
| UNDERFORECAST_ONLY | B | 3.91% | 4.16% | 3381 | 94668 | 63120.288000 | 0.263034 | 0.394474 | 39.45% | -0.098523 | -14.78% | 0.381974 | 0.544433 | 0.724726 | 61.06% |
| CENSORING_AND_UNDERFORECAST | C | 0.06% | 0.09% | 64 | 1792 | 1293.420000 | 0.319786 | 0.424922 | 44.31% | -0.151698 | -21.02% | 0.397032 | 0.667247 | 0.849260 | 65.85% |
| CENSORING_ONLY | C | 0.08% | 0.09% | 82 | 2296 | 1310.410000 | 0.332397 | 0.475862 | 58.24% | 0.024059 | 4.22% | 0.475357 | 0.725457 | 0.920150 | 44.51% |
| NEITHER | C | 3.45% | 3.11% | 3065 | 85820 | 47221.158000 | 0.259301 | 0.384366 | 47.13% | 0.034425 | 6.26% | 0.382824 | 0.544454 | 0.733324 | 43.20% |
| UNDERFORECAST_ONLY | C | 1.41% | 1.55% | 1250 | 35000 | 23509.276000 | 0.263379 | 0.396569 | 39.21% | -0.089035 | -13.26% | 0.386450 | 0.558505 | 0.754538 | 59.70% |

**Duplo sinal: 1.028 séries (2,056%), 1,982% da venda normalizada train e 2,637% dos actuals do backtest.** A reúne 706 séries, 1,641% da venda train total; B reúne 258, 0,286% da venda train total. Juntas são 964 séries e 1,927% da venda train. São recortes para estudar na futura simulação, não recomendações de compra. A + duplo sinal tem bias −0,2500, RMSE 1,0788 e desvio 1,0495. Esses números não estimam demanda perdida.

## Composição XYZ e exposição da matriz

| Célula | XYZ | Séries | Venda train | Desvio erro |
|---|---|---|---|---|
| CENSORING_AND_UNDERFORECAST | X | 45 | 0.08% | 0.686273 |
| CENSORING_ONLY | X | 96 | 0.24% | 0.907501 |
| NEITHER | X | 8960 | 19.64% | 0.570918 |
| UNDERFORECAST_ONLY | X | 4016 | 8.65% | 0.564239 |
| CENSORING_AND_UNDERFORECAST | Y | 110 | 0.20% | 0.771791 |
| CENSORING_ONLY | Y | 273 | 0.64% | 0.980117 |
| NEITHER | Y | 10247 | 19.82% | 0.577403 |
| UNDERFORECAST_ONLY | Y | 5047 | 10.50% | 0.610545 |
| CENSORING_AND_UNDERFORECAST | Z | 873 | 1.70% | 0.961457 |
| CENSORING_ONLY | Z | 1254 | 2.21% | 0.846686 |
| NEITHER | Z | 12641 | 23.43% | 0.714052 |
| UNDERFORECAST_ONLY | Z | 6438 | 12.89% | 0.780939 |

| Célula | Exposição | Séries | Venda train | Desvio erro |
|---|---|---|---|---|
| CENSORING_AND_UNDERFORECAST | HIGH | 1028 | 1.98% | 0.932983 |
| CENSORING_ONLY | HIGH | 1623 | 3.09% | 0.874214 |
| NEITHER | HIGH | 6013 | 17.61% | 0.906143 |
| UNDERFORECAST_ONLY | HIGH | 3942 | 12.17% | 0.965357 |
| NEITHER | LOW | 9613 | 15.28% | 0.511848 |
| UNDERFORECAST_ONLY | LOW | 3978 | 6.30% | 0.522424 |
| NEITHER | MEDIUM | 16222 | 30.01% | 0.573179 |
| UNDERFORECAST_ONLY | MEDIUM | 7581 | 13.57% | 0.549938 |

Células com censura só aparecem em HIGH, por construção da flag. As combinações ausentes são estruturais, não classes nulas ou séries descartadas. Essa relação não constitui nova descoberta empírica.

## Duplo sinal e elevada incerteza

Para quantificar sobreposição, usam-se os p75 globais por série de cada uma das quatro medidas, somente como diagnóstico. Não é criada uma flag de compra, um score ou uma nova célula da matriz. Os thresholds são conhecidos após 25/06 e não podem retroagir nos folds.

| Grupo | Medida | p75 global | Séries | Acima ou igual p75 | Proporção |
|---|---|---|---|---|---|
| CENSORING_AND_UNDERFORECAST | error_std | 0.550570 | 1028 | 518 | 50.39% |
| CENSORING_AND_UNDERFORECAST | rmse | 0.567010 | 1028 | 529 | 51.46% |
| CENSORING_AND_UNDERFORECAST | p90_absolute_error | 0.883176 | 1028 | 543 | 52.82% |
| CENSORING_AND_UNDERFORECAST | p95_absolute_error | 1.055403 | 1028 | 536 | 52.14% |
| A_DOUBLE | error_std | 0.550570 | 706 | 398 | 56.37% |
| A_DOUBLE | rmse | 0.567010 | 706 | 406 | 57.51% |
| A_DOUBLE | p90_absolute_error | 0.883176 | 706 | 417 | 59.07% |
| A_DOUBLE | p95_absolute_error | 1.055403 | 706 | 409 | 57.93% |
| B_DOUBLE | error_std | 0.550570 | 258 | 118 | 45.74% |
| B_DOUBLE | rmse | 0.567010 | 258 | 118 | 45.74% |
| B_DOUBLE | p90_absolute_error | 0.883176 | 258 | 120 | 46.51% |
| B_DOUBLE | p95_absolute_error | 1.055403 | 258 | 120 | 46.51% |

São 518 séries com duplo sinal e desvio do erro ≥0,55057; 398 delas em A e 118 em B. A proporção é 50,39% no duplo sinal e 56,37% em A + duplo sinal. As alternativas RMSE/p90/p95 também são exibidas para evitar escolher a medida apenas pelo resultado favorável.

## Robustez temporal

| Fold | Séries | Previsões | D actual | MAE | RMSE | WAPE | Bias | Bias % | Desvio erro | p90 absoluto | p95 absoluto | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 50000 | 350000 | 363013.688000 | 0.358081 | 0.609330 | 34.52% | 0.025931 | 2.50% | 0.608778 | 0.762605 | 1.088890 | 46.51% |
| 2 | 50000 | 350000 | 366080.901000 | 0.401740 | 0.733230 | 38.41% | -0.010901 | -1.04% | 0.733150 | 0.845552 | 1.245073 | 48.54% |
| 3 | 50000 | 350000 | 370208.823000 | 0.370632 | 0.610242 | 35.04% | 0.015826 | 1.50% | 0.610038 | 0.803918 | 1.175249 | 47.38% |
| 4 | 50000 | 350000 | 418726.255000 | 0.432076 | 0.725749 | 36.12% | -0.125020 | -10.45% | 0.714901 | 0.941765 | 1.386714 | 58.45% |

| Fold | Exposição | RMSE | Bias % | Dias subprevistos |
|---|---|---|---|---|
| 1 | HIGH | 0.838586 | 1.47% | 48.72% |
| 1 | LOW | 0.536521 | 2.24% | 44.70% |
| 1 | MEDIUM | 0.493074 | 3.51% | 46.37% |
| 2 | HIGH | 1.082748 | -4.57% | 50.76% |
| 2 | LOW | 0.493008 | 2.56% | 46.05% |
| 2 | MEDIUM | 0.608009 | 0.32% | 48.78% |
| 3 | HIGH | 0.792053 | 0.67% | 48.70% |
| 3 | LOW | 0.506178 | -1.09% | 47.74% |
| 3 | MEDIUM | 0.551099 | 3.51% | 46.48% |
| 4 | HIGH | 1.007026 | -13.18% | 62.09% |
| 4 | LOW | 0.547207 | -5.49% | 53.61% |
| 4 | MEDIUM | 0.631159 | -10.21% | 59.29% |

| Fold | Flag | RMSE | Bias % | Dias subprevistos |
|---|---|---|---|---|
| 1 | False | 0.593490 | 2.48% | 46.50% |
| 1 | True | 0.843539 | 2.78% | 46.63% |
| 2 | False | 0.716491 | -0.61% | 48.47% |
| 2 | True | 0.985422 | -8.41% | 49.81% |
| 3 | False | 0.595888 | 1.72% | 47.30% |
| 3 | True | 0.825606 | -2.07% | 48.90% |
| 4 | False | 0.709289 | -10.39% | 58.64% |
| 4 | True | 0.973954 | -11.47% | 55.01% |

HIGH tem RMSE maior que LOW e MEDIUM em todos os folds; flag=True também tem RMSE maior que False nas quatro janelas. Isso sustenta a associação descritiva de magnitude, mas não um sinal de bias universal: HIGH tem bias positivo nos folds 1 e 3, e flag=True no fold 1. A frequência de subprevisão da flag é maior nos folds 1–3 e menor no fold 4. O duplo sinal tem bias agregado negativo nos quatro folds, lembrando que a seleção das séries usa o conjunto desses erros.

| Cenário | Séries | Previsões | D actual | MAE | RMSE | WAPE | Bias | Bias % | Desvio erro | p90 absoluto | p95 absoluto | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official_all | 50000 | 1400000 | 1518029.667000 | 0.390632 | 0.672312 | 36.03% | -0.023541 | -2.17% | 0.671900 | 0.837832 | 1.222739 | 50.22% |
| central_98pct_error | 50000 | 1372000 | 1364071.933000 | 0.336059 | 0.470528 | 33.80% | -0.020828 | -2.09% | 0.470067 | 0.760834 | 1.032172 | 50.22% |
| exclude_low_actual_p05 | 47499 | 1329972 | 1496988.619000 | 0.400094 | 0.686586 | 35.55% | -0.027808 | -2.47% | 0.686023 | 0.860019 | 1.254546 | 50.82% |
| omit_fold_1 | 50000 | 1050000 | 1155015.979000 | 0.401482 | 0.692034 | 36.50% | -0.040032 | -3.64% | 0.690876 | 0.864964 | 1.269528 | 51.46% |
| omit_fold_2 | 50000 | 1050000 | 1151948.766000 | 0.386930 | 0.650741 | 35.27% | -0.027754 | -2.53% | 0.650149 | 0.835476 | 1.216646 | 50.78% |
| omit_fold_3 | 50000 | 1050000 | 1147820.844000 | 0.397299 | 0.691766 | 36.34% | -0.036663 | -3.35% | 0.690794 | 0.849819 | 1.239998 | 51.16% |
| omit_fold_4 | 50000 | 1050000 | 1099303.412000 | 0.376817 | 0.653530 | 35.99% | 0.010285 | 0.98% | 0.653449 | 0.802454 | 1.168543 | 47.48% |

| Fold omitido | Persistentes oficiais | Mantêm bias<0 | 3 restantes negativos | ≥2 restantes negativos |
|---|---|---|---|---|
| 1 | 16529 | 15672 | 8259 | 16529 |
| 2 | 16529 | 15436 | 7458 | 16529 |
| 3 | 16529 | 15646 | 7785 | 16529 |
| 4 | 16529 | 14974 | 6131 | 16529 |

**O sinal do bias global depende do fold 4:** ao omiti-lo, passa de −0,02354 para +0,01029. Não se deve afirmar subprevisão global uniforme ao longo do tempo. Entretanto, entre as 16.529 séries persistentes oficiais, 14.974 (90,59%) continuam com bias consolidado negativo sem o fold 4; ao omitir qualquer outro fold, a retenção do sinal é de 93,39%–94,82%. Essa verificação não inventa uma regra equivalente para três folds nem substitui a classificação de quatro folds.

A sensibilidade central p1–p99 do erro mantém 98% das observações: RMSE cai de 0,6723 para 0,4705 e desvio de 0,6719 para 0,4701, mostrando influência importante das caudas. Bias continua negativo. As quatro células de risco também são comparadas nesse cenário no artefato de robustez. O duplo sinal mantém bias negativo (−0,1792) e RMSE maior que NEITHER (0,6092 contra 0,4499), mas fica praticamente empatado com CENSORING_ONLY (0,6102): a ordenação fina de RMSE depende das caudas. Excluir extremos condicionado ao próprio erro muda o estimando; esses números não substituem o resultado oficial. Nenhum outlier foi removido dos marts principais.

## Baixa escala e WAPE

| Grupo | Séries | D total | % actual | Persistentes | WAPE mediano | WAPE p95 | Desvio mediano |
|---|---|---|---|---|---|---|---|
| at_or_below_p05 | 2501 | 21041.048000 | 1.39% | 230 | 61.13% | 167.64% | 0.222359 |
| above_p05 | 47499 | 1496988.619000 | 98.61% | 16299 | 37.19% | 72.95% | 0.361823 |

O p05 da soma actual por série é 10,13; inclui empates e 2.501 séries (1,386% da venda do backtest). Seu WAPE mediano é 61,13%, contra 37,19% nas demais, mas desvio mediano menor: 0,2224 contra 0,3618. Há 230 persistentes nesse recorte. Nenhuma série é escolhida como risco somente pelo WAPE. Nenhum D por série é zero (mínimo 1,1); há 263 série×fold com D=0, cujos percentuais continuam nulos.

## Atividade promocional — análise complementar

| Escopo ABC | Métrica | Spearman com activity_rate | Séries |
|---|---|---|---|
| ALL | mae | -0.048535 | 50000 |
| ALL | bias | 0.052186 | 50000 |
| ALL | bias_pct | 0.049894 | 50000 |
| ALL | underforecast_rate | -0.029208 | 50000 |
| ALL | error_std | -0.046406 | 50000 |
| ALL | mean_demand | -0.002255 | 50000 |
| ALL | stockout_rate | -0.016611 | 50000 |
| A | mae | -0.151819 | 33379 |
| A | bias | 0.074632 | 33379 |
| A | bias_pct | 0.063551 | 33379 |
| A | underforecast_rate | -0.030952 | 33379 |
| A | error_std | -0.151829 | 33379 |
| A | mean_demand | -0.053264 | 33379 |
| A | stockout_rate | -0.055752 | 33379 |
| B | mae | 0.035831 | 12160 |
| B | bias | 0.018171 | 12160 |
| B | bias_pct | 0.025542 | 12160 |
| B | underforecast_rate | -0.031649 | 12160 |
| B | error_std | 0.038613 | 12160 |
| B | mean_demand | -0.034626 | 12160 |
| B | stockout_rate | 0.029784 | 12160 |
| C | mae | 0.200178 | 4461 |
| C | bias | 0.054042 | 4461 |
| C | bias_pct | 0.061434 | 4461 |
| C | underforecast_rate | -0.091503 | 4461 |
| C | error_std | 0.207988 | 4461 |
| C | mean_demand | -0.003116 | 4461 |
| C | stockout_rate | -0.057788 | 4461 |

Não se criaram bandas arbitrárias de atividade. Associação contínua com MAE/desvio é fraca no conjunto (≈−0,049/−0,046); em A é ≈−0,152. A comparação entre séries não equivale à associação diária da Fase 2 entre atividade, venda e ruptura. Não há uplift causal, novo modelo ou decisão baseada nesse sinal. Mantém-se como complemento e limitação, sem alterar a matriz.

## Exemplos reproduzíveis

| Regra | Loja | Produto | XYZ | D 28 dias | Bias | Desvio erro | Dias subprevistos | Ruptura histórica |
|---|---|---|---|---|---|---|---|---|
| A_NEITHER | 243 | 223 | X | 32.500000 | -0.043698 | 0.383335 | 50.00% | 40.00% |
| A_UNDERFORECAST_ONLY | 232 | 310 | X | 49.500000 | -0.296009 | 0.423207 | 78.57% | 67.78% |
| A_CENSORING_ONLY | 596 | 129 | Z | 16.300000 | 0.058056 | 0.593653 | 42.86% | 80.00% |
| A_CENSORING_AND_UNDERFORECAST | 360 | 600 | Z | 30.000000 | -0.397437 | 0.581170 | 78.57% | 82.22% |
| A_MAX_ERROR_STD | 550 | 267 | Z | 648.300000 | -1.602200 | 7.764284 | 60.71% | 94.44% |
| A_MAX_UNDERFORECAST_RATE | 305 | 300 | Z | 239.630000 | -2.143736 | 1.993540 | 96.43% | 54.44% |
| LOW_EXPOSURE_MIN_MAE | 503 | 500 | Z | 4.730000 | -0.016233 | 0.100884 | 57.14% | 33.33% |

Para cada célula entre séries A, escolhe-se a série mais próxima do desvio mediano daquela célula. Outros exemplos: maior desvio em A, maior taxa de subprevisão em A, menor MAE entre LOW. Todos os empates são resolvidos por loja/produto. O último exemplo é de baixa exposição relativa, não ausência de ruptura, e tem baixa escala. Exemplos não definem thresholds nem representam universalmente as células.

## Artefatos, notebook e reprodução

| Artefato | Caminho | Linhas | SHA-256 |
|---|---|---|---|
| uncertainty | data/processed/mart_forecast_uncertainty.parquet | 50000 | 2aaff8293974c0e7ddd1e2d5913c1534dc491e46e4d2fae1907c9f01c068de51 |
| risk_profile | data/processed/mart_demand_risk_profile.parquet | 50000 | b9ac3aaecae0633aed435b618a7e39d8e2912cf7e9375f1e10e21241bd919102 |
| calibration | data/processed/mart_error_calibration.parquet | 48 | cdfbf0126e54003587987c903bbaf559f11d974dd7f1f3e8be67167222d1d4be |
| series_fold | data/outputs/forecast_uncertainty/series_fold.parquet | 200000 | 34a8a8216a81141e50bd96fa155fb994b1a7229f8d172dcf339d1cde7d416ecd |
| risk_matrix | data/outputs/forecast_uncertainty/risk_matrix.parquet | 36 | 2bcd8560e936513867c0011d22d0da92bfa84786695d6cfd306557fcf3470524 |
| fold_diagnostics | data/outputs/forecast_uncertainty/fold_diagnostics.parquet | 40 | dec3433c9a6c6bd038ea8f00fcb7b0f905599a6673371f2b0417bc6ec9a4e61e |
| robustness | data/outputs/forecast_uncertainty/robustness.parquet | 19 | 0fc7ece9316f6d1880fcda65913a2d235fbc8a6e2cb2f4544feea692cd5f3c55 |
| persistence_retention | data/outputs/forecast_uncertainty/persistence_retention.parquet | 4 | d7350c19e489dc02b4a41d58e998636c1008087b12916000d1cc2578efc168fa |
| persistence_distribution | data/outputs/forecast_uncertainty/persistence_distribution.parquet | 5 | a8c01174dd25efedf01c9962d4618bd4b65c8e6ecf45fae0fc834cb0380c085e |
| persistence_sensitivity | data/outputs/forecast_uncertainty/persistence_sensitivity.parquet | 3 | ae72e048ef5e2f8915e9fc04e35e243d5e68d68986ac8ebec6eb9a5993beb1b3 |
| series_distributions | data/outputs/forecast_uncertainty/series_distributions.parquet | 8 | c45cf841ed6b53c96b39b0c93908fc407b226899e782d10614737424f94b44df |
| metric_correlations | data/outputs/forecast_uncertainty/metric_correlations.parquet | 48 | e118646a771dce2c8340253d2a144501760d96e8ddca7c9bc01bc74a3ac9e93e |
| high_uncertainty_diagnostics | data/outputs/forecast_uncertainty/high_uncertainty_diagnostics.parquet | 28 | 3ba4be2f53cfd4e074c05f4af1d90b4fc6beb8c0b387dbdee37c3425a469c031 |
| activity_associations | data/outputs/forecast_uncertainty/activity_associations.parquet | 28 | 2ec2499bdf7eb9e70545c677014bc44a14a79e9f67204aceff2f7d1066b72103 |
| low_scale_diagnostics | data/outputs/forecast_uncertainty/low_scale_diagnostics.parquet | 2 | dab99cf78f50929100c8bc7687e712ae7592425d9fdddfdb43e28483bae59422 |
| example_selection | data/outputs/forecast_uncertainty/example_selection.parquet | 7 | 8bebd4d94ffa08b3bc598f6b260630803e005aff53b306d4ed054361a8f4b92f |
| example_forecasts | data/outputs/forecast_uncertainty/example_forecasts.parquet | 196 | 0ddadb558efb70839beb9c628649e3bd14858bca48cfdb01e1fa06f68ceb71e0 |

Os marts de incerteza e risco têm grão store_id+product_id. O mart de calibração tem grão `level` + dimensões aplicáveis; contém 48 linhas, com dimensões não aplicáveis nulas. Filtrar level antes de agregar. Esses nulos estruturais não existem nas classes do mart de risco. Não há score numérico ou fórmula de safety stock.

```powershell
.\.venv\Scripts\python.exe scripts/build_forecast_risk_profile.py
.\.venv\Scripts\python.exe scripts/render_forecast_uncertainty.py
.\.venv\Scripts\python.exe -m pytest --basetemp=.tmp/pytest-phase6-final --deselect=tests/test_raw_quality.py::test_raw_files_manifest_hashes_and_schema --deselect=tests/test_raw_quality.py::test_staging_reproducible_from_full_raw
.\.venv\Scripts\python.exe -m pip check
git diff --check
git status
```

Notebook `05_forecast_uncertainty_and_risk.ipynb`: dez figuras consumindo somente outputs; nenhuma transformação crítica exclusiva de célula. A reprodução compara todos os Parquet e summary.json em uma raiz sem raw/eval e bloqueia chamadas de ajuste ETS. Tempo e pico de memória não entram na igualdade dos hashes.

## Limitações e implicações para a próxima decisão

Quatro folds não cobrem outras estações ou regimes. As 28 observações limitam caudas por série; amostras agregadas misturam escalas e dependências. Agrupar por labels de 25/06 é válido para diagnóstico e preparação de decisão posterior, não prova prospectiva em origens anteriores. A matriz combina sinais observados e parcialmente definidos pelo próprio erro, sem causalidade ou validação externa de risco futuro. O bias global é sensível à última janela e medidas quadráticas às caudas. Não corrigir forecasts a partir desses sinais.

Preservar error_std, RMSE, p90/p95 absolutos, bias, quantis assinados e underforecast_amount como possíveis entradas da futura simulação. Nenhuma medida foi escolhida para uma fórmula, e não se agregou erro de lead time sem testar dependência temporal. A/B com duplo sinal merecem investigação na etapa que vier a ser autorizada, sem compra, lost sales, reposição ou Power BI nesta entrega.

Execução tabular: 28.54 s; pico 1103.94 MiB; Parquet: 53,094,191 bytes. Nenhum novo fitting. HEAD de partida `6a7ccec`; sem commit.

## Validação final e recomendação

**106 testes aprovados, dois legados desmarcados, em 169,47 s.** As únicas exclusões são `test_raw_files_manifest_hashes_and_schema` e `test_staging_reproducible_from_full_raw`, pois abririam eval; seus arquivos foram preservados. Os oito testes da Fase 6 passaram, incluindo reprodução byte a byte dos 17 Parquet e de summary.json em raiz sem raw/eval, com ajuste ETS bloqueado. A suíte mantém os testes existentes de reprodução dos baselines e de seis ajustes ETS em temporários, sem reexecução populacional ETS ou alteração dos outputs oficiais. Código ETS, forecasts e comparação da Fase 5 permaneceram iguais por hash. Notebook íntegro: 11 células executadas, dez figuras, nenhum erro; inspeção visual concluída. `pip check` e `git diff --check` aprovados; stage vazio. Dados, outputs, ambiente e temporários ignorados, exceto os quatro marcadores `.gitkeep` preexistentes. Nenhum commit, acesso a eval ou avanço para reposição/Power BI.

**Recomendação técnica: Fase 6 aprovada para revisão como diagnóstico descritivo.** A regra de persistência proposta foi mantida; suas sensibilidades e limites estão explícitos. Aprovação desta entrega não autoriza holdout, reposição, estimativa de censura ou avanço automático.
