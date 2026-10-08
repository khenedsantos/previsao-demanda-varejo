# Fase 4 — Forecasting baselines e backtesting temporal

Análise **prospectiva, exclusivamente dentro de train**, sobre `sale_amount`: venda observada normalizada. Não representa demanda latente, unidades físicas ou receita. Eval permanece congelado como holdout final; não participa da execução, seleção ou segmentação.

## Desenho temporal e baselines

Quatro folds com histórico crescente e sete dias de horizonte, sem sobreposição dos testes. Todos começam o histórico em 28/03/2024. O primeiro tem 62 dias e oito semanas completas, preservando histórico para a regra XYZ; os demais acrescentam uma semana. Quatro folds equilibram essa exigência e a avaliação em mais de uma janela dentro dos 90 dias.

| Fold | Início histórico | Fim histórico | Dias | Origem / início teste | Fim teste |
|---|---|---|---|---|---|
| 1 | 2024-03-28 | 2024-05-28 | 62 | 2024-05-29 | 2024-06-04 |
| 2 | 2024-03-28 | 2024-06-04 | 69 | 2024-06-05 | 2024-06-11 |
| 3 | 2024-03-28 | 2024-06-11 | 76 | 2024-06-12 | 2024-06-18 |
| 4 | 2024-03-28 | 2024-06-18 | 83 | 2024-06-19 | 2024-06-25 |

`forecast_origin` é o **primeiro dia previsto, antes de observar sua venda**. `cutoff_date = origin − 1 dia`. Naive repete o actual do cutoff nos sete dias. Seasonal Naive usa, para cada target_date, o actual exatamente de target_date − 7 dias. Nenhum deles se atualiza com actuals do próprio horizonte.

São **50,000 séries × 4 folds × 7 dias × 2 modelos = 2,800,000 previsões**. Cada modelo tem 1.400.000 previsões; a cobertura é completa, sem exclusão de zeros ou séries.

## Métricas, sinal e agregação

Para `e = forecast − actual`, N observações e D = soma(actual):

- MAE = soma(abs(e))/N; RMSE = sqrt(soma(e²)/N).
- WAPE = soma(abs(e))/D; bias = soma(e)/N; bias_pct = soma(e)/D.
- Bias é **assinado**, apesar de estar na escala absoluta da venda: positivo indica superprevisão, negativo subprevisão. Não é abs(bias).
- D=0 mantém WAPE e bias_pct nulos; MAE/RMSE/bias continuam definidos. MAPE não é calculado.
- Métricas consolidadas são calculadas das somas suficientes, nunca da média dos WAPEs/RMSEs das séries. MAE/RMSE dão peso a cada previsão; WAPE global pondera as escalas de venda.
- Melhoria relativa = (métrica Naive − métrica Seasonal Naive)/métrica Naive, para MAE/RMSE/WAPE. Referência zero torna a melhoria indefinida. Não se aplica essa divisão ao bias assinado.

## Resultado global e baseline de referência

| Modelo | Previsões | D = soma actual | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|
| naive | 1400000 | 1518029.667000 | 0.471573 | 0.819916 | 43.49% | -0.081365 | -7.50% |
| seasonal_naive | 1400000 | 1518029.667000 | 0.458587 | 0.775595 | 42.29% | -0.035451 | -3.27% |

| Métrica | Naive | Seasonal Naive | Melhoria relativa |
|---|---|---|---|
| mae | 0.471573 | 0.458587 | 2.75% |
| rmse | 0.819916 | 0.775595 | 5.41% |
| wape | 0.434908 | 0.422931 | 2.75% |

**Referência: Seasonal Naive**, pelo menor WAPE global consolidado. Também reduz MAE e RMSE e aproxima o bias de zero. Vence em WAPE nos quatro folds, mas sua dispersão global de WAPE é ligeiramente maior: não domina todos os critérios nem todos os grupos.

## Performance por ABC

