# Fase 7 — Final holdout evaluation

## Objetivo, autorização e protocolo congelado

Esta é a **primeira abertura analítica autorizada de eval**, após aprovação e commit das fases 0–6 em `d6681aa`. Verificações anteriores de ingestão/schema não constituíram avaliação preditiva. O holdout 26/06–02/07/2024 foi reservado para avaliar a metodologia, sem seleção, tuning ou recalibração. [Protocolo registrado antes da abertura](final_holdout_protocol.md). Target: venda observada normalizada, não demanda latente, receita ou unidades físicas. Esta fase não implementa reposição.

ETS A/N/A usa todo train de 28/03 a 25/06: 90 dias, sazonalidade aditiva de período sete, sem tendência, estados iniciais estimados, SLSQP/maxiter=200/ftol=1e-6/use_brute=False/remove_bias=False, uma thread numérica. Previsão direta de sete passos, sem atualização no horizonte. Seasonal Naive usa exclusivamente 19–25/06. Reutilizou-se a função ETS congelada, incluindo fallback e projeção de negativos em zero.

As 700.000 previsões sem actuals foram finalizadas em `2026-10-09T13:42:56.015549+00:00`; a abertura analítica foi registrada em `2026-10-09T13:43:37.663417+00:00`. Hash anterior à abertura: `d66ee703bbbc16d456da0a7befcd25815422b10e0fc025245f70f35b944d0dd0`. Releituras para testes/reprodução não criam outra seleção de modelo: a metodologia e as previsões permanecem iguais.

## Integridade e proveniência

| Linhas eval | Séries | Datas | Início | Fim | Grão único | Schema/hash | SHA-256 eval |
|---|---|---|---|---|---|---|---|
| 350000 | 50000 | 7 | 2024-06-26 | 2024-07-02 | True | True | 1b118840664280c6b88bffc84c80ee1f54c05d911e354b7599e5da10995e960e |

SHA-256 train: `6706832db892bbae4969c19d87e07975d2543d2ba7d7d4756360654785de5a3d`. SHA-256 protocolo: `d1827c791d68d267fe1290cce1ae47dc60fc48c0f7b1ace2b38e9148ce50ffb5`. Foram verificados os 53 artefatos protegidos das fases 3–6; nenhum foi sobrescrito. Cobertura de eval coincide exatamente com as 50.000 séries conhecidas. Labels e métricas históricas vêm dos marts de 25/06, agora disponíveis legitimamente antes da origem 26/06. Não foram recalculados usando eval.

## Métricas e comparação global

Erro=forecast−actual. MAE=Σ|e|/N; RMSE=√(Σe²/N); WAPE=Σ|e|/Σactual; bias=Σe/N; bias_pct=Σe/Σactual. Percentuais com denominador zero são nulos. Sem MAPE. Agregação pelas observações, sem média de WAPEs ou RMSEs por série. Improvement=(SN−ETS)/SN para MAE/RMSE/WAPE; referência zero mantém improvement nulo. Não há improvement relativo de bias assinado.

| Modelo | Séries | Previsões | Actual total | MAE | RMSE | WAPE | Bias | Bias % | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|
| ets_ana | 50000 | 350000 | 417568.523000 | 0.424983 | 0.711311 | 35.62% | -0.026863 | -2.25% | 51.66% |
| seasonal_naive | 50000 | 350000 | 417568.523000 | 0.499071 | 0.835819 | 41.83% | 0.003308 | 0.28% | 45.45% |

| Improvement MAE | Improvement RMSE | Improvement WAPE |
|---|---|---|
| 14.85% | 14.90% | 14.85% |

Não existe threshold prévio de aceitabilidade operacional do bias. Sua direção/magnitude são reportadas, sem declarar aceitabilidade para uma política de estoque ainda inexistente.

## Comparação com os quatro folds

| Modelo | Fold | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|
| ets_ana | 1 | 0.358081 | 0.609330 | 34.52% | 0.025931 | 2.50% |
| ets_ana | 2 | 0.401740 | 0.733230 | 38.41% | -0.010901 | -1.04% |
| ets_ana | 3 | 0.370632 | 0.610242 | 35.04% | 0.015826 | 1.50% |
| ets_ana | 4 | 0.432076 | 0.725749 | 36.12% | -0.125020 | -10.45% |
| seasonal_naive | 1 | 0.426069 | 0.729601 | 41.08% | 0.017375 | 1.68% |
| seasonal_naive | 2 | 0.458965 | 0.785785 | 43.88% | -0.008763 | -0.84% |
| seasonal_naive | 3 | 0.455944 | 0.755159 | 43.11% | -0.011794 | -1.12% |
| seasonal_naive | 4 | 0.493370 | 0.828341 | 41.24% | -0.138621 | -11.59% |

