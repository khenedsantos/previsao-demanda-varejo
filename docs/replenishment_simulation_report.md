# Fase 8 — Replenishment policy simulation

## 1. Objetivo e natureza da entrega

Transformar forecasts ETS **já congelados** e incerteza histórica em limiares hipotéticos de posição de estoque. **Simulação**, na escala de venda observada normalizada: não é política real da empresa, estoque físico, ordem de compra ou demanda latente. HEAD inicial `3c52827`; zero fitting ETS, zero acesso a actuals de eval e nenhuma alteração dos forecasts. O protocolo foi escrito antes de calcular cobertura da política no fold 4: [protocolo](replenishment_simulation_protocol.md).

## 2. Por que é simulação

Faltam estoque físico completo, posição de inventário, pedidos abertos, lead times reais, fornecedores e custos. Safety stock (SS) e reorder point (ROP) são quantidades **simuladas**, sem equivalência comprovada com unidades físicas. Não se calcula quantidade a comprar, lost sales, fill rate, OTIF ou custo financeiro.

## 3. Premissas e fronteira temporal

Forecast oficial A/N/A inalterado, incluindo clipping e fallback anteriores. O input de planejamento é `final_holdout/frozen_predictions.parquet`, sem actuals, salvo antes da abertura de eval na Fase 7. Somente erros de backtest de train calibram os buffers. Rótulos históricos são os snapshots prospectivos da Fase 4, cada um conhecido antes de seu fold. Aplicação de validação usa rótulos de 18/06; snapshot final usa rótulos de 25/06. Migrações de classe entre cortes não são reclassificadas retroativamente.

## 4. Cenários e significado de cobertura alvo

| Cenário | L hipotético | Cobertura alvo |
|---|---|---|
| LEAN | 1 | 90.00% |
| BASE | 2 | 95.00% |
| PROTECTED | 3 | 98.00% |

`service_level` permanece no YAML por compatibilidade; outputs usam `target_coverage_level`. É o quantil alvo da distribuição histórica do erro contra **venda observada normalizada**, não serviço real ou garantia de ausência de ruptura. Os valores dos três cenários não foram alterados.

## 5. Erro acumulado e buffer

Nos primeiros L dias de cada fold: `lead_time_error = Σforecast − Σactual`; `lead_time_shortfall = max(Σactual − Σforecast, 0)`. Padronização: `shortfall / (error_std × sqrt(L))`. `SS = quantil_empírico × error_std × sqrt(L)`; `ROP = Σforecast[:L] + SS`. Bias continua separado do point forecast. Underforecast histórico pode aumentar o quantil de shortfall e, portanto, o buffer; isso não corrige nem altera ETS. Nenhum MAPE.

| Cenário | Fold | Bias acumulado médio | Shortfall médio |
|---|---|---|---|
| BASE | 1 | 0.073385 | 0.222497 |
| BASE | 2 | 0.053769 | 0.240778 |
| BASE | 3 | 0.109008 | 0.197311 |
| BASE | 4 | -0.253713 | 0.425160 |
| LEAN | 1 | 0.066339 | 0.131441 |
| LEAN | 2 | -0.003359 | 0.179625 |
| LEAN | 3 | 0.052355 | 0.137144 |
| LEAN | 4 | -0.131988 | 0.249689 |
| PROTECTED | 1 | 0.050899 | 0.322739 |
| PROTECTED | 2 | 0.098098 | 0.313267 |
| PROTECTED | 3 | 0.149109 | 0.274199 |
| PROTECTED | 4 | -0.420707 | 0.643743 |

## 6. Dependência temporal dos resíduos

Diagnóstico anterior à validação, somente folds 1–3. Erros centrados por média da série e divididos pelo std histórico de 21 erros. Correlações agrupam pares dentro do mesmo fold/série; nunca atravessam fronteiras. Razão de agregação = Var(soma dos primeiros L resíduos padronizados)/ΣVar(resíduo de cada passo). Trata-se de diagnóstico agrupado, não estimativa confiável de autocorrelação individual com apenas 21 erros.

| Diagnóstico | Lag/L | Pares/janelas | Valor |
|---|---|---|---|
| within_fold_lag_correlation | 1 | 900000 | 0.065042 |
| within_fold_lag_correlation | 2 | 750000 | 0.057623 |
| within_fold_lag_correlation | 3 | 600000 | 0.037049 |
| within_fold_lag_correlation | 4 | 450000 | 0.042002 |
| within_fold_lag_correlation | 5 | 300000 | 0.067097 |
| within_fold_lag_correlation | 6 | 150000 | 0.054657 |
| variance_aggregation_ratio | 1 | 150000 | 1.000000 |
| variance_aggregation_ratio | 2 | 150000 | 1.078643 |
| variance_aggregation_ratio | 3 | 150000 | 1.156390 |