| ABC | Modelo | Previsões | D = soma actual | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|---|
| A | naive | 939274 | 1229245.357000 | 0.531151 | 0.916582 | 40.59% | -0.104213 | -7.96% |
| A | seasonal_naive | 939274 | 1229245.357000 | 0.521827 | 0.875359 | 39.87% | -0.045215 | -3.45% |
| B | naive | 336049 | 215394.586000 | 0.360254 | 0.605725 | 56.21% | -0.028545 | -4.45% |
| B | seasonal_naive | 336049 | 215394.586000 | 0.333641 | 0.527947 | 52.05% | -0.017362 | -2.71% |
| C | naive | 124677 | 73389.724000 | 0.322783 | 0.480323 | 54.84% | -0.051606 | -8.77% |
| C | seasonal_naive | 124677 | 73389.724000 | 0.318935 | 0.480436 | 54.18% | -0.010651 | -1.81% |

| ABC | Métrica | Melhoria relativa SN |
|---|---|---|
| A | mae | 1.76% |
| A | rmse | 4.50% |
| A | wape | 1.76% |
| B | mae | 7.39% |
| B | rmse | 12.84% |
| B | wape | 7.39% |
| C | mae | 1.19% |
| C | rmse | -0.02% |
| C | wape | 1.19% |

## Performance por XYZ

| XYZ | Modelo | Previsões | D = soma actual | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|---|
| X | naive | 371203 | 421301.021000 | 0.457784 | 0.757639 | 40.33% | -0.107187 | -9.44% |
| X | seasonal_naive | 371203 | 421301.021000 | 0.441591 | 0.735678 | 38.91% | -0.037770 | -3.33% |
| Y | naive | 442162 | 458247.963000 | 0.444188 | 0.741003 | 42.86% | -0.075610 | -7.30% |
| Y | seasonal_naive | 442162 | 458247.963000 | 0.433479 | 0.722036 | 41.83% | -0.026789 | -2.58% |
| Z | naive | 586635 | 638480.683000 | 0.500940 | 0.909544 | 46.03% | -0.069364 | -6.37% |
| Z | seasonal_naive | 586635 | 638480.683000 | 0.488266 | 0.836766 | 44.86% | -0.040512 | -3.72% |

| XYZ | Métrica | Melhoria relativa SN |
|---|---|---|
| X | mae | 3.54% |
| X | rmse | 2.90% |
| X | wape | 3.54% |
| Y | mae | 2.41% |
| Y | rmse | 2.56% |
| Y | wape | 2.41% |
| Z | mae | 2.53% |
| Z | rmse | 8.00% |
| Z | wape | 2.53% |

## Performance por ABC × XYZ

| ABC | XYZ | Modelo | Previsões | D = soma actual | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|---|---|
| A | X | naive | 261527 | 348995.649000 | 0.521289 | 0.849464 | 39.06% | -0.126259 | -9.46% |
| A | X | seasonal_naive | 261527 | 348995.649000 | 0.506820 | 0.833022 | 37.98% | -0.048438 | -3.63% |
| A | Y | naive | 305907 | 374825.963000 | 0.503685 | 0.832483 | 41.11% | -0.088418 | -7.22% |
| A | Y | seasonal_naive | 305907 | 374825.963000 | 0.494132 | 0.815472 | 40.33% | -0.030959 | -2.53% |
| A | Z | naive | 371840 | 505423.745000 | 0.560682 | 1.022009 | 41.25% | -0.101703 | -7.48% |
| A | Z | seasonal_naive | 371840 | 505423.745000 | 0.555165 | 0.948909 | 40.84% | -0.054676 | -4.02% |
| B | X | naive | 81172 | 55308.538000 | 0.313585 | 0.489933 | 46.02% | -0.061768 | -9.07% |
| B | X | seasonal_naive | 81172 | 55308.538000 | 0.289707 | 0.426294 | 42.52% | -0.013628 | -2.00% |
| B | Y | naive | 99057 | 61954.433000 | 0.314390 | 0.486335 | 50.27% | -0.045124 | -7.21% |
| B | Y | seasonal_naive | 99057 | 61954.433000 | 0.298614 | 0.450150 | 47.74% | -0.019712 | -3.15% |
| B | Z | naive | 155820 | 98131.615000 | 0.413723 | 0.718247 | 65.69% | -0.000698 | -0.11% |
| B | Z | seasonal_naive | 155820 | 98131.615000 | 0.378794 | 0.614518 | 60.15% | -0.017813 | -2.83% |
| C | X | naive | 28504 | 16996.834000 | 0.285755 | 0.413671 | 47.92% | -0.061542 | -10.32% |
| C | X | seasonal_naive | 28504 | 16996.834000 | 0.275631 | 0.404835 | 46.22% | -0.008639 | -1.45% |
| C | Y | naive | 37198 | 21467.567000 | 0.300546 | 0.444613 | 52.08% | -0.051463 | -8.92% |
| C | Y | seasonal_naive | 37198 | 21467.567000 | 0.293822 | 0.434299 | 50.91% | -0.011347 | -1.97% |
| C | Z | naive | 58975 | 34925.323000 | 0.354705 | 0.529474 | 59.90% | -0.046893 | -7.92% |
| C | Z | seasonal_naive | 58975 | 34925.323000 | 0.355706 | 0.538318 | 60.06% | -0.011184 | -1.89% |

