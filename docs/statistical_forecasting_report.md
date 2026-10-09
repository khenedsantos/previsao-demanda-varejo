# Fase 5 — Comparação populacional ETS A/N/A versus Seasonal Naive

## Escopo e proveniência

Execução autorizada de **50.000 séries × quatro folds = 200.000 ajustes solicitados**, com sete previsões por ajuste. Somente A/N/A foi executado nesta continuação. O limite de engenharia inicial de 30 minutos foi explicitamente revogado pelo usuário. O benchmark anterior permanece como proveniência; não foi repetido. HEAD de partida: `4dfaa9d`; sem commit nesta fase.

Target `sale_amount`: **venda observada normalizada**, não demanda latente, unidades físicas ou receita. Eval não participa de ajuste, segmentação, métricas, escolha, exemplos ou notebook. A verificação de fonte seleciona exclusivamente a entrada train do manifesto. Os snapshots prospectivos e forecasts Seasonal Naive da Fase 4 são verificados por SHA-256 e reutilizados, sem duplicar o mart de forecasts daquela fase.

| Fold | Cutoff | Dias de histórico | Origem | Último target |
|---|---|---|---|---|
| 1 | 2024-05-28 | 62 | 2024-05-29 | 2024-06-04 |
| 2 | 2024-06-04 | 69 | 2024-06-05 | 2024-06-11 |
| 3 | 2024-06-11 | 76 | 2024-06-12 | 2024-06-18 |
| 4 | 2024-06-18 | 83 | 2024-06-19 | 2024-06-25 |

Origem é o primeiro dia previsto, antes de observar sua venda. Históricos começam em 28/03/2024; o filtro até o cutoff acontece na SQL antes da agregação. Actuals futuros só são unidos depois do forecast pronto. Não se usa a segmentação full-train dos 90 dias nas decisões prospectivas.

## Modelo, fallback e clipping

Holt-Winters A/N/A: sem tendência; sazonalidade aditiva; `seasonal_periods=7`; inicialização estimada. SLSQP, `maxiter=200`, `ftol=1e-6`, `use_brute=False`, `remove_bias=False`, sem Box-Cox. O módulo `ets.py` e sua configuração permanecem os mesmos do benchmark. Não houve tuning ou avaliação de A/A/A nesta execução.

Fallback Seasonal Naive usa somente os últimos sete dias disponíveis. Motivos possíveis: histórico constante, sazonal insuficiente, não convergência, forecast não finito ou exceção numérica de ajuste. Histórico inválido bloqueia o cálculo. `model_requested`, `model_used`, `fallback_flag`, `fallback_reason`, convergência e avisos são preservados. O candidato é avaliado incluindo fallback, sem descartar séries.

Projeção de negativos em zero preserva `forecast_unclipped` e `negative_clipped`. Não altera o histórico nem representa falha. A magnitude abaixo é o aumento da previsão provocado exclusivamente por essa projeção.

| Nível | Fold | Solicitados | Fallback | Taxa fallback | Forecasts clipping | Ajustes com clipping | Taxa clipping | Menor original | Magnitude média | Projeção total |
|---|---|---|---|---|---|---|---|---|---|---|
| global | indefinido | 200000 | 0 | 0.00% | 4149 | 2191 | 0.30% | -1.091927 | 0.099808 | 414.104775 |
| fold | 1.000000 | 50000 | 0 | 0.00% | 1109 | 566 | 0.32% | -0.931073 | 0.106814 | 118.457181 |
| fold | 2.000000 | 50000 | 0 | 0.00% | 1270 | 637 | 0.36% | -0.809988 | 0.095200 | 120.903740 |
| fold | 3.000000 | 50000 | 0 | 0.00% | 914 | 472 | 0.26% | -1.027349 | 0.101707 | 92.959763 |
| fold | 4.000000 | 50000 | 0 | 0.00% | 856 | 516 | 0.24% | -1.091927 | 0.095542 | 81.784092 |

Motivos observados: nenhum fallback populacional.

## Métricas e denominadores

Para e = forecast − actual, N = número de previsões e D = soma(actual): MAE = soma(abs(e))/N; RMSE = sqrt(soma(e²)/N); WAPE = soma(abs(e))/D; bias = soma(e)/N; bias_pct = soma(e)/D. Bias negativo significa subprevisão. WAPE/bias_pct são nulos quando D=0; os erros absolutos continuam definidos. Não há MAPE. Consolidar significa somar erros e actuals, nunca tirar média ingênua dos WAPEs ou RMSEs das séries.

Melhoria = (Seasonal Naive − ETS) / Seasonal Naive, somente para MAE/RMSE/WAPE. Referência zero torna a melhoria indefinida. Não há melhoria relativa de bias assinado. `mart_model_comparison` guarda os dois valores, somas suficientes, denominadores, melhoria e vencedor pareados. Dimensões não aplicáveis ficam nulas; sempre filtrar `level` antes de agregar.

## Global