| Modelo | Métrica | Agregado backtest | Média folds | Mínimo | Máximo | Desvio amostral | Fold 4 | Holdout | Delta fold 4 | Delta agregado | Fora do intervalo |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ets_ana | mae | 0.390632 | 0.390632 | 0.358081 | 0.432076 | 0.033169 | 0.432076 | 0.424983 | -0.007093 | 0.034351 | False |
| ets_ana | rmse | 0.672312 | 0.669638 | 0.609330 | 0.733230 | 0.069179 | 0.725749 | 0.711311 | -0.014438 | 0.038998 | False |
| ets_ana | wape | 0.360260 | 0.360224 | 0.345244 | 0.384092 | 0.017238 | 0.361159 | 0.356215 | -0.004944 | -0.004045 | False |
| ets_ana | bias | -0.023541 | -0.023541 | -0.125020 | 0.025931 | 0.069414 | -0.125020 | -0.026863 | 0.098157 | -0.003322 | False |
| ets_ana | bias_pct | -0.021711 | -0.018740 | -0.104500 | 0.025001 | 0.059085 | -0.104500 | -0.022516 | 0.081984 | -0.000805 | False |
| seasonal_naive | mae | 0.458587 | 0.458587 | 0.426069 | 0.493370 | 0.027534 | 0.493370 | 0.499071 | 0.005701 | 0.040484 | True |
| seasonal_naive | rmse | 0.775595 | 0.774722 | 0.729601 | 0.828341 | 0.042490 | 0.828341 | 0.835819 | 0.007477 | 0.060224 | True |
| seasonal_naive | wape | 0.422931 | 0.423262 | 0.410795 | 0.438804 | 0.013855 | 0.412392 | 0.418314 | 0.005922 | -0.004617 | False |
| seasonal_naive | bias | -0.035451 | -0.035451 | -0.138621 | 0.017375 | 0.070016 | -0.138621 | 0.003308 | 0.141929 | 0.038759 | False |
| seasonal_naive | bias_pct | -0.032695 | -0.029661 | -0.115869 | 0.016752 | 0.058826 | -0.115869 | 0.002773 | 0.118642 | 0.035467 | False |

Na tabela de estabilidade, percentuais estão em proporção (0,01=1 ponto percentual); deltas são diferenças assinadas. Mínimo/máximo dos quatro folds não é intervalo de confiança. Apenas uma semana final foi avaliada.

## ABC

| abc_class | Modelo | Séries | Previsões | Actual total | MAE | RMSE | WAPE | Bias | Bias % | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|
| A | ets_ana | 33379 | 233653 | 339218.572000 | 0.494607 | 0.813112 | 34.07% | -0.028771 | -1.98% | 52.11% |
| A | seasonal_naive | 33379 | 233653 | 339218.572000 | 0.579390 | 0.957476 | 39.91% | 0.008297 | 0.57% | 45.81% |
| B | ets_ana | 12160 | 85120 | 58993.724000 | 0.293308 | 0.460650 | 42.32% | -0.025150 | -3.63% | 50.81% |
| B | seasonal_naive | 12160 | 85120 | 58993.724000 | 0.343590 | 0.520374 | 49.58% | -0.010002 | -1.44% | 44.73% |
| C | ets_ana | 4461 | 31227 | 19356.227000 | 0.262952 | 0.381496 | 42.42% | -0.017256 | -2.78% | 50.65% |
| C | seasonal_naive | 4461 | 31227 | 19356.227000 | 0.321907 | 0.481977 | 51.93% | 0.002254 | 0.36% | 44.73% |

## XYZ

| xyz_class | Modelo | Séries | Previsões | Actual total | MAE | RMSE | WAPE | Bias | Bias % | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|
| X | ets_ana | 13117 | 91819 | 113807.331000 | 0.397987 | 0.681361 | 32.11% | -0.070263 | -5.67% | 54.53% |
| X | seasonal_naive | 13117 | 91819 | 113807.331000 | 0.472873 | 0.816089 | 38.15% | -0.007516 | -0.61% | 45.90% |
| Y | ets_ana | 15677 | 109739 | 124650.231000 | 0.401093 | 0.664176 | 35.31% | -0.017735 | -1.56% | 51.99% |
| Y | seasonal_naive | 15677 | 109739 | 124650.231000 | 0.481005 | 0.807157 | 42.35% | 0.016213 | 1.43% | 45.37% |
| Z | ets_ana | 21206 | 148442 | 179110.961000 | 0.459343 | 0.761375 | 38.07% | -0.006766 | -0.56% | 49.64% |
| Z | seasonal_naive | 21206 | 148442 | 179110.961000 | 0.528631 | 0.868082 | 43.81% | 0.000463 | 0.04% | 45.24% |

## ABC × XYZ