| ABC | XYZ | Métrica | Melhoria relativa SN |
|---|---|---|---|
| A | X | mae | 2.78% |
| A | X | rmse | 1.94% |
| A | X | wape | 2.78% |
| A | Y | mae | 1.90% |
| A | Y | rmse | 2.04% |
| A | Y | wape | 1.90% |
| A | Z | mae | 0.98% |
| A | Z | rmse | 7.15% |
| A | Z | wape | 0.98% |
| B | X | mae | 7.61% |
| B | X | rmse | 12.99% |
| B | X | wape | 7.61% |
| B | Y | mae | 5.02% |
| B | Y | rmse | 7.44% |
| B | Y | wape | 5.02% |
| B | Z | mae | 8.44% |
| B | Z | rmse | 14.44% |
| B | Z | wape | 8.44% |
| C | X | mae | 3.54% |
| C | X | rmse | 2.14% |
| C | X | wape | 3.54% |
| C | Y | mae | 2.24% |
| C | Y | rmse | 2.32% |
| C | Y | wape | 2.24% |
| C | Z | mae | -0.28% |
| C | Z | rmse | -1.67% |
| C | Z | wape | -0.28% |

## Performance por Exposição à ruptura

| Exposição | Modelo | Previsões | D = soma actual | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|---|
| HIGH | naive | 369131 | 604162.532000 | 0.606058 | 1.130168 | 37.03% | -0.178812 | -10.93% |
| HIGH | seasonal_naive | 369131 | 604162.532000 | 0.593231 | 1.058777 | 36.25% | -0.078880 | -4.82% |
| LOW | naive | 363300 | 280700.653000 | 0.420853 | 0.659613 | 54.47% | -0.026455 | -3.42% |
| LOW | seasonal_naive | 363300 | 280700.653000 | 0.412469 | 0.637767 | 53.38% | -0.009037 | -1.17% |
| MEDIUM | naive | 667569 | 633166.482000 | 0.424813 | 0.683221 | 44.79% | -0.057365 | -6.05% |
| MEDIUM | seasonal_naive | 667569 | 633166.482000 | 0.409234 | 0.648325 | 43.15% | -0.025812 | -2.72% |

| Exposição | Métrica | Melhoria relativa SN |
|---|---|---|
| HIGH | mae | 2.12% |
| HIGH | rmse | 6.32% |
| HIGH | wape | 2.12% |
| LOW | mae | 1.99% |
| LOW | rmse | 3.31% |
| LOW | wape | 1.99% |
| MEDIUM | mae | 3.67% |
| MEDIUM | rmse | 5.11% |
| MEDIUM | wape | 3.67% |

## Performance por Flag de possível censura

| Flag | Modelo | Previsões | D = soma actual | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|---|
| False | naive | 1306823 | 1405505.803000 | 0.462610 | 0.803931 | 43.01% | -0.077671 | -7.22% |
| False | seasonal_naive | 1306823 | 1405505.803000 | 0.448465 | 0.759113 | 41.70% | -0.031177 | -2.90% |
| True | naive | 93177 | 112523.864000 | 0.597288 | 1.017995 | 49.46% | -0.133173 | -11.03% |
| True | seasonal_naive | 93177 | 112523.864000 | 0.600554 | 0.977910 | 49.73% | -0.095392 | -7.90% |

| Flag | Métrica | Melhoria relativa SN |
|---|---|---|
| False | mae | 3.06% |
| False | rmse | 5.57% |
| False | wape | 3.06% |
| True | mae | -0.55% |
| True | rmse | 3.94% |
| True | wape | -0.55% |

### Interpretação dos segmentos

