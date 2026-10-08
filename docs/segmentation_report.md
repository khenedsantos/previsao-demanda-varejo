# Fase 3 — Segmentação e perfil operacional

Gerado por `python scripts/build_segmentation.py`. Três dimensões independentes: ABC por contribuição de venda normalizada do produto; XYZ por estabilidade observada da série; exposição à ruptura e flag de possível censura. **Não há score composto.**

Fonte exclusiva: train, 28/03/2024 a 2024-06-25; 865 produtos; 50,000 séries loja-produto. Eval não foi usado. Nenhum forecasting, backtesting, modelo, reposição ou dashboard foi implementado.

## ABC — relevância do produto

A contribuição é a soma de sale_amount no train, recalculada diretamente do arquivo oficial. Produtos são ordenados por contribuição decrescente e depois product_id crescente. Não representa receita, margem ou unidade física.

**Fronteira:** seja P o acumulado antes do produto. A se P<0,80; B se 0,80≤P<0,95; C se P≥0,95. Assim, o produto que cruza o limite fica na classe cujo intervalo está sendo completado. Igualdade com uma fronteira, com tolerância absoluta de 1e-12 na participação, significa que o intervalo já está completo. Empates não são agrupados; product_id resolve a ordem. Não há cotas por contagem nem números de produtos hardcoded na classificação.

| abc_class | n_products | normalized_sales_total | normalized_sales_share | n_series |
|---|---|---|---|---|
| A | 122 | 3596479.260000 | 0.800345 | 33379 |
| B | 167 | 672498.970000 | 0.149655 | 12160 |
| C | 576 | 224682.557000 | 0.050000 | 4461 |

Produtos que encerram cada classe:

| abc_class | product_id | abc_rank | normalized_sales_cumulative_share_before | normalized_sales_cumulative_share |
|---|---|---|---|---|
| A | 806 | 122 | 0.798619283944 | 0.800345070639 |
| B | 109 | 289 | 0.949608072853 | 0.950000107340 |
| C | 173 | 865 | 0.999992573983 | 1.000000000000 |

ABC é propagado por product_id para todas as séries daquele produto. Não é recalculado por loja-produto. A classe representa relevância global no painel observado; quantidade de lojas em que o produto aparece também influencia sua contribuição.

## XYZ — métricas, redundância e escolha

Avaliadas: CV diário, CV semanal, correlação e MAE entre os perfis semanais das metades, lag 7, zero_ratio e ADI. Matrizes calculadas por pares completos; as quatro séries sem estabilidade válida não são preenchidas. Cada célula tem contagem de pares no Parquet de suporte.

### Pearson

| métrica | CV_dia | CV_semana | corr_forma | MAE_forma | lag7 | zeros | ADI |
|---|---|---|---|---|---|---|---|
| CV_dia | 1.000000 | 0.810912 | -0.098821 | 0.684981 | 0.060739 | 0.733595 | 0.696970 |
| CV_semana | 0.810912 | 1.000000 | -0.097200 | 0.475941 | 0.366551 | 0.595109 | 0.569221 |
| corr_forma | -0.098821 | -0.097200 | 1.000000 | -0.496836 | 0.244117 | -0.202028 | -0.178694 |
| MAE_forma | 0.684981 | 0.475941 | -0.496836 | 1.000000 | -0.072668 | 0.692595 | 0.662028 |
| lag7 | 0.060739 | 0.366551 | 0.244117 | -0.072668 | 1.000000 | -0.115009 | -0.103814 |
| zeros | 0.733595 | 0.595109 | -0.202028 | 0.692595 | -0.115009 | 1.000000 | 0.965058 |
| ADI | 0.696970 | 0.569221 | -0.178694 | 0.662028 | -0.103814 | 0.965058 | 1.000000 |

### Spearman