| abc_class | xyz_class | Modelo | Séries | Previsões | Actual total | MAE | RMSE | WAPE | Bias | Bias % | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | X | ets_ana | 9012 | 63084 | 93445.343000 | 0.464994 | 0.786586 | 31.39% | -0.088724 | -5.99% | 55.46% |
| A | X | seasonal_naive | 9012 | 63084 | 93445.343000 | 0.552393 | 0.940766 | 37.29% | -0.010169 | -0.69% | 46.42% |
| A | Y | ets_ana | 10557 | 73899 | 101566.676000 | 0.472474 | 0.770748 | 34.38% | -0.016936 | -1.23% | 52.57% |
| A | Y | seasonal_naive | 10557 | 73899 | 101566.676000 | 0.563272 | 0.932602 | 40.98% | 0.024472 | 1.78% | 45.78% |
| A | Z | ets_ana | 13810 | 96670 | 144206.553000 | 0.530852 | 0.860311 | 35.59% | 0.001305 | 0.09% | 49.56% |
| A | Z | seasonal_naive | 13810 | 96670 | 144206.553000 | 0.609329 | 0.986610 | 40.85% | 0.007984 | 0.54% | 45.43% |
| B | X | ets_ana | 2966 | 20762 | 15119.719000 | 0.254518 | 0.354811 | 34.95% | -0.029028 | -3.99% | 52.25% |
| B | X | seasonal_naive | 2966 | 20762 | 15119.719000 | 0.300681 | 0.426013 | 41.29% | 0.000513 | 0.07% | 44.49% |
| B | Y | ets_ana | 3805 | 26635 | 17615.756000 | 0.256700 | 0.356492 | 38.81% | -0.016785 | -2.54% | 50.75% |
| B | Y | seasonal_naive | 3805 | 26635 | 17615.756000 | 0.314449 | 0.452639 | 47.54% | 0.003945 | 0.60% | 44.24% |
| B | Z | ets_ana | 5389 | 37723 | 26258.249000 | 0.340506 | 0.565505 | 48.92% | -0.028922 | -4.16% | 50.06% |
| B | Z | seasonal_naive | 5389 | 37723 | 26258.249000 | 0.387781 | 0.605370 | 55.71% | -0.025637 | -3.68% | 45.22% |
| C | X | ets_ana | 1139 | 7973 | 5242.269000 | 0.241411 | 0.351020 | 36.72% | -0.031578 | -4.80% | 53.10% |
| C | X | seasonal_naive | 1139 | 7973 | 5242.269000 | 0.292087 | 0.441143 | 44.42% | -0.007434 | -1.13% | 45.50% |
| C | Y | ets_ana | 1315 | 9205 | 5467.799000 | 0.245842 | 0.349471 | 41.39% | -0.026904 | -4.53% | 50.95% |
| C | Y | seasonal_naive | 1315 | 9205 | 5467.799000 | 0.302488 | 0.437847 | 50.92% | -0.014594 | -2.46% | 45.32% |
| C | Z | ets_ana | 2007 | 14049 | 8646.159000 | 0.286386 | 0.416589 | 46.53% | -0.002808 | -0.46% | 49.06% |
| C | Z | seasonal_naive | 2007 | 14049 | 8646.159000 | 0.351553 | 0.529425 | 57.12% | 0.018792 | 3.05% | 43.91% |

## Exposição histórica

| stockout_exposure | Modelo | Séries | Previsões | Actual total | MAE | RMSE | WAPE | Bias | Bias % | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|
| HIGH | ets_ana | 12606 | 88242 | 161913.783000 | 0.564431 | 0.964557 | 30.76% | -0.030681 | -1.67% | 51.30% |
| HIGH | seasonal_naive | 12606 | 88242 | 161913.783000 | 0.660046 | 1.140762 | 35.97% | 0.007115 | 0.39% | 45.79% |
| LOW | ets_ana | 13591 | 95137 | 81142.057000 | 0.368053 | 0.550566 | 43.15% | -0.020998 | -2.46% | 51.17% |
| LOW | seasonal_naive | 13591 | 95137 | 81142.057000 | 0.441051 | 0.662702 | 51.71% | -0.001912 | -0.22% | 46.09% |
| MEDIUM | ets_ana | 23803 | 166621 | 174512.683000 | 0.383638 | 0.630091 | 36.63% | -0.028190 | -2.69% | 52.13% |
| MEDIUM | seasonal_naive | 23803 | 166621 | 174512.683000 | 0.446947 | 0.726295 | 42.67% | 0.004272 | 0.41% | 44.91% |

## Possível censura histórica

| censoring_risk_flag | Modelo | Séries | Previsões | Actual total | MAE | RMSE | WAPE | Bias | Bias % | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|
| False | ets_ana | 47349 | 331443 | 391596.109000 | 0.411401 | 0.691496 | 34.82% | -0.023800 | -2.01% | 51.70% |
| False | seasonal_naive | 47349 | 331443 | 391596.109000 | 0.484090 | 0.811120 | 40.97% | 0.007595 | 0.64% | 45.31% |
| True | ets_ana | 2651 | 18557 | 25972.414000 | 0.667567 | 1.001205 | 47.70% | -0.081575 | -5.83% | 50.96% |
| True | seasonal_naive | 2651 | 18557 | 25972.414000 | 0.766647 | 1.193789 | 54.78% | -0.073274 | -5.24% | 48.02% |

## Persistência pré-holdout

| persistent_underforecast_flag | Modelo | Séries | Previsões | Actual total | MAE | RMSE | WAPE | Bias | Bias % | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|
| False | ets_ana | 33471 | 234297 | 241202.750000 | 0.400857 | 0.677026 | 38.94% | -0.022078 | -2.14% | 51.52% |
| False | seasonal_naive | 33471 | 234297 | 241202.750000 | 0.467347 | 0.788714 | 45.40% | -0.007671 | -0.75% | 45.86% |
| True | ets_ana | 16529 | 115703 | 176365.773000 | 0.473838 | 0.776112 | 31.09% | -0.036554 | -2.40% | 51.94% |
| True | seasonal_naive | 16529 | 115703 | 176365.773000 | 0.563310 | 0.923878 | 36.96% | 0.025539 | 1.68% | 44.63% |