ABC usa a contribuição global do produto até cada corte, propagada às séries. A tem MAE maior, mas WAPE menor que B/C, evidenciando a diferença de escala. O ganho relativo de WAPE é maior em B (7,39%); B–Z chega a 8,44%. C–Z piora 0,28% em WAPE e C piora ligeiramente em RMSE.

X tem menor WAPE que Y e Z nos dois baselines; também tem MAE/RMSE menores que Z. Isso apoia parcialmente a hipótese preditiva, sem estabelecer uma ordem universal: Y tem MAE/RMSE menores que X e, no Seasonal Naive, Z tem **menor desvio e CV do WAPE entre folds** que X. As regras XYZ não foram ajustadas ao resultado. Os grupos são prospectivos e sua composição pode mudar entre folds.

HIGH tem maior MAE/RMSE e bias mais negativo, porém WAPE menor que LOW: vende mais em escala normalizada, e o denominador muda a comparação. A flag tem WAPE e subprevisão maiores que o grupo sem flag. Dentro da flag, Seasonal Naive piora MAE/WAPE em 0,55%, embora melhore RMSE e bias. Essas associações não demonstram que ruptura causou o erro, não estimam demanda perdida e não convertem bias negativo automaticamente em risco de ruptura.

## Bias por série e por segmento

A distribuição abaixo agrega os 28 dias previstos por série e modelo. Quantis são calculados sobre séries com mesmo peso. Não equivalem ao bias percentual global ponderado. As tabelas anteriores contêm bias e bias_pct por ABC, XYZ, exposição e flag.

| Modelo | Bias < 0 | Bias > 0 | Bias = 0 | Bias p05 | Bias mediana | Bias p95 | Bias % p05 | Bias % mediana | Bias % p95 |
|---|---|---|---|---|---|---|---|---|---|
| naive | 31689 | 18259 | 52 | -0.528929 | -0.056071 | 0.285714 | -45.98% | -7.44% | 35.46% |
| seasonal_naive | 30698 | 19100 | 202 | -0.285714 | -0.019643 | 0.135714 | -20.58% | -2.75% | 18.00% |

Naive subprevê em 63,38% das séries; Seasonal Naive em 61,40%. O bias percentual global cai em magnitude de −7,50% para −3,27%, mas a subprevisão continua, especialmente no quarto fold (−12,15% e −11,59%). Pode ser operacionalmente indesejável, sem identificar a causa ou uma política de compra.

## Folds e estabilidade

| Fold | Modelo | Previsões | D = soma actual | MAE | RMSE | WAPE | Bias | Bias % |
|---|---|---|---|---|---|---|---|---|
| 1.000000 | naive | 350000 | 363013.688000 | 0.440148 | 0.779372 | 42.44% | -0.054676 | -5.27% |
| 2.000000 | naive | 350000 | 366080.901000 | 0.470760 | 0.868720 | 45.01% | -0.089984 | -8.60% |
| 3.000000 | naive | 350000 | 370208.823000 | 0.468176 | 0.761293 | 44.26% | -0.035466 | -3.35% |
| 4.000000 | naive | 350000 | 418726.255000 | 0.507210 | 0.864514 | 42.40% | -0.145334 | -12.15% |
| 1.000000 | seasonal_naive | 350000 | 363013.688000 | 0.426069 | 0.729601 | 41.08% | 0.017375 | 1.68% |
| 2.000000 | seasonal_naive | 350000 | 366080.901000 | 0.458965 | 0.785785 | 43.88% | -0.008763 | -0.84% |
| 3.000000 | seasonal_naive | 350000 | 370208.823000 | 0.455944 | 0.755159 | 43.11% | -0.011794 | -1.12% |
| 4.000000 | seasonal_naive | 350000 | 418726.255000 | 0.493370 | 0.828341 | 41.24% | -0.138621 | -11.59% |

Desvio amostral (ddof=1) entre quatro folds; CV = desvio/média apenas para métricas de erro com média positiva. Bias mantém sinal e não recebe CV. Média dos WAPEs dos folds é apresentada separadamente do WAPE global consolidado.

| Modelo | mae média | Desvio | Mínimo | Máximo | CV |
|---|---|---|---|---|---|
| naive | 0.471573 | 0.027506 | 0.440148 | 0.507210 | 0.058329 |
| seasonal_naive | 0.458587 | 0.027534 | 0.426069 | 0.493370 | 0.060042 |