| Modelo | N | D | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|
| ets_ana | 1400000 | 1518029.667000 | 0.390632 | 0.672312 | 36.03% | -0.023541 | -2.17% |
| seasonal_naive | 1400000 | 1518029.667000 | 0.458587 | 0.775595 | 42.29% | -0.035451 | -3.27% |

| Ganho MAE | Ganho RMSE | Ganho WAPE |
|---|---|---|
| 14.82% | 13.32% | 14.82% |

## Quatro folds

| Fold | Modelo | N | D | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|---|
| 1.000000 | ets_ana | 350000 | 363013.688000 | 0.358081 | 0.609330 | 34.52% | 0.025931 | 2.50% |
| 1.000000 | seasonal_naive | 350000 | 363013.688000 | 0.426069 | 0.729601 | 41.08% | 0.017375 | 1.68% |
| 2.000000 | ets_ana | 350000 | 366080.901000 | 0.401740 | 0.733230 | 38.41% | -0.010901 | -1.04% |
| 2.000000 | seasonal_naive | 350000 | 366080.901000 | 0.458965 | 0.785785 | 43.88% | -0.008763 | -0.84% |
| 3.000000 | ets_ana | 350000 | 370208.823000 | 0.370632 | 0.610242 | 35.04% | 0.015826 | 1.50% |
| 3.000000 | seasonal_naive | 350000 | 370208.823000 | 0.455944 | 0.755159 | 43.11% | -0.011794 | -1.12% |
| 4.000000 | ets_ana | 350000 | 418726.255000 | 0.432076 | 0.725749 | 36.12% | -0.125020 | -10.45% |
| 4.000000 | seasonal_naive | 350000 | 418726.255000 | 0.493370 | 0.828341 | 41.24% | -0.138621 | -11.59% |

| Fold | Ganho MAE | Ganho RMSE | Ganho WAPE |
|---|---|---|---|
| 1.000000 | 15.96% | 16.48% | 15.96% |
| 2.000000 | 12.47% | 6.69% | 12.47% |
| 3.000000 | 18.71% | 19.19% | 18.71% |
| 4.000000 | 12.42% | 12.39% | 12.42% |

## ABC

| ABC | Modelo | N | D | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|---|
| A | ets_ana | 939274 | 1229245.357000 | 0.446714 | 0.764135 | 34.13% | -0.030631 | -2.34% |
| A | seasonal_naive | 939274 | 1229245.357000 | 0.521827 | 0.875359 | 39.87% | -0.045215 | -3.45% |
| B | ets_ana | 336049 | 215394.586000 | 0.281113 | 0.441008 | 43.86% | -0.009865 | -1.54% |
| B | seasonal_naive | 336049 | 215394.586000 | 0.333641 | 0.527947 | 52.05% | -0.017362 | -2.71% |
| C | ets_ana | 124677 | 73389.724000 | 0.263320 | 0.390411 | 44.73% | -0.006991 | -1.19% |
| C | seasonal_naive | 124677 | 73389.724000 | 0.318935 | 0.480436 | 54.18% | -0.010651 | -1.81% |

| ABC | Ganho MAE | Ganho RMSE | Ganho WAPE |
|---|---|---|---|
| A | 14.39% | 12.71% | 14.39% |
| B | 15.74% | 16.47% | 15.74% |
| C | 17.44% | 18.74% | 17.44% |

## XYZ

| XYZ | Modelo | N | D | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|---|
| X | ets_ana | 371203 | 421301.021000 | 0.374110 | 0.624522 | 32.96% | -0.029177 | -2.57% |
| X | seasonal_naive | 371203 | 421301.021000 | 0.441591 | 0.735678 | 38.91% | -0.037770 | -3.33% |
| Y | ets_ana | 442162 | 458247.963000 | 0.371165 | 0.624317 | 35.81% | -0.005683 | -0.55% |
| Y | seasonal_naive | 442162 | 458247.963000 | 0.433479 | 0.722036 | 41.83% | -0.026789 | -2.58% |
| Z | ets_ana | 586635 | 638480.683000 | 0.415760 | 0.733571 | 38.20% | -0.033435 | -3.07% |
| Z | seasonal_naive | 586635 | 638480.683000 | 0.488266 | 0.836766 | 44.86% | -0.040512 | -3.72% |

| XYZ | Ganho MAE | Ganho RMSE | Ganho WAPE |
|---|---|---|---|
| X | 15.28% | 15.11% | 15.28% |
| Y | 14.38% | 13.53% | 14.38% |
| Z | 14.85% | 12.33% | 14.85% |

## ABC × XYZ