As razões acima de 1 para L=2/3 contrariam a aproximação de independência. sqrt(L) é uma escala de referência; os quantis empíricos de shortfalls acumulados preservam a dependência observada dentro de cada janela. Não garantem a mesma dependência em períodos futuros nem normalidade.

## 7. Calibração empírica e suporte

Quantil linear, com 20 observações esperadas na cauda: mínimos exatos 200/400/1000. Hierarquia fixa: ABC×XYZ×exposure → ABC×XYZ → XYZ → GLOBAL, usando o nível mais específico elegível. n conta janelas série×fold; séries distintas também são registradas. Dependência entre séries e folds reduz a informação efetiva; o mínimo de cauda é uma regra de suporte, não intervalo de confiança. Escala não positiva/não finita ou GLOBAL insuficiente bloqueia. Nenhuma série teve escala inválida, nenhuma foi excluída silenciosamente e RMSE não substituiu std.

| Etapa | Cenário | Nível usado | Séries |
|---|---|---|---|
| final_snapshot | BASE | ABC_XYZ_EXPOSURE | 50000 |
| final_snapshot | LEAN | ABC_XYZ_EXPOSURE | 50000 |
| final_snapshot | PROTECTED | ABC_XYZ | 439 |
| final_snapshot | PROTECTED | ABC_XYZ_EXPOSURE | 49561 |
| validation_fold4 | BASE | ABC_XYZ_EXPOSURE | 50000 |
| validation_fold4 | LEAN | ABC_XYZ_EXPOSURE | 50000 |
| validation_fold4 | PROTECTED | ABC_XYZ | 769 |
| validation_fold4 | PROTECTED | ABC_XYZ_EXPOSURE | 49231 |

## 8. Referência Normal e sensibilidade limitada

Normal z(q) usa a mesma escala histórica, apenas como benchmark. A fórmula empírica foi pré-definida, sem seleção por holdout ou busca de dezenas de variantes. Comparar cobertura e tamanho não significa escolher o maior buffer.

| Cenário | Multiplicador empírico médio | Cobertura empírica fold4 | Cobertura Normal fold4 | SS empírico médio | SS Normal médio |
|---|---|---|---|---|---|
| LEAN | 1.121268 | 79.65% | 83.64% | 0.511824 | 0.586152 |
| BASE | 1.532885 | 84.08% | 86.14% | 0.994327 | 1.063939 |
| PROTECTED | 2.161456 | 88.32% | 87.20% | 1.720674 | 1.626981 |

| Cenário | z Normal |
|---|---|
| BASE | 1.644854 |
| LEAN | 1.281552 |
| PROTECTED | 2.053749 |

## 9. Validação temporal folds 1–3 → fold 4

Escala ddof=1 calculada com exatamente 21 erros por série; o std final da Fase 6 não é usado nesta validação. Multiplicadores e escalas são persistidos em `calibration_locked.json` antes de medir cobertura. Cobertura = fração de séries com ROP ≥ venda observada acumulada, sem pesos; gap = cobertura − alvo. **Os três targets não foram atingidos:** subcobertura de aproximadamente 9,68–10,92 pontos percentuais. A Normal também fica abaixo dos alvos; supera a cobertura empírica em LEAN/BASE, mas fica abaixo em PROTECTED. O fold4 apresenta bias acumulado médio negativo em L1/L2/L3 (−0,132/−0,254/−0,421), enquanto L2/L3 tinham bias positivo nos três folds anteriores. Essa mudança temporal coincide com maior shortfall; a calibração histórica não o cobriu nos níveis nominais. Não interpretar isso como prova causal ou corrigir o ETS. Não há ajuste posterior para forçar o target. Esta validação usa um único fold de train; não comprova cobertura futura.

| Cenário | Alvo | Observada | Gap (fração) | SS > forecast | Fallback |
|---|---|---|---|---|---|
| LEAN | 90.00% | 79.65% | -10.35% | 12.99% | 0.00% |
| BASE | 95.00% | 84.08% | -10.92% | 12.29% | 0.00% |
| PROTECTED | 98.00% | 88.32% | -9.68% | 16.01% | 1.54% |

| Cenário | Séries | SS médio | SS mediano | SS p90 | ROP médio | ROP mediano | ΣSS/Σforecast | Ratio mediano |
|---|---|---|---|---|---|---|---|---|
| LEAN | 50000 | 0.511824 | 0.375718 | 0.928358 | 1.487017 | 1.023745 | 0.524845 | 0.554574 |
| BASE | 50000 | 0.994327 | 0.725540 | 1.818773 | 2.914928 | 2.003899 | 0.517716 | 0.541710 |
| PROTECTED | 50000 | 1.720674 | 1.248513 | 3.154131 | 4.641414 | 3.195116 | 0.589123 | 0.616247 |