| métrica | CV_dia | CV_semana | corr_forma | MAE_forma | lag7 | zeros | ADI |
|---|---|---|---|---|---|---|---|
| CV_dia | 1.000000 | 0.802030 | -0.078767 | 0.584763 | 0.081769 | 0.664557 | 0.664557 |
| CV_semana | 0.802030 | 1.000000 | -0.075789 | 0.362799 | 0.359572 | 0.480472 | 0.480472 |
| corr_forma | -0.078767 | -0.075789 | 1.000000 | -0.565586 | 0.255605 | -0.207144 | -0.207144 |
| MAE_forma | 0.584763 | 0.362799 | -0.565586 | 1.000000 | -0.095814 | 0.570179 | 0.570179 |
| lag7 | 0.081769 | 0.359572 | 0.255605 | -0.095814 | 1.000000 | -0.114237 | -0.114237 |
| zeros | 0.664557 | 0.480472 | -0.207144 | 0.570179 | -0.114237 | 1.000000 | 1.000000 |
| ADI | 0.664557 | 0.480472 | -0.207144 | 0.570179 | -0.114237 | 1.000000 | 1.000000 |

CV diário e semanal têm Pearson ≈0,81 e Spearman ≈0,80: usar ambos como critérios principais duplicaria boa parte do sinal. CV semanal e correlação de forma têm associação linear/rank fraca (≈−0,10/−0,08), representando aspectos complementares. MAE de forma aumenta com CV diário (≈0,69) e se associa inversamente à correlação da forma (≈−0,50); fica como diagnóstico, sem adicionar um terceiro corte. Isso é parcimônia, não prova de equivalência entre métricas.

**Conjunto mínimo escolhido: CV semanal + correlação do padrão entre metades.** O primeiro descreve variação dos totais entre semanas; o segundo, persistência da forma por weekday. Essa escolha evita penalizar automaticamente variação diária causada por um padrão semanal repetível. CV diário, MAE, lag 7, zeros e fim de semana continuam disponíveis para validação.

Lag 7 não define classe: na Fase 2 ele também refletiu variação de nível. ADI é 1/(1−zero_ratio); Spearman=1, apesar de Pearson não ser exatamente 1 pela não linearidade. Zero_ratio permanece diagnóstico: as 74 séries com maioria de zeros já estão em Z pela regra escolhida. Não se adiciona uma exceção redundante nem se trata o painel como predominantemente intermitente.

### Alternativas transparentes comparadas

Todas usam Z se CV≥limite superior OU estabilidade≤limite inferior; X se CV≤limite baixo E estabilidade≥limite bom, após a regra Z; Y nos demais casos. Quantis são calculados somente em train, por interpolação linear. Mediana/caudas significa p50/p75 no CV e p25/p50 na estabilidade.

| regra | CV_baixo | CV_alto | forma_baixa | forma_boa | X | Y | Z | mudam_vs_escolhida |
|---|---|---|---|---|---|---|---|---|
| weekly_quartiles | 0.197197 | 0.381016 | 0.058267 | 0.659168 | 3448 | 25346 | 21206 | 9669 |
| weekly_median_tail | 0.265992 | 0.381016 | 0.058267 | 0.394744 | 13117 | 15677 | 21206 | 0 |
| weekly_tertiles | 0.218772 | 0.333567 | 0.185500 | 0.573624 | 5953 | 16962 | 27085 | 13043 |
| daily_median_tail | 0.514077 | 0.641412 | 0.058267 | 0.394744 | 13150 | 15770 | 21080 | 9226 |

Escolhida **weekly_median_tail**: reserva X para desempenho simultaneamente favorável nas duas dimensões (metades melhores) e Z para uma cauda desfavorável (quartil). Quartis em ambos os lados restringem X a cerca de 7% do painel; tercis ampliam Z para mais da metade. A opção escolhida preserva separação descritiva entre classes sem impor tamanhos iguais. A alternativa de CV diário tem distribuição semelhante, mas mede também oscilação dentro da semana. Apesar das contagens próximas, a troca para CV diário muda 9.226 séries (18,45%): tamanhos semelhantes não implicam as mesmas séries em cada classe. Não existe quebra natural única demonstrada nas distribuições: os quantis são uma convenção relativa, explicitamente escolhida, e não limites físicos universais ou thresholds otimizados para erro preditivo.