## Matriz de risco pré-holdout

| demand_observation_risk_cell | Modelo | Séries | Previsões | Actual total | MAE | RMSE | WAPE | Bias | Bias % | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|
| CENSORING_AND_UNDERFORECAST | ets_ana | 1028 | 7196 | 12615.809000 | 0.711028 | 1.057252 | 40.56% | -0.036689 | -2.09% | 49.12% |
| CENSORING_AND_UNDERFORECAST | seasonal_naive | 1028 | 7196 | 12615.809000 | 0.806560 | 1.217108 | 46.01% | 0.001830 | 0.10% | 46.28% |
| CENSORING_ONLY | ets_ana | 1623 | 11361 | 13356.605000 | 0.640039 | 0.964020 | 54.44% | -0.110005 | -9.36% | 52.13% |
| CENSORING_ONLY | seasonal_naive | 1623 | 11361 | 13356.605000 | 0.741367 | 1.178780 | 63.06% | -0.120844 | -10.28% | 49.12% |
| NEITHER | ets_ana | 31848 | 222936 | 227846.145000 | 0.388668 | 0.659062 | 38.03% | -0.017597 | -1.72% | 51.49% |
| NEITHER | seasonal_naive | 31848 | 222936 | 227846.145000 | 0.453383 | 0.763518 | 44.36% | -0.001903 | -0.19% | 45.69% |
| UNDERFORECAST_ONLY | ets_ana | 15501 | 108507 | 163749.964000 | 0.458107 | 0.753769 | 30.36% | -0.036545 | -2.42% | 52.13% |
| UNDERFORECAST_ONLY | seasonal_naive | 15501 | 108507 | 163749.964000 | 0.547178 | 0.901063 | 36.26% | 0.027111 | 1.80% | 44.52% |

## As 706 séries A com duplo sinal

| Modelo | Séries | Previsões | Actual total | MAE | RMSE | WAPE | Bias | Bias % | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|
| ets_ana | 706 | 4942 | 10136.640000 | 0.772216 | 1.135618 | 37.65% | -0.082131 | -4.00% | 50.20% |
| seasonal_naive | 706 | 4942 | 10136.640000 | 0.875708 | 1.315359 | 42.69% | -0.027764 | -1.35% | 46.18% |

## Persistência: retenção prospectiva do sinal

| Flag prévia | Séries | Bias holdout negativo | Proporção | Actual zero |
|---|---|---|---|---|
| False | 33471 | 18172 | 54.29% | 60 |
| True | 16529 | 9276 | 56.12% | 1 |

Regra histórica preservada: bias consolidado negativo e ≥3 dos quatro folds com bias negativo. As 16.529 séries foram definidas antes de eval. A matriz cruza essa flag com possível censura: NEITHER, UNDERFORECAST_ONLY, CENSORING_ONLY, CENSORING_AND_UNDERFORECAST. Os 1.028 casos de duplo sinal e os 706 casos A não foram selecionados novamente. A retenção de sinal em sete dias é evidência descritiva; não significa demanda perdida, causalidade ou insuficiência comprovada de estoque.

## Incerteza histórica versus erro futuro

| Medida histórica | Erro holdout | Séries | Spearman |
|---|---|---|---|
| error_std | mae | 50000 | 0.726828 |
| error_std | rmse | 50000 | 0.735952 |
| rmse | mae | 50000 | 0.730036 |
| rmse | rmse | 50000 | 0.739605 |
| p90_absolute_error | mae | 50000 | 0.728400 |
| p90_absolute_error | rmse | 50000 | 0.737248 |
| p95_absolute_error | mae | 50000 | 0.725376 |
| p95_absolute_error | rmse | 50000 | 0.734899 |