### Cobertura por segmentos prospectivos

| Cenário | Nível | Célula | Séries | Cobertura | Gap | Normal |
|---|---|---|---|---|---|---|
| BASE | ABC | A | 33438 | 81.94% | -13.06% | 84.00% |
| BASE | ABC | B | 12110 | 87.76% | -7.24% | 89.65% |
| BASE | ABC | C | 4452 | 90.21% | -4.79% | 92.59% |
| BASE | ABC_XYZ | A|X | 9251 | 77.16% | -17.84% | 80.15% |
| BASE | ABC_XYZ | A|Y | 10848 | 80.82% | -14.18% | 83.43% |
| BASE | ABC_XYZ | A|Z | 13339 | 86.16% | -8.84% | 87.14% |
| BASE | ABC_XYZ | B|X | 2887 | 84.93% | -10.07% | 87.67% |
| BASE | ABC_XYZ | B|Y | 3618 | 87.53% | -7.47% | 90.41% |
| BASE | ABC_XYZ | B|Z | 5605 | 89.37% | -5.63% | 90.19% |
| BASE | ABC_XYZ | C|X | 1047 | 89.02% | -5.98% | 91.31% |
| BASE | ABC_XYZ | C|Y | 1355 | 89.67% | -5.33% | 93.14% |
| BASE | ABC_XYZ | C|Z | 2050 | 91.17% | -3.83% | 92.88% |
| BASE | XYZ | X | 13185 | 79.80% | -15.20% | 82.68% |
| BASE | XYZ | Y | 15821 | 83.11% | -11.89% | 85.85% |
| BASE | XYZ | Z | 20994 | 87.51% | -7.49% | 88.52% |
| BASE | exposure | HIGH | 13288 | 79.92% | -15.08% | 83.27% |
| BASE | exposure | LOW | 12871 | 88.28% | -6.72% | 89.22% |
| BASE | exposure | MEDIUM | 23841 | 84.14% | -10.86% | 86.07% |
| LEAN | ABC | A | 33438 | 77.89% | -12.11% | 82.00% |
| LEAN | ABC | B | 12110 | 82.32% | -7.68% | 86.17% |
| LEAN | ABC | C | 4452 | 85.56% | -4.44% | 89.06% |
| LEAN | ABC_XYZ | A|X | 9251 | 73.72% | -16.28% | 79.14% |
| LEAN | ABC_XYZ | A|Y | 10848 | 76.95% | -13.05% | 81.53% |
| LEAN | ABC_XYZ | A|Z | 13339 | 81.56% | -8.44% | 84.38% |
| LEAN | ABC_XYZ | B|X | 2887 | 80.57% | -9.43% | 83.58% |
| LEAN | ABC_XYZ | B|Y | 3618 | 81.84% | -8.16% | 86.24% |
| LEAN | ABC_XYZ | B|Z | 5605 | 83.53% | -6.47% | 87.46% |
| LEAN | ABC_XYZ | C|X | 1047 | 85.00% | -5.00% | 88.54% |
| LEAN | ABC_XYZ | C|Y | 1355 | 86.35% | -3.65% | 89.52% |
| LEAN | ABC_XYZ | C|Z | 2050 | 85.32% | -4.68% | 89.02% |
| LEAN | XYZ | X | 13185 | 76.12% | -13.88% | 80.86% |
| LEAN | XYZ | Y | 15821 | 78.87% | -11.13% | 83.29% |
| LEAN | XYZ | Z | 20994 | 82.45% | -7.55% | 85.65% |
| LEAN | exposure | HIGH | 13288 | 77.47% | -12.53% | 82.83% |
| LEAN | exposure | LOW | 12871 | 82.14% | -7.86% | 85.38% |
| LEAN | exposure | MEDIUM | 23841 | 79.52% | -10.48% | 83.16% |
| PROTECTED | ABC | A | 33438 | 86.26% | -11.74% | 84.95% |
| PROTECTED | ABC | B | 12110 | 92.17% | -5.83% | 91.25% |
| PROTECTED | ABC | C | 4452 | 93.31% | -4.69% | 93.15% |
| PROTECTED | ABC_XYZ | A|X | 9251 | 81.88% | -16.12% | 80.78% |
| PROTECTED | ABC_XYZ | A|Y | 10848 | 85.33% | -12.67% | 84.57% |
| PROTECTED | ABC_XYZ | A|Z | 13339 | 90.06% | -7.94% | 88.15% |
| PROTECTED | ABC_XYZ | B|X | 2887 | 90.13% | -7.87% | 90.16% |
| PROTECTED | ABC_XYZ | B|Y | 3618 | 92.45% | -5.55% | 91.87% |
| PROTECTED | ABC_XYZ | B|Z | 5605 | 93.04% | -4.96% | 91.40% |
| PROTECTED | ABC_XYZ | C|X | 1047 | 92.93% | -5.07% | 92.36% |
| PROTECTED | ABC_XYZ | C|Y | 1355 | 92.92% | -5.08% | 93.65% |
| PROTECTED | ABC_XYZ | C|Z | 2050 | 93.76% | -4.24% | 93.22% |
| PROTECTED | XYZ | X | 13185 | 84.57% | -13.43% | 83.75% |
| PROTECTED | XYZ | Y | 15821 | 87.61% | -10.39% | 87.02% |
| PROTECTED | XYZ | Z | 20994 | 91.22% | -6.78% | 89.51% |
| PROTECTED | exposure | HIGH | 13288 | 84.36% | -13.64% | 83.47% |
| PROTECTED | exposure | LOW | 12871 | 92.10% | -5.90% | 90.77% |
| PROTECTED | exposure | MEDIUM | 23841 | 88.49% | -9.51% | 87.36% |