### Regra final e limites calculados

- **Z:** CV semanal ≥ **0.381015820606** (p75) OU correlação da forma ≤ **0.058267078628** (p25).
- **X:** sem critério Z, CV semanal ≤ **0.265992446005** (p50) E correlação da forma ≥ **0.394743548722** (p50).
- **Y:** demais séries. Empates ficam juntos; Z tem prioridade se houver sobreposição de limites.

| xyz_class | n_series | series_share |
|---|---|---|
| X | 13117 | 0.262340 |
| Y | 15677 | 0.313540 |
| Z | 21206 | 0.424120 |

### Casos indefinidos e razões auditáveis

Uma métrica indefinida nunca é substituída por zero. Havendo evidência válida de Z na outra métrica, a série recebe Z com razão específica; sem essa evidência, recebe Y_INCOMPLETE_METRICS (classe provisória de revisão, sem presumir estabilidade). As quatro séries reais têm CV semanal acima de p75 e recebem Z_HIGH_CV_NO_PATTERN. Nenhuma série foi descartada.

| store_id | product_id | weekly_coefficient_of_variation | xyz_class | xyz_reason |
|---|---|---|---|---|
| 230 | 757 | 1.636890 | Z | Z_HIGH_CV_NO_PATTERN |
| 364 | 384 | 1.405468 | Z | Z_HIGH_CV_NO_PATTERN |
| 455 | 757 | 1.311877 | Z | Z_HIGH_CV_NO_PATTERN |
| 484 | 757 | 1.916415 | Z | Z_HIGH_CV_NO_PATTERN |

| xyz_reason | definição |
|---|---|
| X_LOW_CV_STABLE | CV até a mediana e estabilidade a partir da mediana; nenhum critério Z. |
| Y_INTERMEDIATE | Métricas válidas, fora dos critérios X e Z. |
| Z_HIGH_CV | CV a partir do p75; estabilidade não está na cauda inferior. |
| Z_LOW_STABILITY | Estabilidade até p25; CV não está na cauda superior. |
| Z_BOTH | CV a partir de p75 e estabilidade até p25. |
| Z_HIGH_CV_NO_PATTERN | Estabilidade indefinida; CV válido a partir de p75 já justifica Z. |
| Z_LOW_PATTERN_NO_CV | CV indefinido; estabilidade válida até p25 já justifica Z. |
| Y_INCOMPLETE_METRICS | Sem evidência válida suficiente para X ou Z; revisar, não presumir estabilidade. |

### Validação do comportamento das classes

Medianas por classe. A separação nas métricas que definem a regra é esperada por construção; não constitui validação preditiva independente. Quantis e contagens válidas estão no output de suporte.

| xyz_class | coefficient_of_variation | weekly_coefficient_of_variation | weekly_pattern_half_correlation | weekly_pattern_half_mae | autocorrelation_lag7 | zero_ratio | mean_demand | weekend_weekday_relative_difference |
|---|---|---|---|---|---|---|---|---|
| X | 0.435236 | 0.194340 | 0.654477 | 0.144212 | 0.189688 | 0.011111 | 0.713333 | 0.321488 |
| Y | 0.500968 | 0.279893 | 0.344906 | 0.188036 | 0.192723 | 0.022222 | 0.662667 | 0.255966 |
| Z | 0.631284 | 0.407659 | -0.010043 | 0.245689 | 0.224612 | 0.033333 | 0.626667 | 0.189968 |

CV diário/semanal e MAE aumentam de X para Z; correlação de forma diminui. Lag 7 não segue essa ordem: sua mediana em Z é maior que em X. Portanto Z descreve instabilidade nos eixos escolhidos, não dificuldade de previsão comprovada. Somente a fase futura de forecast/backtesting poderá avaliar essa hipótese operacional.