| Medida histórica | Quartil | Corte q25 | Corte q50 | Corte q75 | Modelo | Séries | Previsões | Actual total | MAE | RMSE | WAPE | Bias | Bias % | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| error_std | 1 | 0.255446 | 0.352702 | 0.550570 | ets_ana | 12500 | 87500 | 47695.432000 | 0.207225 | 0.270684 | 38.02% | -0.037735 | -6.92% | 54.49% |
| error_std | 2 | 0.255446 | 0.352702 | 0.550570 | ets_ana | 12500 | 87500 | 62691.606000 | 0.270984 | 0.350656 | 37.82% | -0.032097 | -4.48% | 52.39% |
| error_std | 3 | 0.255446 | 0.352702 | 0.550570 | ets_ana | 12500 | 87500 | 89741.628000 | 0.380923 | 0.499412 | 37.14% | -0.035513 | -3.46% | 51.13% |
| error_std | 4 | 0.255446 | 0.352702 | 0.550570 | ets_ana | 12500 | 87500 | 217439.857000 | 0.840801 | 1.256268 | 33.83% | -0.002107 | -0.08% | 48.63% |
| error_std | 1 | 0.255446 | 0.352702 | 0.550570 | seasonal_naive | 12500 | 87500 | 47695.432000 | 0.240581 | 0.312915 | 44.14% | -0.014863 | -2.73% | 45.23% |
| error_std | 2 | 0.255446 | 0.352702 | 0.550570 | seasonal_naive | 12500 | 87500 | 62691.606000 | 0.326838 | 0.421446 | 45.62% | -0.002707 | -0.38% | 45.29% |
| error_std | 3 | 0.255446 | 0.352702 | 0.550570 | seasonal_naive | 12500 | 87500 | 89741.628000 | 0.459599 | 0.603820 | 44.81% | -0.005684 | -0.55% | 46.17% |
| error_std | 4 | 0.255446 | 0.352702 | 0.550570 | seasonal_naive | 12500 | 87500 | 217439.857000 | 0.969264 | 1.467733 | 39.00% | 0.036485 | 1.47% | 45.12% |
| rmse | 1 | 0.260504 | 0.360194 | 0.567010 | ets_ana | 12500 | 87500 | 47478.887000 | 0.207013 | 0.270225 | 38.15% | -0.038269 | -7.05% | 54.56% |
| rmse | 2 | 0.260504 | 0.360194 | 0.567010 | ets_ana | 12500 | 87500 | 62306.910000 | 0.270313 | 0.349484 | 37.96% | -0.031711 | -4.45% | 52.37% |
| rmse | 3 | 0.260504 | 0.360194 | 0.567010 | ets_ana | 12500 | 87500 | 88646.869000 | 0.380735 | 0.499061 | 37.58% | -0.035727 | -3.53% | 51.12% |
| rmse | 4 | 0.260504 | 0.360194 | 0.567010 | ets_ana | 12500 | 87500 | 219135.857000 | 0.841871 | 1.256833 | 33.62% | -0.001745 | -0.07% | 48.59% |
| rmse | 1 | 0.260504 | 0.360194 | 0.567010 | seasonal_naive | 12500 | 87500 | 47478.887000 | 0.240691 | 0.312976 | 44.36% | -0.014210 | -2.62% | 45.19% |
| rmse | 2 | 0.260504 | 0.360194 | 0.567010 | seasonal_naive | 12500 | 87500 | 62306.910000 | 0.326038 | 0.420355 | 45.79% | -0.002112 | -0.30% | 45.25% |
| rmse | 3 | 0.260504 | 0.360194 | 0.567010 | seasonal_naive | 12500 | 87500 | 88646.869000 | 0.459798 | 0.603560 | 45.38% | -0.005645 | -0.56% | 46.22% |
| rmse | 4 | 0.260504 | 0.360194 | 0.567010 | seasonal_naive | 12500 | 87500 | 219135.857000 | 0.969756 | 1.468140 | 38.72% | 0.035199 | 1.41% | 45.15% |
| p90_absolute_error | 1 | 0.407686 | 0.562807 | 0.883176 | ets_ana | 12500 | 87500 | 47868.640000 | 0.209087 | 0.273221 | 38.22% | -0.036909 | -6.75% | 54.33% |
| p90_absolute_error | 2 | 0.407686 | 0.562807 | 0.883176 | ets_ana | 12500 | 87500 | 61942.024000 | 0.269241 | 0.349842 | 38.03% | -0.031944 | -4.51% | 52.39% |
| p90_absolute_error | 3 | 0.407686 | 0.562807 | 0.883176 | ets_ana | 12500 | 87500 | 88673.321000 | 0.378017 | 0.496425 | 37.30% | -0.035089 | -3.46% | 51.19% |
| p90_absolute_error | 4 | 0.407686 | 0.562807 | 0.883176 | ets_ana | 12500 | 87500 | 219084.538000 | 0.843588 | 1.257129 | 33.69% | -0.003510 | -0.14% | 48.72% |
| p90_absolute_error | 1 | 0.407686 | 0.562807 | 0.883176 | seasonal_naive | 12500 | 87500 | 47868.640000 | 0.244325 | 0.321078 | 44.66% | -0.011874 | -2.17% | 44.99% |
| p90_absolute_error | 2 | 0.407686 | 0.562807 | 0.883176 | seasonal_naive | 12500 | 87500 | 61942.024000 | 0.326367 | 0.430370 | 46.10% | -0.000813 | -0.11% | 45.39% |
| p90_absolute_error | 3 | 0.407686 | 0.562807 | 0.883176 | seasonal_naive | 12500 | 87500 | 88673.321000 | 0.456972 | 0.604336 | 45.09% | -0.005852 | -0.58% | 46.15% |
| p90_absolute_error | 4 | 0.407686 | 0.562807 | 0.883176 | seasonal_naive | 12500 | 87500 | 219084.538000 | 0.968619 | 1.463161 | 38.69% | 0.031771 | 1.27% | 45.28% |
| p95_absolute_error | 1 | 0.476838 | 0.664517 | 1.055403 | ets_ana | 12500 | 87500 | 47763.515000 | 0.208545 | 0.271819 | 38.20% | -0.037780 | -6.92% | 54.44% |
| p95_absolute_error | 2 | 0.476838 | 0.664517 | 1.055403 | ets_ana | 12500 | 87500 | 62111.071000 | 0.271420 | 0.352577 | 38.24% | -0.031890 | -4.49% | 52.38% |
| p95_absolute_error | 3 | 0.476838 | 0.664517 | 1.055403 | ets_ana | 12500 | 87500 | 88185.958000 | 0.379625 | 0.499204 | 37.67% | -0.034051 | -3.38% | 51.05% |
| p95_absolute_error | 4 | 0.476838 | 0.664517 | 1.055403 | ets_ana | 12500 | 87500 | 219507.979000 | 0.840342 | 1.255568 | 33.50% | -0.003731 | -0.15% | 48.77% |
| p95_absolute_error | 1 | 0.476838 | 0.664517 | 1.055403 | seasonal_naive | 12500 | 87500 | 47763.515000 | 0.243498 | 0.318960 | 44.61% | -0.012967 | -2.38% | 45.04% |
| p95_absolute_error | 2 | 0.476838 | 0.664517 | 1.055403 | seasonal_naive | 12500 | 87500 | 62111.071000 | 0.327283 | 0.430134 | 46.11% | -0.001904 | -0.27% | 45.41% |
| p95_absolute_error | 3 | 0.476838 | 0.664517 | 1.055403 | seasonal_naive | 12500 | 87500 | 88185.958000 | 0.457970 | 0.604909 | 45.44% | -0.003841 | -0.38% | 45.99% |
| p95_absolute_error | 4 | 0.476838 | 0.664517 | 1.055403 | seasonal_naive | 12500 | 87500 | 219507.979000 | 0.967532 | 1.463457 | 38.57% | 0.031943 | 1.27% | 45.37% |