| ABC | XYZ | Modelo | N | D | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|---|---|
| A | X | ets_ana | 261527 | 348995.649000 | 0.431288 | 0.708244 | 32.32% | -0.038176 | -2.86% |
| A | X | seasonal_naive | 261527 | 348995.649000 | 0.506820 | 0.833022 | 37.98% | -0.048438 | -3.63% |
| A | Y | ets_ana | 305907 | 374825.963000 | 0.427268 | 0.710419 | 34.87% | -0.003652 | -0.30% |
| A | Y | seasonal_naive | 305907 | 374825.963000 | 0.494132 | 0.815472 | 40.33% | -0.030959 | -2.53% |
| A | Z | ets_ana | 371840 | 505423.745000 | 0.473562 | 0.840800 | 34.84% | -0.047518 | -3.50% |
| A | Z | seasonal_naive | 371840 | 505423.745000 | 0.555165 | 0.948909 | 40.84% | -0.054676 | -4.02% |
| B | X | ets_ana | 81172 | 55308.538000 | 0.242212 | 0.360211 | 35.55% | -0.008032 | -1.18% |
| B | X | seasonal_naive | 81172 | 55308.538000 | 0.289707 | 0.426294 | 42.52% | -0.013628 | -2.00% |
| B | Y | ets_ana | 99057 | 61954.433000 | 0.246855 | 0.368449 | 39.47% | -0.011255 | -1.80% |
| B | Y | seasonal_naive | 99057 | 61954.433000 | 0.298614 | 0.450150 | 47.74% | -0.019712 | -3.15% |
| B | Z | ets_ana | 155820 | 98131.615000 | 0.323156 | 0.515315 | 51.31% | -0.009936 | -1.58% |
| B | Z | seasonal_naive | 155820 | 98131.615000 | 0.378794 | 0.614518 | 60.15% | -0.017813 | -2.83% |
| C | X | ets_ana | 28504 | 16996.834000 | 0.225111 | 0.327785 | 37.75% | -0.006817 | -1.14% |
| C | X | seasonal_naive | 28504 | 16996.834000 | 0.275631 | 0.404835 | 46.22% | -0.008639 | -1.45% |
| C | Y | ets_ana | 37198 | 21467.567000 | 0.240816 | 0.348008 | 41.73% | -0.007544 | -1.31% |
| C | Y | seasonal_naive | 37198 | 21467.567000 | 0.293822 | 0.434299 | 50.91% | -0.011347 | -1.97% |
| C | Z | ets_ana | 58975 | 34925.323000 | 0.295983 | 0.440351 | 49.98% | -0.006727 | -1.14% |
| C | Z | seasonal_naive | 58975 | 34925.323000 | 0.355706 | 0.538318 | 60.06% | -0.011184 | -1.89% |

| ABC | XYZ | Ganho MAE | Ganho RMSE | Ganho WAPE |
|---|---|---|---|---|
| A | X | 14.90% | 14.98% | 14.90% |
| A | Y | 13.53% | 12.88% | 13.53% |
| A | Z | 14.70% | 11.39% | 14.70% |
| B | X | 16.39% | 15.50% | 16.39% |
| B | Y | 17.33% | 18.15% | 17.33% |
| B | Z | 14.69% | 16.14% | 14.69% |
| C | X | 18.33% | 19.03% | 18.33% |
| C | Y | 18.04% | 19.87% | 18.04% |
| C | Z | 16.79% | 18.20% | 16.79% |

## Exposição à ruptura

| Exposição | Modelo | N | D | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|---|
| HIGH | ets_ana | 369131 | 604162.532000 | 0.517346 | 0.946077 | 31.61% | -0.066746 | -4.08% |
| HIGH | seasonal_naive | 369131 | 604162.532000 | 0.593231 | 1.058777 | 36.25% | -0.078880 | -4.82% |
| LOW | ets_ana | 363300 | 280700.653000 | 0.340762 | 0.517150 | 44.10% | 0.002504 | 0.32% |
| LOW | seasonal_naive | 363300 | 280700.653000 | 0.412469 | 0.637767 | 53.38% | -0.009037 | -1.17% |
| MEDIUM | ets_ana | 667569 | 633166.482000 | 0.347706 | 0.554487 | 36.66% | -0.013825 | -1.46% |
| MEDIUM | seasonal_naive | 667569 | 633166.482000 | 0.409234 | 0.648325 | 43.15% | -0.025812 | -2.72% |

| Exposição | Ganho MAE | Ganho RMSE | Ganho WAPE |
|---|---|---|---|
| HIGH | 12.79% | 10.64% | 12.79% |
| LOW | 17.38% | 18.91% | 17.38% |
| MEDIUM | 15.03% | 14.47% | 15.03% |

## Flag de possível censura

| Flag | Modelo | N | D | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|---|
| False | ets_ana | 1306823 | 1405505.803000 | 0.381651 | 0.657795 | 35.49% | -0.018611 | -1.73% |
| False | seasonal_naive | 1306823 | 1405505.803000 | 0.448465 | 0.759113 | 41.70% | -0.031177 | -2.90% |
| True | ets_ana | 93177 | 112523.864000 | 0.516598 | 0.850187 | 42.78% | -0.092689 | -7.68% |
| True | seasonal_naive | 93177 | 112523.864000 | 0.600554 | 0.977910 | 49.73% | -0.095392 | -7.90% |