## Exposição à ruptura e possível censura

Métrica principal: stockout_rate, com p25=**0.344444444444** e p75=**0.522222222222**. LOW se taxa≤p25; HIGH se taxa≥p75; MEDIUM entre eles. HIGH tem prioridade se os quantis coincidirem. São exposições relativas ao painel, não níveis absolutos aceitáveis de disponibilidade. LOW ainda pode ter ruptura frequente.

Horas totais, maior sequência e duração média dos dias afetados validam a dimensão, sem pesos e sem alterar XYZ.

| stockout_exposure | n_series | normalized_sales_total | mean_stockout_rate | median_stockout_rate | censoring_risk_count |
|---|---|---|---|---|---|
| HIGH | 12606 | 1565788.010000 | 0.643285 | 0.611111 | 2651 |
| LOW | 13591 | 969464.815000 | 0.284174 | 0.300000 | 0 |
| MEDIUM | 23803 | 1958407.962000 | 0.426919 | 0.422222 | 0 |

Medianas das métricas de suporte:

| stockout_exposure | stockout_rate | total_stockout_hours | maximum_consecutive_stockout_days | mean_stockout_hours_when_affected | zero_ratio |
|---|---|---|---|---|---|
| LOW | 0.300000 | 201.000000 | 5.000000 | 7.800000 | 0.033333 |
| MEDIUM | 0.422222 | 253.000000 | 6.000000 | 6.630435 | 0.011111 |
| HIGH | 0.611111 | 357.000000 | 11.000000 | 6.363636 | 0.011111 |

Horas totais e maior sequência medianas crescem de LOW para HIGH, mas a duração média por dia afetado não: sua mediana cai de 7,80 para 6,36 horas. Frequência e duração capturam aspectos diferentes. Por isso HIGH não é apresentado como índice completo de severidade, e LOW não é interpretado como ausência de problema de disponibilidade.

**censoring_risk_flag** = stockout_rate≥p75 E zero_ratio≥p75 (**0.055555555556**). Resultado recalculado: **2,651 séries (5.30%)**, reproduzindo o achado da Fase 2. Entre os zeros desse grupo, 96.28% coincidem com ruptura em [06h,22h). É alta exposição à possível censura da venda observada, não demanda perdida comprovada. A ausência da flag não comprova ausência de censura.

## Matriz ABC × XYZ

Participação = venda da célula / venda total normalizada do train. Produtos podem aparecer em várias colunas XYZ por terem séries de classes diferentes; **n_products não é aditivo** entre células. Contagem/participação de censoring refere-se às séries dentro da célula.

| abc_class | xyz_class | n_series | n_products | normalized_sales_total | normalized_sales_share | mean_stockout_rate | median_stockout_rate | censoring_risk_count | censoring_risk_share | high_exposure_count |
|---|---|---|---|---|---|---|---|---|---|---|
| A | X | 9012 | 111 | 1043298.679000 | 0.232171 | 0.476720 | 0.466667 | 113 | 0.012539 | 3127 |
| A | Y | 10557 | 121 | 1126226.033000 | 0.250626 | 0.446846 | 0.422222 | 278 | 0.026333 | 2692 |
| A | Z | 13810 | 122 | 1426954.548000 | 0.317548 | 0.450703 | 0.433333 | 1386 | 0.100362 | 3779 |
| B | X | 2966 | 136 | 179912.888000 | 0.040037 | 0.434866 | 0.400000 | 20 | 0.006743 | 591 |
| B | Y | 3805 | 160 | 208482.456000 | 0.046395 | 0.405236 | 0.388889 | 79 | 0.020762 | 576 |
| B | Z | 5389 | 166 | 284103.626000 | 0.063223 | 0.424734 | 0.400000 | 629 | 0.116719 | 1102 |
| C | X | 1139 | 277 | 63004.596000 | 0.014021 | 0.428768 | 0.400000 | 8 | 0.007024 | 215 |
| C | Y | 1315 | 368 | 65042.831000 | 0.014474 | 0.402577 | 0.377778 | 26 | 0.019772 | 224 |
| C | Z | 2007 | 439 | 96635.130000 | 0.021505 | 0.377307 | 0.366667 | 112 | 0.055805 | 300 |