| Modelo | rmse média | Desvio | Mínimo | Máximo | CV |
|---|---|---|---|---|---|
| naive | 0.818475 | 0.056104 | 0.761293 | 0.868720 | 0.068547 |
| seasonal_naive | 0.774722 | 0.042490 | 0.729601 | 0.828341 | 0.054845 |

| Modelo | wape média | Desvio | Mínimo | Máximo | CV |
|---|---|---|---|---|---|
| naive | 0.435257 | 0.013167 | 0.423961 | 0.450081 | 0.030251 |
| seasonal_naive | 0.423262 | 0.013855 | 0.410795 | 0.438804 | 0.032733 |

| Modelo | bias média | Desvio | Mínimo | Máximo |
|---|---|---|---|---|
| naive | -0.081365 | 0.048254 | -0.145334 | -0.035466 |
| seasonal_naive | -0.035451 | 0.070016 | -0.138621 | 0.017375 |

| XYZ | Modelo | mae média | Desvio | Mínimo | Máximo | CV |
|---|---|---|---|---|---|---|
| X | naive | 0.457784 | 0.029838 | 0.421063 | 0.493858 | 0.065179 |
| Y | naive | 0.444195 | 0.028447 | 0.420294 | 0.485131 | 0.064041 |
| Z | naive | 0.500921 | 0.027461 | 0.467212 | 0.532235 | 0.054821 |
| X | seasonal_naive | 0.441616 | 0.032365 | 0.397991 | 0.474239 | 0.073288 |
| Y | seasonal_naive | 0.433476 | 0.029751 | 0.397824 | 0.469996 | 0.068633 |
| Z | seasonal_naive | 0.488243 | 0.024879 | 0.465158 | 0.523000 | 0.050957 |

| XYZ | Modelo | rmse média | Desvio | Mínimo | Máximo | CV |
|---|---|---|---|---|---|---|
| X | naive | 0.755404 | 0.068019 | 0.694393 | 0.850957 | 0.090043 |
| Y | naive | 0.738752 | 0.065835 | 0.678360 | 0.830471 | 0.089116 |
| Z | naive | 0.904506 | 0.110552 | 0.803874 | 1.060054 | 0.122223 |
| X | seasonal_naive | 0.733830 | 0.061363 | 0.657386 | 0.806451 | 0.083621 |
| Y | seasonal_naive | 0.720279 | 0.057364 | 0.657053 | 0.793166 | 0.079642 |
| Z | seasonal_naive | 0.836449 | 0.025745 | 0.811222 | 0.866954 | 0.030779 |

| XYZ | Modelo | wape média | Desvio | Mínimo | Máximo | CV |
|---|---|---|---|---|---|---|
| X | naive | 0.403434 | 0.014365 | 0.386940 | 0.419221 | 0.035606 |
| Y | naive | 0.428842 | 0.011169 | 0.416035 | 0.442024 | 0.026045 |
| Z | naive | 0.461008 | 0.019971 | 0.441254 | 0.488766 | 0.043320 |
| X | seasonal_naive | 0.389199 | 0.019828 | 0.365738 | 0.410602 | 0.050946 |
| Y | seasonal_naive | 0.418644 | 0.020342 | 0.393793 | 0.439531 | 0.048591 |
| Z | seasonal_naive | 0.449204 | 0.010591 | 0.433598 | 0.457127 | 0.023578 |

| XYZ | Modelo | bias média | Desvio | Mínimo | Máximo |
|---|---|---|---|---|---|
| X | naive | -0.107467 | 0.067818 | -0.201947 | -0.052246 |
| Y | naive | -0.075469 | 0.055825 | -0.154953 | -0.024247 |
| Z | naive | -0.069343 | 0.035536 | -0.102531 | -0.033072 |
| X | seasonal_naive | -0.038035 | 0.099345 | -0.186338 | 0.023999 |
| Y | seasonal_naive | -0.026757 | 0.073376 | -0.136241 | 0.017730 |
| Z | seasonal_naive | -0.040467 | 0.051297 | -0.110447 | 0.012928 |

A amplitude do WAPE global é 42,40–45,01% no Naive e 41,08–43,88% no Seasonal Naive. Os desvios são 1,317 e 1,386 pontos percentuais (CV 3,03% e 3,27%). O segundo é melhor em nível de erro, sem vantagem de estabilidade global. Quatro folds não sustentam inferência de significância.