## 10. Calibração final com quatro folds

Após a validação, a mesma regra usa quatro folds (200.000 janelas por cenário) e o std congelado da Fase 6, com 28 erros por série. Rótulos das observações de calibração continuam prospectivos; aplicação final usa classes de 25/06. Nenhum actual eval participa. A cobertura fold4 pertence à calibração 1–3 e fica nula nas linhas de calibração final; não apresentamos desempenho do próprio conjunto de calibração como validação independente.

| Cenário | Séries | SS médio | SS mediano | SS p90 | ROP médio | ROP mediano | ΣSS/Σforecast | Ratio mediano |
|---|---|---|---|---|---|---|---|---|
| LEAN | 50000 | 0.572306 | 0.420960 | 1.036319 | 1.646254 | 1.113975 | 0.532899 | 0.569898 |
| BASE | 50000 | 1.147687 | 0.833226 | 2.095767 | 3.263576 | 2.200754 | 0.542413 | 0.572994 |
| PROTECTED | 50000 | 2.024079 | 1.470216 | 3.709359 | 5.239064 | 3.554384 | 0.629576 | 0.663305 |

| Cenário | Multiplicador final médio | SS Normal médio | SS > forecast | Ratios indefinidos |
|---|---|---|---|---|
| LEAN | 1.188375 | 0.618131 | 13.54% | 231 |
| BASE | 1.668896 | 1.121985 | 13.19% | 129 |
| PROTECTED | 2.399520 | 1.715745 | 18.42% | 70 |

## 11. LEAN

L=1, q=90%: SS médio **0.572306**, ROP médio **1.646254**, ratio agregado **53.29%**. Em relação a LEAN, SS cresce **0.00%** e ROP **0.00%**. O fator explícito sqrt(L) é 1.000000; multiplicador final médio 1.188375. L e q variam juntos: efeitos não são identificáveis separadamente por estes três cenários. Forecast acumulado, escala sqrt(L) e quantil contribuem simultaneamente; não há cenário vencedor automático.

## 12. BASE

L=2, q=95%: SS médio **1.147687**, ROP médio **3.263576**, ratio agregado **54.24%**. Em relação a LEAN, SS cresce **100.54%** e ROP **98.24%**. O fator explícito sqrt(L) é 1.414214; multiplicador final médio 1.668896. L e q variam juntos: efeitos não são identificáveis separadamente por estes três cenários. Forecast acumulado, escala sqrt(L) e quantil contribuem simultaneamente; não há cenário vencedor automático.

## 13. PROTECTED

L=3, q=98%: SS médio **2.024079**, ROP médio **5.239064**, ratio agregado **62.96%**. Em relação a LEAN, SS cresce **253.67%** e ROP **218.24%**. O fator explícito sqrt(L) é 1.732051; multiplicador final médio 2.399520. L e q variam juntos: efeitos não são identificáveis separadamente por estes três cenários. Forecast acumulado, escala sqrt(L) e quantil contribuem simultaneamente; não há cenário vencedor automático.

## 14. ABC

| Cenário | Classe | Séries | SS médio | ROP médio | Ratio mediano | Participação no SS |
|---|---|---|---|---|---|---|
| BASE | A | 33379 | 1.328464 | 3.916816 | 0.557019 | 77.27% |
| BASE | B | 12160 | 0.812226 | 2.010347 | 0.605177 | 17.21% |
| BASE | C | 4461 | 0.709453 | 1.791885 | 0.602625 | 5.52% |
| LEAN | A | 33379 | 0.655789 | 1.970258 | 0.544837 | 76.50% |
| LEAN | B | 12160 | 0.413605 | 1.020779 | 0.615483 | 17.58% |
| LEAN | C | 4461 | 0.380242 | 0.926877 | 0.644517 | 5.93% |
| PROTECTED | A | 33379 | 2.344743 | 6.275851 | 0.647883 | 77.33% |
| PROTECTED | B | 12160 | 1.433146 | 3.254081 | 0.695288 | 17.22% |
| PROTECTED | C | 4461 | 1.235531 | 2.892168 | 0.686289 | 5.45% |