## Perfis operacionais prioritários

Os grupos abaixo se sobrepõem: A_CENSOR_FLAG pode estar nos demais perfis A. Não somar suas participações como uma partição.

| profile | n_series | n_products | normalized_sales_total | normalized_sales_share | median_stockout_rate | median_weekly_cv | median_pattern_correlation | censoring_risk_count |
|---|---|---|---|---|---|---|---|---|
| AX_HIGH | 3127 | 77 | 446119.746000 | 0.099278 | 0.611111 | 0.193588 | 0.691623 | 113 |
| AY_HIGH | 2692 | 97 | 392208.501000 | 0.087280 | 0.611111 | 0.278681 | 0.371634 | 278 |
| AZ_HIGH | 3779 | 94 | 557653.607000 | 0.124098 | 0.622222 | 0.446334 | 0.052583 | 1386 |
| A_CENSOR_FLAG | 1777 | 73 | 182998.765000 | 0.040724 | 0.633333 | 0.500504 | 0.163954 | 1777 |
| CZ_LOW | 911 | 280 | 46946.544000 | 0.010447 | 0.277778 | 0.419475 | -0.023327 | 0 |

- **AX_HIGH:** produto relevante e série relativamente estável, mas alta frequência de ruptura. Investigar disponibilidade antes de interpretar a venda como demanda livre de restrição.
- **AY_HIGH:** produto relevante com comportamento intermediário e exposição elevada. Preservar os dois diagnósticos ao avaliar métodos futuramente.
- **AZ_HIGH:** relevância combinada a instabilidade observada e ruptura. Requer análise cuidadosa de censura e incerteza; não prova erro de forecast elevado.
- **A_CENSOR_FLAG:** grupo relevante especialmente exposto à possível censura; prioridade de investigação da qualidade do alvo, sem quantificar venda perdida.
- **CZ_LOW:** contribuição global menor e instabilidade apesar de exposição relativamente baixa. A baixa relevância não torna a série automaticamente simples de prever.

## Exemplos reproduzíveis

Maiores valores da métrica indicada dentro do filtro, com desempate por store_id e product_id. A_CENSOR_HIGH_STOCKOUT filtra A+flag e ordena por ruptura, depois zeros e identificadores; não é um score de risco. CX/CZ próximos da mediana minimizam a distância absoluta do CV semanal à mediana da combinação, sem reivindicar representatividade em todos os eixos. Regras podem selecionar a mesma série.

| selection_rule | store_id | product_id | abc_class | xyz_class | stockout_exposure | censoring_risk_flag | total_demand | weekly_coefficient_of_variation | weekly_pattern_half_correlation | stockout_rate | zero_ratio |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AX_MAX_SALES | 737 | 267 | A | X | MEDIUM | False | 1558.700000 | 0.231194 | 0.535745 | 0.455556 | 0.000000 |
| AX_MAX_STOCKOUT | 365 | 596 | A | X | HIGH | False | 55.400000 | 0.222774 | 0.609004 | 0.977778 | 0.011111 |
| AZ_MAX_STOCKOUT | 11 | 267 | A | Z | HIGH | False | 1610.200000 | 0.587801 | 0.929476 | 1.000000 | 0.000000 |
| A_CENSOR_HIGH_STOCKOUT | 63 | 267 | A | Z | HIGH | True | 1439.300000 | 0.651526 | 0.760407 | 0.988889 | 0.155556 |
| CX_MEDIAN_WEEKLY_CV | 52 | 752 | C | X | HIGH | False | 36.940000 | 0.193930 | 0.593194 | 1.000000 | 0.000000 |
| CZ_MEDIAN_WEEKLY_CV | 436 | 586 | C | Z | LOW | False | 47.900000 | 0.410265 | -0.354666 | 0.166667 | 0.055556 |