## Denominadores, zeros e baixa escala

| Nível | Modelo | Casos | D=0 | Menor D positivo | p05 de D>0 | Casos D≤p05 | WAPE mediano baixo D | WAPE máximo baixo D |
|---|---|---|---|---|---|---|---|---|
| series | naive | 50000 | 0 | 1.100000 | 10.130000 | 2501 | 68.97% | 405.88% |
| series | seasonal_naive | 50000 | 0 | 1.100000 | 10.130000 | 2501 | 68.83% | 290.91% |
| series_fold | naive | 200000 | 263 | 0.100000 | 2.200000 | 10257 | 85.71% | 13200.00% |
| series_fold | seasonal_naive | 200000 | 263 | 0.100000 | 2.200000 | 10257 | 92.78% | 9100.00% |

Há 263 séries×fold com D=0 por modelo (526 linhas de métricas), mantendo WAPE/bias_pct indefinidos. Nenhuma série tem D=0 ao agregar os quatro folds. O p05 empírico dos denominadores positivos serve somente ao diagnóstico: não filtra a avaliação nem define um limite operacional. WAPE extremo com D=0,1 é matematicamente válido, mas pouco estável. Os denominadores por grupo estão nas tabelas e no mart; não se faz média de WAPE para contornar o problema.

## Exemplos selecionados por regra

Seleção no **último fold** para manter uma única origem e segmento por exemplo. Melhor/pior significa menor/maior WAPE válido; subprevisão usa menor bias assinado. HIGH escolhe maior WAPE; flag escolhe menor bias negativo; Naive supera SN escolhe maior WAPE(SN)−WAPE(Naive)>0. Empates por store_id e product_id. São extremos, não exemplos representativos, e sua seleção após medir erro é apenas descritiva, sem efeito em previsão ou escolha de classes.

| Regra | Loja | Produto | ABC | XYZ | D | WAPE SN | Bias SN |
|---|---|---|---|---|---|---|---|
| SN_BEST_AX | 587 | 589 | A | X | 106.200000 | 4.05% | 0.214286 |
| SN_WORST_AX | 592 | 4 | A | X | 1.400000 | 385.71% | 0.600000 |
| SN_MOST_UNDER_AZ | 550 | 267 | A | Z | 182.200000 | 29.42% | -7.657143 |
| SN_HIGH_EXPOSURE_HIGH_ERROR | 219 | 129 | A | Z | 0.100000 | 4400.00% | 0.600000 |
| SN_CENSOR_STRONG_UNDER | 74 | 300 | A | Z | 47.500000 | 93.05% | -6.257143 |
| NAIVE_BEATS_SEASONAL | 584 | 864 | B | Z | 0.100000 | 4350.00% | 0.592857 |

O pior AX tem D=1,4, o HIGH de maior WAPE e o caso em que Naive mais supera SN têm D=0,1. Essa dependência da escala deve acompanhar a leitura dos gráficos. O notebook mostra 14 dias de histórico e sete previstos, com ambos os modelos, actual e marcação de dias afetados por ruptura.

## Controle temporal, proveniência e contratos

Cada fold filtra train **antes** do perfil, ABC, XYZ, quantis de exposição e flag. O pipeline não lê os marts finais da Fase 2/3, staging ou eval. Actuals do horizonte são unidos somente depois da geração das previsões. `source_observation_date` permite auditar a fonte de cada previsão. Os snapshots registram cutoff/origem e os thresholds de cada fold ficam no JSON.

| Fold | Semanas completas | Forma indefinida | Sem ruptura | CV semanal p50 | CV semanal p75 | Ruptura p25 | Ruptura p75 |
|---|---|---|---|---|---|---|---|
| 1 | 8 | 7 | 2 | 0.234329 | 0.332822 | 0.338710 | 0.548387 |
| 2 | 9 | 4 | 1 | 0.238946 | 0.338380 | 0.333333 | 0.521739 |
| 3 | 10 | 4 | 0 | 0.246403 | 0.346097 | 0.342105 | 0.526316 |
| 4 | 11 | 4 | 0 | 0.256478 | 0.362309 | 0.337349 | 0.518072 |