## 15. XYZ

| Cenário | Classe | Séries | SS médio | ROP médio | Ratio mediano | Participação no SS |
|---|---|---|---|---|---|---|
| BASE | X | 13117 | 1.055383 | 3.127004 | 0.542078 | 24.12% |
| BASE | Y | 15677 | 1.063497 | 3.082297 | 0.563785 | 29.05% |
| BASE | Z | 21206 | 1.267020 | 3.482068 | 0.614497 | 46.82% |
| LEAN | X | 13117 | 0.521871 | 1.570223 | 0.536161 | 23.92% |
| LEAN | Y | 15677 | 0.535065 | 1.560162 | 0.567524 | 29.31% |
| LEAN | Z | 21206 | 0.631033 | 1.756929 | 0.606523 | 46.76% |
| PROTECTED | X | 13117 | 1.863071 | 5.029207 | 0.620952 | 24.15% |
| PROTECTED | Y | 15677 | 1.847938 | 4.918989 | 0.646901 | 28.63% |
| PROTECTED | Z | 21206 | 2.253886 | 5.605495 | 0.726084 | 47.23% |

## 16. exposure

| Cenário | Classe | Séries | SS médio | ROP médio | Ratio mediano | Participação no SS |
|---|---|---|---|---|---|---|
| BASE | HIGH | 12606 | 1.515596 | 4.836610 | 0.502472 | 33.29% |
| BASE | LOW | 13591 | 1.018188 | 2.532533 | 0.651683 | 24.11% |
| BASE | MEDIUM | 23803 | 1.026784 | 2.847912 | 0.568170 | 42.59% |
| LEAN | HIGH | 12606 | 0.719663 | 2.395912 | 0.472051 | 31.70% |
| LEAN | LOW | 13591 | 0.516010 | 1.294739 | 0.657008 | 24.51% |
| LEAN | MEDIUM | 23803 | 0.526409 | 1.449945 | 0.574644 | 43.79% |
| PROTECTED | HIGH | 12606 | 2.678364 | 7.720423 | 0.588247 | 33.36% |
| PROTECTED | LOW | 13591 | 1.800436 | 4.088671 | 0.750934 | 24.18% |
| PROTECTED | MEDIUM | 23803 | 1.805267 | 4.581794 | 0.654845 | 42.46% |

## 17. Overlays de risco e exemplos

Censoring, persistência e risk_cell não são dimensões de calibração nem multiplicadores. A + CENSORING_AND_UNDERFORECAST destaca coexistência de relevância, buffer e sinais de observação; é grupo de investigação, não compra automática. Nenhum score ou nova classificação de prioridade.

| Cenário | Recorte | Sinal | Séries | SS médio | ROP médio | Ratio mediano | Participação no SS total |
|---|---|---|---|---|---|---|---|
| BASE | A_double_signal | A|CENSORING_AND_UNDERFORECAST | 706 | 1.736288 | 5.535646 | 0.489099 | 2.14% |
| BASE | risk_cell | CENSORING_AND_UNDERFORECAST | 1028 | 1.579787 | 4.869930 | 0.514998 | 2.83% |
| BASE | risk_cell | CENSORING_ONLY | 1623 | 1.637111 | 3.572207 | 0.906104 | 4.63% |
| BASE | risk_cell | NEITHER | 31848 | 1.102954 | 2.881253 | 0.614608 | 61.21% |
| BASE | risk_cell | UNDERFORECAST_ONLY | 15501 | 1.159694 | 3.910244 | 0.479429 | 31.33% |
| LEAN | A_double_signal | A|CENSORING_AND_UNDERFORECAST | 706 | 0.834146 | 2.738789 | 0.464472 | 2.06% |
| LEAN | risk_cell | CENSORING_AND_UNDERFORECAST | 1028 | 0.764963 | 2.415925 | 0.494212 | 2.75% |
| LEAN | risk_cell | CENSORING_ONLY | 1623 | 0.789213 | 1.765071 | 0.858216 | 4.48% |
| LEAN | risk_cell | NEITHER | 31848 | 0.552282 | 1.457881 | 0.615075 | 61.47% |
| LEAN | risk_cell | UNDERFORECAST_ONLY | 15501 | 0.577959 | 1.969798 | 0.475931 | 31.31% |
| PROTECTED | A_double_signal | A|CENSORING_AND_UNDERFORECAST | 706 | 3.081001 | 8.768777 | 0.582133 | 2.15% |
| PROTECTED | risk_cell | CENSORING_AND_UNDERFORECAST | 1028 | 2.800253 | 7.732467 | 0.610820 | 2.84% |
| PROTECTED | risk_cell | CENSORING_ONLY | 1623 | 2.893684 | 5.845449 | 1.056610 | 4.64% |
| PROTECTED | risk_cell | NEITHER | 31848 | 1.944720 | 4.658866 | 0.709347 | 61.20% |
| PROTECTED | risk_cell | UNDERFORECAST_ONLY | 15501 | 2.044603 | 6.202279 | 0.558541 | 31.32% |