## Limites e uso temporal

**No backtesting futuro, ABC, XYZ, thresholds e quantis não poderão ser reaproveitados retrospectivamente.** Recalcular somente com dados disponíveis até cada origem quando forem features ou critérios de decisão temporal. O pipeline recusa um mart da Fase 2 cujo corte seja diferente do solicitado.

XYZ usa venda observada: separar disponibilidade da regra não remove seu efeito indireto nos valores de venda. Promoção e mudança de nível também podem afetar as métricas. O corte é curto, com 12 semanas completas; não há sazonalidade anual validada. Os limites por quantis são relativos e não universais. Nenhuma política de reposição foi definida.

## Rastreabilidade e reprodução

Fonte train SHA-256: `6706832db892bbae4969c19d87e07975d2543d2ba7d7d4756360654785de5a3d`; revisão `08c1fab7f9257bc73679d415d65d644165d351d4`. Perfil da Fase 2 SHA-256: `2f8a9da452f6d00f762d0c736eb343c8ae45303919ae2cc44073202f2bce077e`.

Runtime: python 3.12.0, pandas 3.0.6, numpy 2.5.3, duckdb 1.5.6, pyarrow 25.0.1.

| name | path | rows | sha256 |
|---|---|---|---|
| product_abc | data/processed/mart_product_abc.parquet | 865 | 36563615b409c7b08e67acb15790282c9fc96fccbfc3e3c5050fed4fa155aaf3 |
| series_xyz | data/processed/mart_series_xyz.parquet | 50000 | ed7ef98dec8eb1fc974d9d26e5d09467ad1ac0af0caaf39c8ad53c724d90cda0 |
| stockout_exposure | data/processed/mart_stockout_exposure.parquet | 50000 | 1e74f775bf1d81cc494f5ccefe23f4c7a04ff14822737adf62c2efafa6cc2cec |
| operational_profile | data/processed/mart_operational_profile.parquet | 50000 | c5df94df59df6420f58b4997a5259ed002c14d08df4cb9d45a0c9b9c7c3ee059 |
| correlations | data/outputs/segmentation/metric_correlations.parquet | 98 | c932ce2acec116e826212ad977a42cc94b706c8dbaf29fb4046f37154c39e1f8 |
| candidate_comparison | data/outputs/segmentation/xyz_candidates.parquet | 12 | de04ec552291dced71ac9d6c3ddd8d4567563a0787a9b1c7a2a28845eb151058 |
| xyz_class_profiles | data/outputs/segmentation/xyz_class_profiles.parquet | 24 | ddab81708655a6ee704a1da1ed87f625006eaee97a9dc75a329db0b035b71435 |
| abc_xyz_matrix | data/outputs/segmentation/abc_xyz_matrix.parquet | 9 | a48a16b632b6f932080896867e6e9340b8fddc8a567abbd65c1181abbc001952 |
| exposure_cube | data/outputs/segmentation/abc_xyz_exposure.parquet | 27 | 35b1996848fe1b3bbbe392d846ac35c4dd5899078e7772ffaf7eb0e9a12a84d1 |
| example_profiles | data/outputs/segmentation/example_profiles.parquet | 6 | 15ce504845cfd56e105a1ebc2a3abdfbde598f40698da856c0bee9bb19dabfa8 |
| example_series | data/outputs/segmentation/example_series.parquet | 540 | c7dbd42fd98242dcfcbd45351082c63dbd48743325752369ea68e0900cfe80b3 |

Resumo: `data/outputs/segmentation/summary.json`. Notebook: `notebooks/02_segmentation.ipynb`, com nove figuras baseadas nos outputs. Reprodução por hash é garantida no runtime registrado, sem timestamps ou caminhos absolutos nos artefatos tabulares. Regras, fórmulas e comandos em `docs/methodology.md`.