Cortes calculados e registrados exclusivamente nos perfis históricos antes da abertura: empates ficam juntos, sem forçar tamanhos iguais. Associações podem refletir escala de venda e dependência entre séries. Não se convertem em intervalo preditivo, nível de serviço ou fórmula de estoque; nenhuma medida foi recalibrada.

## Baixa escala

| Baixa escala histórica | Modelo | Séries | Previsões | Actual total | MAE | RMSE | WAPE | Bias | Bias % | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|
| False | ets_ana | 47499 | 332493 | 410744.673000 | 0.435902 | 0.726013 | 35.29% | -0.024678 | -2.00% | 51.48% |
| True | ets_ana | 2501 | 17507 | 6823.850000 | 0.217611 | 0.323436 | 55.83% | -0.068361 | -17.54% | 55.10% |
| False | seasonal_naive | 47499 | 332493 | 410744.673000 | 0.512205 | 0.853311 | 41.46% | 0.007317 | 0.59% | 45.29% |
| True | seasonal_naive | 2501 | 17507 | 6823.850000 | 0.249634 | 0.370742 | 64.05% | -0.072831 | -18.69% | 48.64% |

Baixa escala usa actual_total histórico ≤10,13 nos 28 dias da Fase 6; não usa um novo corte de eval. Há 61 séries com actual total zero no holdout; seus WAPE/bias_pct ficam nulos. Métricas absolutas acompanham WAPE; nenhum outlier foi removido e não se define risco somente pelo percentual.

## Ruptura contemporânea — análise separada

| Ruptura no próprio dia eval | Modelo | Séries | Previsões | Actual total | MAE | RMSE | WAPE | Bias | Bias % | Dias subprevistos |
|---|---|---|---|---|---|---|---|---|---|---|
| False | ets_ana | 50000 | 206562 | 255541.230000 | 0.401634 | 0.673414 | 32.47% | -0.052559 | -4.25% | 49.22% |
| True | ets_ana | 44126 | 143438 | 162027.293000 | 0.458608 | 0.762583 | 40.60% | 0.010141 | 0.90% | 55.18% |
| False | seasonal_naive | 50000 | 206562 | 255541.230000 | 0.481350 | 0.797899 | 38.91% | -0.009497 | -0.77% | 42.59% |
| True | seasonal_naive | 44126 | 143438 | 162027.293000 | 0.524591 | 0.887584 | 46.44% | 0.021748 | 1.93% | 49.57% |

Este agrupamento usa stock_hour6_22_cnt>0 observado **depois** das previsões, somente para descrição. É por observação: uma série pode participar dos dois grupos, cujas contagens de séries não são aditivas. Não é validação prospectiva de uma nova feature. Não modifica forecast, exposição/flag histórica ou thresholds, e não permite estimar lost sales.

## Exemplos e distribuição de vantagem por série

| Regra da Fase 6 | Loja | Produto |
|---|---|---|
| A_CENSORING_AND_UNDERFORECAST | 360 | 600 |
| A_CENSORING_ONLY | 596 | 129 |
| A_MAX_ERROR_STD | 550 | 267 |
| A_MAX_UNDERFORECAST_RATE | 305 | 300 |
| A_NEITHER | 243 | 223 |
| A_UNDERFORECAST_ONLY | 232 | 310 |
| LOW_EXPOSURE_MIN_MAE | 503 | 500 |

Foram reutilizados todos os sete exemplos da Fase 6, sem seleção por resultado interessante em eval. Eles são ilustrativos, não amostra representativa; escalas e denominadores diferem.