| Flag | Ganho MAE | Ganho RMSE | Ganho WAPE |
|---|---|---|---|
| False | 14.90% | 13.35% | 14.90% |
| True | 13.98% | 13.06% | 13.98% |

Vitórias por fold: {"mae": {"ets": 4}, "rmse": {"ets": 4}, "wape": {"ets": 4}}. Todos os segmentos predefinidos são exibidos, incluindo A/B, AX/AY/AZ, BX/BY/BZ, HIGH e flag=True, independentemente do sinal do resultado.

## Estabilidade entre folds

| Modelo | Média WAPE | Desvio WAPE | Mínimo WAPE | Máximo WAPE | CV WAPE | Desvio bias % |
|---|---|---|---|---|---|---|
| ets_ana | 36.02% | 1.72% | 34.52% | 38.41% | 4.79% | 5.91% |
| seasonal_naive | 42.33% | 1.39% | 41.08% | 43.88% | 3.27% | 5.88% |

Desvio amostral, ddof=1, sobre quatro folds. Não é intervalo de confiança; média por fold não substitui WAPE global. O Parquet de estabilidade também contém os segmentos prospectivos e as cinco métricas.

## Bias por série

Os 28 dias são agregados por série antes dos quantis; séries têm peso igual. Bias global e por ABC/XYZ/exposição/flag constam nas tabelas anteriores. Nenhuma correção posterior de bias foi aplicada.

| Modelo | Séries bias<0 | Proporção | Bias p25 | Bias mediano | Bias p75 | Bias % p05 | Bias % mediano | Bias % p95 |
|---|---|---|---|---|---|---|---|---|
| seasonal_naive | 30698 | 61.40% | -0.076429 | -0.019643 | 0.025714 | -20.58% | -2.75% | 18.00% |
| ets_ana | 27663 | 55.33% | -0.093001 | -0.013751 | 0.054383 | -23.86% | -1.87% | 29.43% |

## Win rate pareado por série

Global agrega os quatro folds por série. ABC/XYZ agregam cada série apenas nos folds em que pertencia à classe prospectiva correspondente: uma série pode aparecer em várias classes; as contagens por classe não são aditivas. Não se atribui retrospectivamente o rótulo do último fold ou do train completo. Empate numérico: atol=1e-12, rtol=1e-10. Win rate e materialidade não constituem critérios isolados de aprovação.

| Nível | Classe | Métrica | Casos | Válidos | Indefinidos | Mín. folds | Máx. folds | ETS vence | SN vence | Empata | Taxa ETS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| global | ALL | mae | 50000 | 50000 | 0 | 4 | 4 | 44203 | 5797 | 0 | 88.41% |
| global | ALL | wape | 50000 | 50000 | 0 | 4 | 4 | 44203 | 5797 | 0 | 88.41% |
| abc | A | mae | 33841 | 33841 | 0 | 1 | 4 | 29872 | 3969 | 0 | 88.27% |
| abc | A | wape | 33841 | 33841 | 0 | 1 | 4 | 29872 | 3969 | 0 | 88.27% |
| abc | B | mae | 12556 | 12556 | 0 | 1 | 4 | 10930 | 1626 | 0 | 87.05% |
| abc | B | wape | 12556 | 12556 | 0 | 1 | 4 | 10930 | 1626 | 0 | 87.05% |
| abc | C | mae | 4629 | 4629 | 0 | 1 | 4 | 4106 | 523 | 0 | 88.70% |
| abc | C | wape | 4629 | 4629 | 0 | 1 | 4 | 4106 | 523 | 0 | 88.70% |
| xyz | X | mae | 19805 | 19805 | 0 | 1 | 4 | 16369 | 3436 | 0 | 82.65% |
| xyz | X | wape | 19805 | 19803 | 2 | 1 | 4 | 16369 | 3434 | 0 | 82.66% |
| xyz | Y | mae | 27308 | 27308 | 0 | 1 | 4 | 22177 | 5131 | 0 | 81.21% |
| xyz | Y | wape | 27308 | 27289 | 19 | 1 | 4 | 22163 | 5126 | 0 | 81.22% |
| xyz | Z | mae | 27787 | 27787 | 0 | 1 | 4 | 23409 | 4378 | 0 | 84.24% |
| xyz | Z | wape | 27787 | 27783 | 4 | 1 | 4 | 23406 | 4377 | 0 | 84.25% |

## Distribuição da melhoria e materialidade

Cada série recebe o mesmo peso e agrega os quatro folds. Percentuais a seguir são descritivos; não configuram automaticamente uma política. MAE e WAPE têm a mesma melhoria por série quando D>0.