Duas séries no fold 1 e uma no fold 2 não têm ruptura histórica: duração média nos dias afetados é legitimamente nula. A validação de suporte aceita esse caso somente se frequência, horas totais e maior sequência forem zero; não imputa duração nem altera regras de classificação da Fase 3.

O mart de previsões tem chave loja+produto+origem+target_date+modelo (fold_id adicional), horizon_step, cutoff, data da fonte, actual, forecast e error. O mart de métricas usa `level` para discriminar série×fold, série, fold, global, ABC, XYZ, exposição, flag e ABC×XYZ; inclui cinco níveis segmento×fold apenas para estabilidade. Dimensões não aplicáveis são nulas. Sempre filtrar level antes de somar. O nível série consolidado não recebe um segmento único: a classificação pode mudar. Contagens de séries/produtos distintos entre grupos/folds não são aditivas.

| Output | Caminho | Linhas |
|---|---|---|
| forecasts | data/processed/mart_forecast_baselines.parquet | 2800000 |
| metrics | data/processed/mart_forecast_metrics.parquet | 500210 |
| fold_segments | data/outputs/forecasting_baselines/fold_segments.parquet | 200000 |
| fold_product_abc | data/outputs/forecasting_baselines/fold_product_abc.parquet | 3460 |
| relative_improvement | data/outputs/forecasting_baselines/relative_improvement.parquet | 75 |
| fold_stability | data/outputs/forecasting_baselines/fold_stability.parquet | 42 |
| example_selection | data/outputs/forecasting_baselines/example_selection.parquet | 6 |
| example_forecasts | data/outputs/forecasting_baselines/example_forecasts.parquet | 84 |
| example_actuals | data/outputs/forecasting_baselines/example_actuals.parquet | 126 |

Fonte verificada: `data/raw/train.parquet`, revisão `08c1fab7f9257bc73679d415d65d644165d351d4`, SHA-256 `6706832db892bbae4969c19d87e07975d2543d2ba7d7d4756360654785de5a3d`. Hashes de nove Parquet e versões do runtime ficam em summary.json. A reprodução exige igualdade dos nove Parquet e do próprio resumo na mesma versão; performance.json contém telemetria variável e fica fora da comparação determinística.

## Reprodução e testes

```powershell
.\.venv\Scripts\python.exe scripts/run_baseline_backtest.py
.\.venv\Scripts\python.exe scripts/render_forecasting_baselines.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
git diff --check
git status
```

Testes cobrem valores conhecidos, sinais, denominador zero, agregação por somas, fontes antes da origem, t−7, cobertura e unicidade real, thresholds por corte e mutação de todo o futuro (venda/disponibilidade/atividade/desconto) sem alterar forecasts ou segmentos. A integração reconstrói os outputs em uma raiz contendo apenas train e as configurações, sem eval, staging ou marts prévios. Testes das fases anteriores continuam validando seus contratos; a checagem estrutural de eval da Fase 1 não o usa no backtest.

## Custo computacional

Execução tabular: 92.88 s. Nove Parquet: 27,094,134 bytes (25.84 MiB); resumo: 249,294 bytes. Pico de working set do processo: 1.15 GiB. DuckDB limitado a 1 GB, uma thread e spill por fold de até 2 GB; esse limite não inclui objetos pandas/PyArrow/Python. Loops são por fold ou pequenos grupos, sem loop por linha nas 2,8 milhões de previsões. Tempo/memória excluem notebook, figuras e relatório, cujos tamanhos são contabilizados separadamente na entrega.

## Limitações e recomendação

A janela é curta (90 dias, 28 avaliados) e contém somente quatro origens. Não se avaliam outras estações, horizontes, novos produtos/lojas ou significância das diferenças. A normalização da fonte limita comparações de escala; disponibilidade, promoção e mudanças de nível podem afetar vendas e segmentos. Nenhuma perda por censura foi corrigida ou identificada. As médias dos grupos misturam séries e composição variável; associação não é causalidade.

Seasonal Naive fica como referência global a superar, preservando Naive como comparação e as exceções C–Z/flag. A Fase 4 é elegível para aprovação após as validações finais; a próxima fase poderá comparar modelos adicionais sob este mesmo protocolo, somente mediante autorização. Nenhum modelo estatístico, tuning, reposição ou dashboard é implementado aqui.