| Métrica | Séries válidas | ETS vence | SN vence | Empates | Indefinidas | Improvement válido | p25 | Mediana | p75 |
|---|---|---|---|---|---|---|---|---|---|
| mae | 50000 | 36118 | 13882 | 0 | 0 | 49940 | -2.36% | 15.84% | 31.49% |
| rmse | 50000 | 37731 | 12269 | 0 | 0 | 49940 | 0.47% | 17.00% | 31.48% |
| wape | 49939 | 36117 | 13822 | 0 | 61 | 49939 | -2.36% | 15.84% | 31.49% |

Empates usam atol=1e-12/rtol=1e-10, preservando a Fase 5. Comparação direta pode ser definida quando improvement relativo não é (referência zero); por isso os denominadores são separados.

## Fallback, clipping e custo

50,000 ajustes solicitados; 0 fallbacks; razões: `{}`. Clipping negativo em 1504 forecasts ETS, envolvendo 791 séries. Modelo solicitado/usado, motivo, forecast matemático original e indicador de clipping permanecem por linha.

Ajustes: 409.53 s; população com I/O: 425.99 s; avaliação: 19.67 s. Pico população: 378.49 MiB; pico avaliação: 988.18 MiB. Parquet de avaliação: 39,355,460 bytes; previsões pré-eval: 7,851,014 bytes. Limite DuckDB não equivale à memória do processo inteiro.

## Artefatos e reprodução

| Artefato | Caminho | Linhas | SHA-256 |
|---|---|---|---|
| forecasts | data/processed/mart_holdout_forecast.parquet | 700000 | fad7ab566c90ef41e8474b689d11186f2edc01d02bfe17b545e6bff4dd1ba3b8 |
| series_evaluation | data/processed/mart_holdout_series_evaluation.parquet | 100000 | 6129f8f98fc93b4f2f75cb4e309218c5a44f7e3ea905952b9cfd0bdd5f7dae10 |
| model_comparison | data/processed/mart_holdout_model_comparison.parquet | 56 | 392fb14c9f60845500c590e21db201293f396df4199570988f1ae77ca35c17c7 |
| paired_comparison | data/outputs/final_holdout/paired_comparison.parquet | 28 | 68fc568f795a5eb30afd1829da450a5e3bdeda03ece4be7663af9d3516acdc89 |
| series_comparison | data/outputs/final_holdout/series_comparison.parquet | 50000 | 6a40eb58d0566fde36bd07ee8a8e78c4fc4001748222cbf5ae8dd7c5d9670fc7 |
| uncertainty_association | data/outputs/final_holdout/uncertainty_association.parquet | 8 | b867039ce4561cd3a88118a310470a1724ec3f26ba045ef135a01f2ec2ee0cf6 |
| uncertainty_quartiles | data/outputs/final_holdout/uncertainty_quartiles.parquet | 32 | a47ab86417854544398622fec30f6facf1a2276e1761105f771f7dfe2e7c2b59 |
| persistence_retention | data/outputs/final_holdout/persistence_retention.parquet | 2 | c316bac7afb98c7bba206ea5d095311293ae5b0abef475e6db02c236b88d91db |
| backtest_comparison | data/outputs/final_holdout/backtest_comparison.parquet | 10 | 8d876fa8d86cc394fc79b72a0c6d94e19681564eb810f77211be617ed6375d4d |
| low_scale | data/outputs/final_holdout/low_scale.parquet | 4 | afb387c57edecf66593f3dbf1c21e4d5cc91c02f91993ae579064334f48d2e8e |
| contemporary_stockout | data/outputs/final_holdout/contemporary_stockout.parquet | 4 | 2a29c6064b2f6d277cb0d2e8693fea328caa22153a2444982311b7eae1a09bcb |
| win_rates | data/outputs/final_holdout/win_rates.parquet | 3 | 575f1e8b67948951e57e3a2653784e61393a3f024249c56c447b6c70bffdc49a |
| example_forecasts | data/outputs/final_holdout/example_forecasts.parquet | 98 | cb659c29554f2450c83f96035e004bedf30fbd35849bd51a5ec48643204e9adc |

Grãos: forecast = dt+loja+produto+modelo (700.000 linhas); série = loja+produto+modelo (100.000); comparação = level+dimensões aplicáveis+modelo. Filtrar level; dimensões não aplicáveis são nulos estruturais. A_DOUBLE é subconjunto adicional e não deve ser somado aos níveis populacionais. O mart de comparação guarda métricas de ambos os modelos; paired_comparison guarda improvements pareados.

```powershell
# Somente primeira execução autorizada, antes de abrir eval:
.\.venv\Scripts\python.exe scripts/run_final_holdout.py --fit-only
# Reproduzir avaliação sem repetir ajustes:
.\.venv\Scripts\python.exe scripts/run_final_holdout.py --evaluate-only
.\.venv\Scripts\python.exe scripts/render_final_holdout.py
.\.venv\Scripts\python.exe -m pytest --basetemp=.tmp/pytest-phase7-final
.\.venv\Scripts\python.exe -m pip check
git diff --check
git status
```

O runner recusa nova execução se existem previsões, parcial ou execução registrada. A avaliação é reproduzida em raiz sem train, com fitting bloqueado; hashes dos Parquet e summary.json devem coincidir. Tempos/timestamps ficam separados. Código congelado e 53 artefatos anteriores são verificados.