| Métrica | Séries válidas | Referência indefinida | p25 | Mediana | p75 | >0 | ≥1% | ≥5% | ≥10% | ≤−1% | ≤−5% | ≤−10% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mae | 50000 | 0 | 7.90% | 16.53% | 24.03% | 88.41% | 87.18% | 81.05% | 69.80% | 10.53% | 7.09% | 4.26% |
| rmse | 50000 | 0 | 9.51% | 17.21% | 23.84% | 91.44% | 90.31% | 84.62% | 73.70% | 7.55% | 4.57% | 2.56% |
| wape | 50000 | 0 | 7.90% | 16.53% | 24.03% | 88.41% | 87.18% | 81.05% | 69.80% | 10.53% | 7.09% | 4.26% |

## Potencial híbrido sem consultar o próprio erro futuro

Regra definida antes da leitura dos resultados populacionais: exigir pelo menos dois folds anteriores concluídos no segmento ABC×XYZ, todos com melhoria de WAPE, nenhum com perda de RMSE e magnitude do bias consolidado anterior não maior que a de SN. Caso contrário, escolher SN. Os dois primeiros folds usam SN; a classe do fold corrente vem do snapshot conhecido na origem. Nenhuma escolha por série ou ajuste da regra a posteriori. Isso é análise de potencial, não política operacional final.

| Nível | Fold | N | D | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|---|
| fold | 1.000000 | 350000 | 363013.688000 | 0.426069 | 0.729601 | 41.08% | 0.017375 | 1.68% |
| fold | 2.000000 | 350000 | 366080.901000 | 0.458965 | 0.785785 | 43.88% | -0.008763 | -0.84% |
| fold | 3.000000 | 350000 | 370208.823000 | 0.444995 | 0.739622 | 42.07% | -0.011087 | -1.05% |
| fold | 4.000000 | 350000 | 418726.255000 | 0.464930 | 0.782436 | 38.86% | -0.134649 | -11.25% |
| global | indefinido | 1400000 | 1518029.667000 | 0.448740 | 0.759773 | 41.38% | -0.034281 | -3.16% |

| Fold | ABC | XYZ | Folds anteriores | Escolha analítica | Motivo |
|---|---|---|---|---|---|
| 1 | A | X | 0 | seasonal_naive | insufficient_completed_folds |
| 2 | A | X | 1 | seasonal_naive | insufficient_completed_folds |
| 3 | A | X | 2 | seasonal_naive | past_absolute_bias_worse |
| 4 | A | X | 3 | seasonal_naive | past_absolute_bias_worse |
| 1 | A | Y | 0 | seasonal_naive | insufficient_completed_folds |
| 2 | A | Y | 1 | seasonal_naive | insufficient_completed_folds |
| 3 | A | Y | 2 | seasonal_naive | past_absolute_bias_worse |
| 4 | A | Y | 3 | seasonal_naive | past_absolute_bias_worse |
| 1 | A | Z | 0 | seasonal_naive | insufficient_completed_folds |
| 2 | A | Z | 1 | seasonal_naive | insufficient_completed_folds |
| 3 | A | Z | 2 | seasonal_naive | past_absolute_bias_worse |
| 4 | A | Z | 3 | ets_ana | past_error_and_bias_qualify |
| 1 | B | X | 0 | seasonal_naive | insufficient_completed_folds |
| 2 | B | X | 1 | seasonal_naive | insufficient_completed_folds |
| 3 | B | X | 2 | seasonal_naive | past_absolute_bias_worse |
| 4 | B | X | 3 | seasonal_naive | past_absolute_bias_worse |
| 1 | B | Y | 0 | seasonal_naive | insufficient_completed_folds |
| 2 | B | Y | 1 | seasonal_naive | insufficient_completed_folds |
| 3 | B | Y | 2 | seasonal_naive | past_absolute_bias_worse |
| 4 | B | Y | 3 | seasonal_naive | past_absolute_bias_worse |
| 1 | B | Z | 0 | seasonal_naive | insufficient_completed_folds |
| 2 | B | Z | 1 | seasonal_naive | insufficient_completed_folds |
| 3 | B | Z | 2 | ets_ana | past_error_and_bias_qualify |
| 4 | B | Z | 3 | ets_ana | past_error_and_bias_qualify |
| 1 | C | X | 0 | seasonal_naive | insufficient_completed_folds |
| 2 | C | X | 1 | seasonal_naive | insufficient_completed_folds |
| 3 | C | X | 2 | ets_ana | past_error_and_bias_qualify |
| 4 | C | X | 3 | ets_ana | past_error_and_bias_qualify |
| 1 | C | Y | 0 | seasonal_naive | insufficient_completed_folds |
| 2 | C | Y | 1 | seasonal_naive | insufficient_completed_folds |
| 3 | C | Y | 2 | ets_ana | past_error_and_bias_qualify |
| 4 | C | Y | 3 | ets_ana | past_error_and_bias_qualify |
| 1 | C | Z | 0 | seasonal_naive | insufficient_completed_folds |
| 2 | C | Z | 1 | seasonal_naive | insufficient_completed_folds |
| 3 | C | Z | 2 | seasonal_naive | past_absolute_bias_worse |
| 4 | C | Z | 3 | seasonal_naive | past_absolute_bias_worse |

## Exemplos e baixa escala