Sete exemplos gráficos reutilizados da Fase 6. Tabela auxiliar `top_a_buffers` lista dez maiores buffers A por cenário, desempate crescente por IDs; não substitui a seleção gráfica nem define prioridade de compra.

| Cenário | Loja A | Produto | SS | ROP | Overlay |
|---|---|---|---|---|---|
| BASE | 550 | 267 | 18.586455 | 70.967698 | NEITHER |
| BASE | 514 | 267 | 17.163496 | 67.816410 | NEITHER |
| BASE | 496 | 267 | 16.828740 | 80.657724 | NEITHER |
| BASE | 475 | 267 | 16.692413 | 80.958116 | NEITHER |
| BASE | 833 | 267 | 16.569484 | 72.813133 | CENSORING_AND_UNDERFORECAST |
| BASE | 304 | 267 | 16.278619 | 72.857022 | CENSORING_AND_UNDERFORECAST |
| BASE | 681 | 267 | 16.252060 | 62.968885 | UNDERFORECAST_ONLY |
| BASE | 52 | 267 | 15.967898 | 61.632363 | UNDERFORECAST_ONLY |
| BASE | 69 | 267 | 14.968463 | 52.656837 | NEITHER |
| BASE | 830 | 267 | 14.545380 | 69.195219 | UNDERFORECAST_ONLY |
| LEAN | 550 | 267 | 8.989935 | 36.563184 | NEITHER |
| LEAN | 514 | 267 | 8.301675 | 32.707686 | NEITHER |
| LEAN | 496 | 267 | 8.139760 | 38.419157 | NEITHER |
| LEAN | 475 | 267 | 8.073821 | 40.807839 | NEITHER |
| LEAN | 833 | 267 | 8.014362 | 36.191860 | CENSORING_AND_UNDERFORECAST |
| LEAN | 304 | 267 | 7.873676 | 36.385099 | CENSORING_AND_UNDERFORECAST |
| LEAN | 681 | 267 | 7.860830 | 29.512804 | UNDERFORECAST_ONLY |
| LEAN | 52 | 267 | 7.723386 | 29.858336 | UNDERFORECAST_ONLY |
| LEAN | 69 | 267 | 7.239977 | 25.130735 | NEITHER |
| LEAN | 80 | 267 | 7.068027 | 23.898103 | UNDERFORECAST_ONLY |
| PROTECTED | 550 | 267 | 33.131701 | 111.459077 | NEITHER |
| PROTECTED | 514 | 267 | 30.595174 | 109.214962 | NEITHER |
| PROTECTED | 496 | 267 | 29.998446 | 124.284830 | NEITHER |
| PROTECTED | 475 | 267 | 29.755434 | 127.219454 | NEITHER |
| PROTECTED | 833 | 267 | 29.536305 | 113.835424 | CENSORING_AND_UNDERFORECAST |
| PROTECTED | 304 | 267 | 29.017816 | 113.776951 | CENSORING_AND_UNDERFORECAST |
| PROTECTED | 681 | 267 | 28.970473 | 100.957092 | UNDERFORECAST_ONLY |
| PROTECTED | 52 | 267 | 28.463934 | 99.993057 | UNDERFORECAST_ONLY |
| PROTECTED | 69 | 267 | 26.682369 | 84.340407 | NEITHER |
| PROTECTED | 830 | 267 | 25.928192 | 107.915172 | UNDERFORECAST_ONLY |