## Limitações e conclusão

Uma única semana não cobre sazonalidades longas, mudanças de regime ou condições operacionais futuras. Erros são medidos contra venda possivelmente censurada, não demanda latente. Classes históricas são conhecidas na origem, mas relações prospectivas são descritivas, com dependência entre lojas/produtos/dias. As medidas de incerteza partem de 28 erros por série; Spearman e quartis podem refletir escala. Eval deixou de ser holdout intocado: não pode orientar retuning e depois ser apresentado como novo teste independente. Nova seleção exigiria desenho de validação futuro. Nenhuma política de estoque foi criada.

**Classificação: B — confirmação parcial da metodologia conjunta.**

A vantagem de erro do ETS recebeu forte confirmação fora da amostra: MAE/WAPE melhoram 14,85% e RMSE 14,90% frente ao Seasonal Naive, com ganho nas três métricas em todos os segmentos predefinidos. WAPE ETS de 35,62% está dentro da faixa dos folds (34,52%–38,41%), abaixo da média de 36,02% e do fold 4 (36,12%). MAE/RMSE são maiores que no agregado do backtest, mas permanecem dentro da faixa dos folds; nenhuma falha ou fallback ocorreu. Porém, o bias_pct ETS de −2,25% fica mais distante de zero que o +0,28% do Seasonal Naive. Não existe threshold anterior que permita declarar esse bias operacionalmente aceitável. A classificação conjunta B expressa confirmação parcial das regras de risco e a ressalva de bias; não significa ganho de erro pequeno ou inferioridade preditiva do ETS. Não se escolheu um limite numérico retrospectivo nem se alterou a metodologia.

As 16.529 persistentes apresentam bias mais negativo e frequência de subprevisão apenas ligeiramente maior: −0,03655/−2,40%/51,94%, contra −0,02208/−2,14%/51,52% nas demais. Mantêm bias negativo 9.276 séries (56,12%), contra 54,29% das não persistentes: separação prospectiva fraca. Duplo sinal tem MAE/RMSE maiores que NEITHER (0,7110/1,0573 contra 0,3887/0,6591) e bias mais negativo, mas menor underforecast_rate (49,12% contra 51,49%); CENSORING_ONLY tem bias_pct ainda mais negativo (−9,36%). Portanto, não se confirmou uma ordenação uniforme de subprevisão pela matriz. A flag de possível censura continua associada a maior magnitude de erro, sem maior frequência global de dias subprevistos. Já a incerteza histórica se associa ao erro futuro: Spearman aproximadamente 0,725–0,740 e crescimento monotônico de MAE/RMSE nos quatro quartis congelados. Isso é associação descritiva, também influenciada por escala; não comprova demanda perdida, causalidade ou suficiência de estoque. As flags, os quartis e os exemplos permanecem inalterados.

Notebook executado: dez figuras, 15.74 s, 935,417 bytes; sem ajustes ou leitura de raw nas células.

## Validação final

**118 testes aprovados, zero falhas, zero erros e nenhuma exclusão**, conforme o XML final (203,21 s). Os dez testes da Fase 7 passaram, incluindo reprodução dos 13 Parquet e summary.json em raiz sem train, com fitting bloqueado. Os dois testes legados de ingestão/staging voltaram a ser executados após a autorização de abertura de eval. Nenhum código/teste mudou depois dessa suíte; a retomada confirmou os registros sem repetir testes ou forecasting. Os hashes de previsões, outputs e dos 53 artefatos anteriores continuam iguais. Notebook: 11 células executadas, dez figuras, zero erros; inspeção visual concluida. `pip check` e `git diff --check` aprovados; stage vazio. Dados, outputs, ambiente e temporários ignorados, exceto marcadores `.gitkeep` preexistentes. Nenhum commit ou avanço para reposição/Power BI.

### Totais globais auditados

| Modelo | Actual total | Forecast total | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|
| ets_ana | 417568.523000 | 408166.462994 | 0.424983 | 0.711311 | 35.62% | -0.026863 | -2.25% |
| seasonal_naive | 417568.523000 | 418726.255000 | 0.499071 | 0.835819 | 41.83% | 0.003308 | 0.28% |

Os totais e métricas acima vêm diretamente dos outputs existentes, sem arredondamento interno. A apresentação decimal não altera os valores armazenados.

### Correção técnica de datas e trilha one-shot

Antes da primeira abertura analítica, o teste sintético detectou date do Parquet versus timestamp do DuckDB. Foi normalizada apenas a representação da chave dt na junção posterior, sem modificar forecasts, regras, tolerancias ou metodologia. `protocol_at_fit_start.json` e `protocol_amendment.json` preservam a trilha anterior/final. Após a abertura, a mesma representação foi normalizada somente na junção t-7 do teste; essa versão passou na suíte de 118 testes.

**Recomendação técnica: Fase 7 aprovada para revisão**, com classificação **B — confirmação parcial** da evidência conjunta. A vantagem de erro do ETS foi fortemente confirmada; a validação das flags foi limitada e o bias do baseline ficou mais próximo de zero. As regras foram preservadas e nenhum resultado desfavorável foi usado para recalibração.