| Regra | Fold | Loja | Produto | ABC | XYZ | D | WAPE SN | WAPE ETS | Ganho WAPE | Bias SN | Bias ETS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ETS_GAIN_AX | 4 | 157 | 74 | A | X | 2.800000 | 73.21% | 17.55% | 76.02% | 0.035714 | 0.053069 |
| ETS_LOSS_AX | 4 | 691 | 599 | A | X | 2.400000 | 4.17% | 34.47% | -727.29% | -0.014286 | 0.118184 |
| ETS_GAIN_AZ | 4 | 34 | 783 | A | Z | 10.800000 | 52.78% | 9.99% | 81.07% | 0.442857 | 0.126993 |
| ETS_REDUCES_UNDER | 4 | 417 | 1 | A | X | 62.500000 | 54.08% | 23.47% | 56.59% | -4.828571 | -0.674920 |
| ETS_INCREASES_UNDER | 4 | 639 | 589 | A | Y | 157.200000 | 19.15% | 8.14% | 57.51% | 1.385714 | -1.533935 |
| SEASONAL_NAIVE_SUPERIOR | 4 | 724 | 188 | B | Z | 1.700000 | 11.76% | 132.41% | -1025.46% | 0.000000 | -0.051464 |

Regras no último fold: maior ganho/piora WAPE em AX, maior ganho em AZ, maior redução de subprevisão mantendo bias não positivo, maior aumento da subprevisão e maior piora WAPE geral. Desempate por IDs. Fallback só é exemplificado se existir, na origem mais recente com ocorrência. Extremos descritivos, não representativos.

| Nível | Pares | D=0 | Menor D positivo | MAE SN zero | Ganho WAPE indefinido |
|---|---|---|---|---|---|
| series | 50000 | 0 | 1.100000 | 0 | 0 |
| series_fold | 200000 | 263 | 0.100000 | 16 | 264 |

Pequenos denominadores amplificam WAPE e sua variação. Os nulos permanecem visíveis; nenhum caso é excluído de MAE/RMSE/bias.

## Benchmark preservado e custo real

Amostra inicial: 135 séries, cinco em cada ABC×XYZ×tercil de escala conhecido no primeiro corte, selecionadas por hash de semente+IDs; quatro folds e 540 ajustes por configuração. A/N/A era o candidato principal antes dos erros. A/A/A foi apenas medido no benchmark anterior, sem nova execução. Projeção ponderada pela população dos estratos: 29,99 minutos de ajustes A/N/A; 1,25 × ajuste projetado + 92,88 s de overhead estimado = **39,03 minutos**. A margem de 25% não é intervalo estatístico. Benchmark: 21,03 s, pico 528,20 MiB; zero fallback em ambas as amostras.

| Configuração no benchmark | Ajustes | Média s/ajuste | p95 s/ajuste | Ajustes projetados s | Total projetado s | Fallback | Falhas | Clipping |
|---|---|---|---|---|---|---|---|---|
| ets_aaa | 540 | 0.012366 | 0.016015 | 2542.559545 | 3271.084273 | 0 | 0 | 6 |
| ets_ana | 540 | 0.008857 | 0.012808 | 1799.310610 | 2342.023104 | 0 | 0 | 2 |

Amostra SHA-256: `148a25d49d712dd30158bbc549acb7792d29d6b31a10e50747b662cb8658a0f9`. Benchmark JSON SHA-256: `5c87bea2abf3a91b80eb0c6f02c9ba027fe030fd6b8be8d1b68bf81662bc60bb`. Não confundir seus resultados de custo com as métricas populacionais desta entrega.

População: **28.766 min**; ajustes: 27.677 min; overhead populacional: 65.353 s. Comparação: 18.831 s. **População + comparação: 29.080 min**, com 84.184 s de overhead total. Esses tempos não incluem desenvolvimento, testes ou renderização posterior do notebook.

Início UTC: 2026-10-09T02:35:31.027751+00:00; fim populacional UTC: 2026-10-09T03:04:16.983280+00:00. Pico do processo de ajustes: 351.92 MiB; pico do processo de comparação: 965.96 MiB. Parquet populacionais e auxiliares: 98,818,416 bytes. Picos são por processo, não soma de processos concorrentes nem memória física total da máquina.

A primeira tentativa de ler todos os históricos juntos excedeu o limite de memória DuckDB antes de qualquer ajuste. A correção necessária foi carregar 2.500 séries por lote, usando as mesmas chaves prospectivas e o mesmo filtro temporal. Modelo, parâmetros e fórmulas não mudaram. A tentativa sem ajustes está registrada em `execution_prebatch_attempt.json`. O tempo real difere da projeção porque há margem conservadora e porque overhead e custo por ajuste foram medidos em carga e organização de I/O diferentes; não foi alterado o modelo para atingir um limite.

## Artefatos e reprodução