| Regra congelada | Loja | Produto | Cenário | Forecast L | SS | ROP |
|---|---|---|---|---|---|---|
| A_NEITHER | 243 | 223 | BASE | 2.431930 | 0.956569 | 3.388499 |
| A_NEITHER | 243 | 223 | LEAN | 1.207422 | 0.479290 | 1.686712 |
| A_NEITHER | 243 | 223 | PROTECTED | 3.689417 | 1.691790 | 5.381206 |
| A_UNDERFORECAST_ONLY | 232 | 310 | BASE | 4.210534 | 1.086942 | 5.297476 |
| A_UNDERFORECAST_ONLY | 232 | 310 | LEAN | 2.149992 | 0.500915 | 2.650907 |
| A_UNDERFORECAST_ONLY | 232 | 310 | PROTECTED | 6.162268 | 1.951178 | 8.113446 |
| A_CENSORING_ONLY | 596 | 129 | BASE | 1.121705 | 1.421110 | 2.542815 |
| A_CENSORING_ONLY | 596 | 129 | LEAN | 0.434332 | 0.687366 | 1.121698 |
| A_CENSORING_ONLY | 596 | 129 | PROTECTED | 1.653648 | 2.533232 | 4.186880 |
| A_CENSORING_AND_UNDERFORECAST | 360 | 600 | BASE | 3.961165 | 1.391229 | 5.352394 |
| A_CENSORING_AND_UNDERFORECAST | 360 | 600 | LEAN | 1.980822 | 0.672912 | 2.653734 |
| A_CENSORING_AND_UNDERFORECAST | 360 | 600 | PROTECTED | 5.998250 | 2.479966 | 8.478215 |
| A_MAX_ERROR_STD | 550 | 267 | BASE | 52.381243 | 18.586455 | 70.967698 |
| A_MAX_ERROR_STD | 550 | 267 | LEAN | 27.573249 | 8.989935 | 36.563184 |
| A_MAX_ERROR_STD | 550 | 267 | PROTECTED | 78.327376 | 33.131701 | 111.459077 |
| A_MAX_UNDERFORECAST_RATE | 305 | 300 | BASE | 21.292209 | 4.772217 | 26.064426 |
| A_MAX_UNDERFORECAST_RATE | 305 | 300 | LEAN | 11.505700 | 2.308236 | 13.813936 |
| A_MAX_UNDERFORECAST_RATE | 305 | 300 | PROTECTED | 31.798583 | 8.506823 | 40.305406 |
| LOW_EXPOSURE_MIN_MAE | 503 | 500 | BASE | 0.166688 | 0.250346 | 0.417034 |
| LOW_EXPOSURE_MIN_MAE | 503 | 500 | LEAN | 0.068359 | 0.122517 | 0.190876 |
| LOW_EXPOSURE_MIN_MAE | 503 | 500 | PROTECTED | 0.245554 | 0.454158 | 0.699712 |

## 18. Limitações

Só quatro folds semanais, uma validação temporal de sete dias e três janelas de calibração por série; caudas são estimadas por pooling. Série×fold não é amostra independente. Classes podem migrar. Padronização é estimada no próprio conjunto de calibração e não incorpora sua incerteza. O diagnóstico de dependência é agrupado e não modela todos os choques comuns. Vendas observadas podem ser censuradas; o buffer não estima demanda latente nem recupera lost sales. Ausência de custos impede ótimo econômico. Equivalência em dias é ROP/(Σforecast7/7), somente com denominador positivo, sem garantia de dias reais. Ratios individuais podem ser grandes em pequena escala; denominadores zero geram nulo, e ratio agregado difere da mediana individual. O planejamento é snapshot histórico de 26/06, não recomendação atual. Um target nominal não garante cobertura de cada segmento.

## 19. Implicações para decisão

**Recomendação técnica: Fase 8 aprovada como simulação descritiva para revisão**, sem autorização de política real. Examinar gaps e concentrações, investigar séries A com duplo sinal e confrontar hipóteses com dados operacionais reais no futuro. PROTECTED representa mais buffer sob outras hipóteses; não é automaticamente melhor. Nenhuma flag aumenta SS.

## 20. Marts, reprodutibilidade e preparação para consumo futuro

`mart_replenishment_simulation`: IDs + scenario, 150.000 linhas; as_of 25/06 e available_from 26/06. `mart_replenishment_calibration`: stage + scenario + calibration_level_used + calibration_key; inclui células candidatas elegíveis ou não, suporte, séries distintas e status PRIMARY/FALLBACK/NOT_USED. Cobertura por célula é calculada somente nas séries efetivamente atribuídas no fold4, não em todo o pool de treinamento. `mart_replenishment_summary`: stage + scenario + level + cell. Filtrar stage/level antes de somar; recortes de risco e A_double_signal se sobrepõem aos níveis populacionais. `historical_fold4_coverage` é referência temporal com composição histórica potencialmente distinta, não cobertura realizada do snapshot final. Normal e cobertura histórica não são escolha de política. Não foi iniciado Power BI.

| Artefato | Linhas | Bytes | SHA-256 |
|---|---|---|---|
| dependence | 9 | 3102 | 6195071254fdb487a4edf7b18c56819a0f6c120c93f51674b1bdca1d16ee780a |
| validation_scale | 50000 | 1007599 | db96d3cb68de5d39cc6f9eb8a01b4d88c812ddf19e7ff4edd9475fc555a3ca43 |
| calibration_folds123 | 120 | 9180 | 21053d9b3d4b5606ebbbc495f514b3bd55a038010d9f638f5bc505a190d2f4ed |
| fold4_validation | 150000 | 12894594 | c07dd37af52e6b0be6fc4b8476606e58faa03d524288a01a126617d4ca52be3a |
| simulation | 150000 | 11802249 | 47d98eec77c2b23687d4453786b1b37a0f15b4a441cde7f8e479424e5713e7e4 |
| calibration | 240 | 16771 | e9ea50439a42e4c34a8988d90a1481aef302cc8f5fb25e683d7201afe9487db6 |
| summary | 129 | 46296 | eb87e6a30afc2a3579d739920a870d8d8f10b2835826eda253e4eab750dec193 |
| examples | 21 | 22519 | 528c98eb704c485d11eb244a946dd9e59b1aeece9c49749095be86056b74a8e7 |
| lead_time_diagnostics | 21 | 5434 | 08adaa3bfbe677974aaae9c793aa4ea2ceab721d972a237d0957587a9b0edbbb |
| fallback_distribution | 8 | 3062 | a339b1131c29fe7d0689e315b8bf644e716c3cc88d7e1e9194e3f28b3e222c47 |
| top_a_buffers | 30 | 22948 | bb786b0386ae2986cb19485f0739d662091ff9788015ef139c589fd87779acb9 |

### Inputs congelados e hashes

| Input | Caminho | SHA-256 |
|---|---|---|
| backtest | data/processed/mart_forecast_statistical.parquet | e37cbec4f5b04c1da503dd459f3fbb9f41eeeed4bfdbfab762d3177e5d96631f |
| segments | data/outputs/forecasting_baselines/fold_segments.parquet | 86f01def1657d24812a57c3d4f6dc95248674d7a1161cf8aaa3484b14c753957 |
| uncertainty | data/processed/mart_forecast_uncertainty.parquet | 2aaff8293974c0e7ddd1e2d5913c1534dc491e46e4d2fae1907c9f01c068de51 |
| risk_profile | data/processed/mart_demand_risk_profile.parquet | b9ac3aaecae0633aed435b618a7e39d8e2912cf7e9375f1e10e21241bd919102 |
| examples | data/outputs/forecast_uncertainty/example_selection.parquet | 8bebd4d94ffa08b3bc598f6b260630803e005aff53b306d4ed054361a8f4b92f |
| predictions | data/outputs/final_holdout/frozen_predictions.parquet | d66ee703bbbc16d456da0a7befcd25815422b10e0fc025245f70f35b944d0dd0 |

Config SHA-256: `ba397890847c48952e7e35b9537315543de248d922b8a1e2f7a746777c9e5dd8`. Protocolo SHA-256: `e193684ad1284995dd03ef576a6c581b5d9ac500a706ec4d0d22406981d381fc`. `summary.json` registra HEAD, fontes, hashes, fórmula, quantis, hierarquia e outputs determinísticos. Runtime fica separado e não participa dos hashes reprodutíveis.

Execução original: **452.82 s**, pico do processo **931.49 MiB**, Parquet **24.64 MiB**. Zero fitting ETS; barreira em `ExponentialSmoothing.fit`.

Notebook `07_replenishment_simulation.ipynb`: dez figuras, consumo exclusivo de outputs, lógica crítica em src. Validação automatizada inclui fórmulas sintéticas, grão populacional, exclusão de fold4 da calibração, invariância a flags e reprodução integral com eval ausente e depois corrompido artificialmente, sem acesso ao eval real. A suíte legada completa não deve ser executada nesta fase: contém fitting ETS e abertura de raw/holdout. O registro da Fase 7 de 118 testes aprovados e as exclusões históricas das fases anteriores permanecem preservados. Resultado específico da rodada está em `validation.json`, separado da análise. Dados, outputs, ambiente e temporários permanecem ignorados; sem stage ou commit.

### Resultado da validação desta rodada

**21 testes aprovados**, 0 falhas, 0 erros, 0 skips na seleção executada, em 30.495 s: 11 testes da Fase 8 e dez verificações de ambiente. Suítes legadas não executadas por poderem ajustar modelos ou abrir raw/holdout. Dois builds completos na raiz de teste (sem eval e depois com arquivos artificiais inválidos) reproduziram os 11 Parquet e summary.json exatamente. Zero fitting e nenhuma leitura de actuals eval. `pip check` sem incompatibilidades; `git diff --check` aprovado; stage vazio. Dez figuras inspecionadas, dez imagens no notebook e zero erros.

A concatenação de chaves de célula foi vetorizada sem mudar fórmulas ou outputs. A última reprodução do código atual levou **11.85 s**; pico cumulativo do processo pytest **1037.02 MiB** (inclui os dois builds e testes). A execução original, mais lenta, permanece registrada acima para auditoria. Nenhum forecast foi refeito.