| Artefato | Caminho relativo | Linhas | SHA-256 |
|---|---|---|---|
| forecasts | data/processed/mart_forecast_statistical.parquet | 1400000 | e37cbec4f5b04c1da503dd459f3fbb9f41eeeed4bfdbfab762d3177e5d96631f |
| comparison | data/processed/mart_model_comparison.parquet | 376031 | bea6240ece47809b9a05582bda8c39ea16691f8533dabd44bde20c0201e752d1 |
| win_rates | data/outputs/statistical_forecasting/win_rates.parquet | 14 | 75924251fd4175e7759b770ab2f878e510da7cf2c546ff82d7a7b83b8344d966 |
| materiality | data/outputs/statistical_forecasting/materiality.parquet | 3 | 213aa74fcbaac9d5943dbe8e9087edcce0e43b830089d31aa67a7db112b41723 |
| fold_stability | data/outputs/statistical_forecasting/fold_stability.parquet | 42 | a9c5ff36443754c52404c0a625daf852e5f25c91314e1443c24b1c22df5741da |
| fit_diagnostics | data/outputs/statistical_forecasting/fit_diagnostics.parquet | 25 | 3a0659862632d7349ef14ac6090c2060d64420e2937bf04953a110ab3253bcde |
| fallback_reasons | data/outputs/statistical_forecasting/fallback_reasons.parquet | 0 | 23b1a014a99c58bc69944ace9ba84cb5654fa4fd5269717e44804e2a4c04aa53 |
| hybrid_choices | data/outputs/statistical_forecasting/hybrid_choices.parquet | 36 | 1c7c7ae872f7caebee0edf42beb0175872038ab4f75c8c9afd4855a834a8ae51 |
| hybrid_metrics | data/outputs/statistical_forecasting/hybrid_metrics.parquet | 5 | c61b29c7012f7978f5240c82ae9a4fbc6f78075b47bb80d3f18aa391a08c8edd |
| example_selection | data/outputs/statistical_forecasting/example_selection.parquet | 6 | d15920d9489574e66173fe0e69f58dc30788495a79ee8915af3a8316c4fd1a97 |
| example_forecasts | data/outputs/statistical_forecasting/example_forecasts.parquet | 84 | d7820e04d3fb0495aec22758e4b244e43d2ce78b39b98e7af5c9422199fd89d0 |
| example_actuals | data/outputs/statistical_forecasting/example_actuals.parquet | 126 | 1c6952b9a62c3525164065bbc966c5dc0b211ab948b98a0343f54d0f3da77dd3 |

Além dos Parquet: summary.json, execution.json, progress.json, population_performance.json e comparison_performance.json. O notebook `notebooks/04_statistical_forecasting.ipynb` consome somente outputs e contém dez figuras; PNGs e telemetria do notebook permanecem ignorados em data/outputs. Nenhum modelo treinado é serializado.

```powershell
.\.venv\Scripts\python.exe scripts/run_statistical_forecast.py --compare-only
.\.venv\Scripts\python.exe scripts/render_statistical_forecasting.py
.\.venv\Scripts\python.exe -m pip check
git diff --check
git status
```

O comando sem `--compare-only` executa população apenas quando não existe mart final ou parcial. Nesta entrega não foi repetida a população. Reprodução valida contratos, hashes da fonte e Fase 4, métricas de SN idênticas às anteriores e seis ajustes determinísticos do último fold. Telemetria não exige igualdade de bytes; dependências e runtime constam em execution.json.

## Limites da evidência

Quatro folds, 28 dias avaliados e 62–83 dias de histórico não demonstram generalização sazonal ou em novas séries. As séries compartilham produtos/lojas; não são 50.000 experimentos independentes. Não há teste de significância nem evidência causal de disponibilidade. Classes relativas mudam entre origens. Vantagem em erro não basta para justificar custo ou piora de bias; a classificação final precisa considerar todos esses critérios. Não houve abertura do holdout, correção de censura, reposição ou Power BI.

## Interpretação da execução aprovada

**A) ETS claramente superior no backtesting observado.** Não é uma afirmação de dominância em toda série ou de desempenho garantido no holdout. A conclusão conjunta se apoia em redução global de MAE/WAPE de 14,82% e de RMSE de 13,32%, vitória nas três métricas nos quatro folds, ganho em todos os segmentos predefinidos e bias global mais próximo de zero. O resultado não depende de uma janela isolada: o ganho WAPE por fold varia de 12,42% a 18,71%. Nas 36 combinações ABC×XYZ×fold, ETS vence em WAPE e RMSE; a menor melhoria WAPE é 10,81%.

A e B melhoram WAPE em 14,39% e 15,74%. Os recortes prioritários AX/AY/AZ melhoram 14,90%/13,53%/14,70%; BX/BY/BZ, 16,39%/17,33%/14,69%. HIGH melhora 12,79% e flag=True 13,98%, mas mantém subprevisão importante. C também melhora: 17,44%; não há evidência para restringir a vantagem de erro apenas a alguns segmentos nesta população.

**O ganho global não veio à custa de maior subprevisão global:** bias_pct passa de −3,27% para −2,17%; a proporção de séries com bias negativo cai de 61,40% para 55,33%. Contudo, isso não significa melhor calibração em todas as séries. O p05 do bias_pct fica mais negativo (−20,58% → −23,86%) e o p95 mais positivo (18,00% → 29,43%): a distribuição se alarga. Nos folds 1 e 3, ETS supera o nível observado em agregado; a magnitude do bias piora nos folds 1, 2 e 3. No fold 2 também há maior subprevisão (−0,84% → −1,04%). No fold 4, ela melhora, mas permanece elevada (−11,59% → −10,45%). Em HIGH, bias_pct passa de −4,82% para −4,08%; na flag=True, de −7,90% para −7,68%. Esses sinais exigem atenção, sem inferir ruptura causada pelo forecast.

Nenhum dos grupos consolidados predefinidos piora a magnitude do bias, mas o recorte por fold revela pioras relevantes: AZ no fold 2 passa de −1,98% para −4,50%; HIGH no fold 2, de −2,65% para −4,28%; flag=True no fold 2, de −8,75% para −10,77%. AY no fold 3 passa de −0,20% para +3,67%, uma sobreprevisão maior em magnitude. São ressalvas explícitas à melhora média, mantendo todos os grupos e origens no summary.json e nas métricas segmento×fold.

ETS tem menor WAPE em cada fold, mas **maior dispersão entre folds**: desvio de 1,72 ponto percentual contra 1,39 de SN; CV de 4,79% contra 3,27%. Menor nível de erro não equivale a menor volatilidade temporal. Os quatro folds não permitem afirmar significância ou estabilidade em outras estações.

O ganho é amplamente distribuído: ETS vence MAE/WAPE em 44.203 séries (88,406%), SN em 5.797, sem empates. A melhoria mediana é 16,53%; 69,802% das séries melhoram pelo menos 10%. Ainda assim, 4,256% pioram pelo menos 10%; uma escolha uniforme não beneficia cada série. A classificação A reflete o conjunto da evidência, incluindo essas perdas e o custo local de 29,08 minutos para população e comparação.

A regra híbrida conservadora usa ETS em BZ/CX/CY no fold 3 e AZ/BZ/CX/CY no fold 4. Gera WAPE global de 41,38%, ganho de 2,15% sobre SN, e RMSE de 0,759773, ganho de 2,04%. É inferior ao ETS uniforme neste backtest. A exigência de bias histórico bloqueia vários grupos apesar dos ganhos de erro; não foi relaxada após observar os resultados. Não há evidência de que essa regra seja necessária ou superior ao candidato único, nem base para selecionar séries pelo erro futuro.

**Próxima decisão recomendada:** revisar A/N/A como candidato principal, preservando Seasonal Naive como referência e fallback. Adoção operacional, validação no holdout e eventual reprodução integral adicional exigem decisão posterior; não foram executadas. Nenhum modelo adicional, política de reposição ou commit foi criado. Com a validação final aprovada, a recomendação técnica é **Fase 5 aprovada para revisão e encerramento desta etapa**, sem bloqueio metodológico remanescente e sem autorizar abertura do holdout.

## Validação final da continuação

Pytest: **98 aprovados, 2 desmarcados**, em 123.69 s. Os 92 testes anteriores foram preservados; oito foram adicionados. Os dois desmarcados abrem o raw eval para contratos de ingestão/staging e não foram executados nesta rodada. As demais validações, incluindo reprodução integral das Fases 2/3/4 sem eval e os novos contratos populacionais, passaram. Não se repete o fitting populacional da Fase 5.

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=.tmp/pytest-phase5-population-final-fixed --deselect=tests/test_raw_quality.py::test_raw_files_manifest_hashes_and_schema --deselect=tests/test_raw_quality.py::test_staging_reproducible_from_full_raw
```

A primeira rodada teve 97 aprovações e uma diferença de reprodução numérica em seis ajustes (máximo absoluto de 0,00012431). Com a mesma configuração de uma thread do runner, os seis ajustes foram reproduzidos exatamente. O teste agora aplica threadpoolctl no contexto de ajuste; a dependência já fazia parte da stack. Nenhuma tolerância foi relaxada, modelo alterado ou previsão substituída.

`pip check`: sem dependências quebradas. `git diff --check`: sem erros. Stage vazio, HEAD `4dfaa9d`, sem commit. Dados, outputs, .venv e .env permanecem ignorados; somente os .gitkeep preexistentes estão rastreados nos diretórios de dados.

## Apresentação executada

Notebook com dez figuras, doze células de código executadas e nenhum erro; inspeção visual concluída. Última renderização: 12.77 s; 929,551 bytes. Pico do kernel: 313.20 MiB. Uma tentativa no sandbox foi bloqueada por ACL do arquivo temporário do Jupyter (WinError 5). A execução fora do sandbox foi autorizada; a tentativa bloqueada e o kernel concluído foram encerrados. Não foi desabilitada a proteção de arquivos do Jupyter.
