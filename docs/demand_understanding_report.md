# Fase 2 — Entendimento da venda observada e disponibilidade

Relatório gerado por `python scripts/build_demand_profile.py`. Fonte exclusiva: `data/raw/train.parquet`. Eval permanece reservado; nenhum dado dele entra neste relatório.

Janela: **2024-03-28 a 2024-06-25**; **4,500,000 registros**, **50,000 séries**, 898 lojas e 865 produtos.

Os nomes `*_demand` atendem ao contrato do mart, mas medem **venda observada normalizada**. Não são demanda latente, quantidade física, receita ou margem. Não há imputação, segmentação ou previsão.

## Distribuições por série

Média diária global: 0.998591; mediana diária: 0.700000; soma normalizada: 4493660.787000. As distribuições abaixo atribuem peso igual a cada série.

| métrica | válidas | indefinidas | mín | p25 | p50 | p75 | p95 | máx |
|---|---|---|---|---|---|---|---|---|
| mean_demand | 50000 | 0 | 0.222000 | 0.494222 | 0.657778 | 1.054444 | 2.651167 | 19.074444 |
| median_demand | 50000 | 0 | 0.000000 | 0.500000 | 0.600000 | 1.000000 | 2.500000 | 22.750000 |
| total_demand | 50000 | 0 | 19.980000 | 44.480000 | 59.200000 | 94.900000 | 238.605000 | 1716.700000 |
| coefficient_of_variation | 50000 | 0 | 0.164274 | 0.430846 | 0.514077 | 0.641412 | 0.953939 | 3.007781 |
| zero_ratio | 50000 | 0 | 0.000000 | 0.000000 | 0.022222 | 0.055556 | 0.200000 | 0.722222 |
| adi | 50000 | 0 | 1.000000 | 1.000000 | 1.022727 | 1.058824 | 1.250000 | 3.600000 |
| positive_demand_cv_squared | 50000 | 0 | 0.026986 | 0.167208 | 0.227708 | 0.328408 | 0.645904 | 4.964548 |
| stockout_rate | 50000 | 0 | 0.055556 | 0.344444 | 0.422222 | 0.522222 | 0.733333 | 1.000000 |
| total_stockout_hours | 50000 | 0 | 56 | 214.000000 | 254.500000 | 316.000000 | 526.000000 | 1397 |
| mean_stockout_hours_when_affected | 50000 | 0 | 2.978723 | 6.058824 | 6.920000 | 8.050000 | 11.470588 | 15.821429 |
| maximum_consecutive_stockout_days | 50000 | 0 | 1 | 5.000000 | 7.000000 | 10.000000 | 19.000000 | 90 |
| autocorrelation_lag7 | 50000 | 0 | -0.426590 | 0.082071 | 0.202459 | 0.345055 | 0.590677 | 0.936916 |
| weekly_coefficient_of_variation | 50000 | 0 | 0.025307 | 0.197197 | 0.265992 | 0.381016 | 0.603932 | 1.916415 |
| weekly_pattern_half_correlation | 49996 | 4 | -0.986097 | 0.058267 | 0.394744 | 0.659168 | 0.879955 | 0.994399 |
| weekly_pattern_half_mae | 49996 | 4 | 0.013813 | 0.144934 | 0.193902 | 0.259185 | 0.425607 | 1.537975 |
| weekend_weekday_relative_difference | 50000 | 0 | -0.851899 | 0.134315 | 0.248922 | 0.382593 | 0.690862 | 3.475524 |
| activity_rate | 50000 | 0 | 0.000000 | 0.075000 | 0.311111 | 0.655556 | 0.966667 | 1.000000 |
| activity_stockout_rate_difference | 40460 | 9540 | -0.888889 | -0.030364 | 0.095238 | 0.226667 | 0.465116 | 0.918605 |

CV usa desvio-padrão amostral; média ≤ 1e-9 gera valor indefinido. Essa tolerância é numérica, não uma regra de XYZ. Valores indefinidos não são preenchidos com zero.

## Concentração

Curvas ordenadas por soma da venda normalizada, com desempate por identificadores. As frações top 1%, 5% e 20% usam arredondamento para cima no número de entidades. A contagem até 80%/95% inclui a entidade que cruza a participação. Não são classes ABC. Contribuições agregadas também refletem o número de combinações loja-produto presentes; o painel não contém todo produto em toda loja.

| level | n_entities | top_1pct_share | top_5pct_share | top_20pct_share | entities_for_80pct | fraction_for_80pct | entities_for_95pct | fraction_for_95pct |
|---|---|---|---|---|---|---|---|---|
| product | 865 | 0.268428 | 0.560940 | 0.869997 | 122 | 0.141040 | 289 | 0.334104 |
| series | 50000 | 0.089082 | 0.229295 | 0.485376 | 29229 | 0.584580 | 44024 | 0.880480 |
| store | 898 | 0.032342 | 0.130784 | 0.397868 | 514 | 0.572383 | 731 | 0.814031 |

## Zeros e intermitência

Zeros: **200,760 registros (4.46%)**. 35,595 séries têm algum zero; 14,405 não têm zeros. **74 séries (0.15%)** têm zeros na maioria dos dias (>50%): essa é uma contagem descritiva literal, não uma classe de intermitência. Séries inteiramente zeradas: 0; médias próximas de zero: 0.

ADI = número de dias observados / número de dias com venda positiva; sem dias positivos, indefinido. É a medida agregada de intervalo médio usada aqui, não a média dos intervalos internos entre ocorrências. Como todas as séries têm o mesmo número de dias, ADI = 1/(1−zero_ratio) e não acrescenta informação independente aos zeros. CV² dos valores positivos descreve a variação de tamanho das ocorrências.

Dos zeros, 153,816 coincidem com ruptura em [06h,22h) e 46,944 não coincidem nessa janela. Um zero observado não demonstra ausência de demanda, mesmo sem ruptura na janela operacional.

A distribuição completa por número de dias zerados está em `summary.json` (`zero_days_distribution`); o notebook mostra sua distribuição acumulada, sem cortes de segmentação.

## Padrão semanal

Semanas completas por série: 12–12. Semanas são segunda a domingo; os trechos incompletos nas pontas não entram em totais/CV semanais nem no teste descritivo de estabilidade. O perfil por weekday usa todos os dias disponíveis e médias por observação, evitando confundir diferenças de contagem com nível de venda.

| weekday | n_rows | mean_demand | stockout_rate | activity_rate | relative_series_quantiles |
|---|---|---|---|---|---|
| 1 | 650000 | 0.942580 | 0.456643 | 0.374600 | 0.866785, 0.952269, 1.036107 |
| 2 | 650000 | 0.961985 | 0.472257 | 0.362855 | 0.878990, 0.971743, 1.067556 |
| 3 | 600000 | 0.906884 | 0.446678 | 0.386200 | 0.822554, 0.907738, 0.990875 |
| 4 | 650000 | 0.866036 | 0.417312 | 0.378938 | 0.795889, 0.872924, 0.948764 |
| 5 | 650000 | 0.926775 | 0.391869 | 0.350909 | 0.847429, 0.924877, 1.003591 |
| 6 | 650000 | 1.178130 | 0.435149 | 0.401183 | 1.049610, 1.150132, 1.258154 |
| 7 | 650000 | 1.200694 | 0.479075 | 0.394857 | 1.084560, 1.180274, 1.281475 |

Weekday: 1 = segunda e 7 = domingo. Os três quantis relativos são p25/p50/p75 da média de cada weekday dividida pela média diária da própria série.

Correlação lag 7 positiva: 44,379 séries; correlação positiva entre perfis das duas metades: 39,143; venda média maior no fim de semana: 46,770.

Lag 7 é a correlação de Pearson dos pares (venda em t, venda em t−7), exigindo pelo menos três pares e desvio-padrão >1e-9 nos dois vetores. Não é a ACF com denominador global. Na estabilidade, cada semana completa é dividida por sua média; comparam-se os sete valores médios das metades cronológicas (seis semanas em cada metade na janela completa). Exigem-se pelo menos duas semanas de média positiva em cada metade. Correlação fica indefinida para perfil constante; MAE de forma continua válida. Nenhuma dessas medidas é um teste de significância.

As diferenças entre séries e a estabilidade imperfeita exigem avaliação temporal posterior. Tendência, promoções e disponibilidade podem influenciar lag 7. O padrão agregado não deve ser imposto a cada série. A janela não permite afirmar sazonalidade anual.

## Ruptura × venda observada

Ruptura em **44.27%** dos registros, definida como `stock_hour6_22_cnt > 0` em [06h,22h). Zero fora dessa definição não significa disponibilidade durante 24 horas.

| stockout | n_rows | mean_demand | median_demand | zero_ratio |
|---|---|---|---|---|
| False | 2507994 | 0.974518 | 0.680000 | 0.018718 |
| True | 1992006 | 1.028900 | 0.700000 | 0.077217 |

Dentro das mesmas séries, 49,912 têm dias com e sem ruptura; em 26,497, a média é maior nos dias com ruptura, e em 23,405, menor. Diferença mediana (com − sem): 0.013889; média das diferenças: -0.127287.

A comparação dentro da série reduz diferenças fixas de nível entre produtos/lojas, mas não controla demanda latente, promoção, calendário ou duração da ruptura. Não identifica efeito causal nem vendas perdidas: demanda elevada também pode anteceder ruptura.

### Grupos descritivos por frequência de ruptura

Cortes nos quartis empíricos da taxa de ruptura; empates permanecem no mesmo grupo, portanto os tamanhos podem diferir. Não são segmentos XYZ.

| empirical_quartile | n_series | min_stockout_rate | max_stockout_rate | mean_zero_ratio | median_cv | fraction_zeros_with_stockout | median_within_series_difference |
|---|---|---|---|---|---|---|---|
| 1 | 13591 | 0.055556 | 0.344444 | 0.058225 | 0.546386 | 0.659562 | -0.024615 |
| 2 | 12419 | 0.355556 | 0.422222 | 0.035643 | 0.513317 | 0.714752 | 0.040182 |
| 3 | 12337 | 0.433333 | 0.522222 | 0.033658 | 0.498690 | 0.790961 | 0.040119 |
| 4 | 11653 | 0.533333 | 1.000000 | 0.049897 | 0.481280 | 0.932696 | -0.018701 |

A interseção de taxa de ruptura ≥ p75 e proporção de zeros ≥ p75 contém **2,651 séries**. Nela, a taxa média de ruptura é 0.658624, a proporção média de zeros é 0.194224 e a fração de zeros coincidentes com ruptura é 0.962775. Esse cruzamento identifica observações especialmente expostas à possível censura, sem estimar demanda perdida ou atribuir uma classe. Os limites são os quantis de train descritos adiante.

### Duração da ruptura

| stockout_hours | n_rows | mean_demand | zero_ratio |
|---|---|---|---|
| 0 | 2507994 | 0.974518 | 0.018718 |
| 1 | 152309 | 1.350315 | 0.008489 |
| 2 | 120358 | 1.482659 | 0.002127 |
| 3 | 142575 | 1.430719 | 0.000905 |
| 4 | 199629 | 1.339614 | 0.000681 |
| 5 | 242299 | 1.243058 | 0.000735 |
| 6 | 203376 | 1.151231 | 0.000865 |
| 7 | 142210 | 1.084964 | 0.001652 |
| 8 | 111818 | 1.038143 | 0.002826 |
| 9 | 102507 | 0.959925 | 0.003405 |
| 10 | 106773 | 0.880613 | 0.002295 |
| 11 | 108853 | 0.769337 | 0.002866 |
| 12 | 84517 | 0.655909 | 0.005585 |
| 13 | 54059 | 0.591949 | 0.008380 |
| 14 | 26778 | 0.462447 | 0.021996 |
| 15 | 12154 | 0.328605 | 0.051999 |
| 16 | 181791 | 0.046020 | 0.814369 |

Nos 181,791 registros com as 16 horas da janela em ruptura, 81.44% apresentam venda diária zero. A média diária é 0.046020; venda positiva ainda pode ocorrer fora da janela. Esse é um sinal direto de exposição à possível censura, sem permitir quantificar a demanda latente.

A relação com weekday está na tabela semanal; a relação com atividade está abaixo. As associações são descritivas e podem refletir seleção dos dias afetados.

## Promoções e discount

Atividade promocional em **37.84%** dos registros.

| activity_flag | n_rows | mean_demand | median_demand | stockout_rate |
|---|---|---|---|---|
| 0 | 2797107 | 0.989662 | 0.600000 | 0.429100 |
| 1 | 1702893 | 1.013258 | 0.700000 | 0.464955 |

40,460 séries têm dias com e sem atividade; 33,456 têm média maior nos dias de atividade. Diferença mediana dentro da série: 0.203704; média das diferenças: 0.267621. Não representam uplift causal. Dentro das mesmas séries, 28,030 têm taxa de ruptura maior nos dias de atividade; diferença mediana de taxa: 0.095238.

| minimum | maximum | zero_rows | discount_rows | equal_one_rows | above_one_rows | quantiles |
|---|---|---|---|---|---|---|
| 0.000000 | 1.088000 | 16039 | 2302806 | 2181121 | 34 | 0.504000, 0.666000, 0.851000, 0.989000, 1.000000, 1.000000, 1.000000 |

`discount_days` conta estritamente 0 < discount < 1. Zero e >1 são mantidos em contagens separadas; `mean_discount` preserva todos os valores. Atividade e fator de desconto são dimensões diferentes, sem equivalência presumida.

| activity_flag | discount_group | n_rows |
|---|---|---|
| 0 | above_one | 34 |
| 0 | between_zero_one | 638412 |
| 0 | one | 2142743 |
| 0 | zero | 15918 |
| 1 | between_zero_one | 1664394 |
| 1 | one | 38378 |
| 1 | zero | 121 |

### Investigação de discount > 1

Train contém **34 ocorrências**. A contagem foi apurada diretamente em train, sem consultar eval. A referência histórica da Fase 1 era 34 ocorrências no conjunto combinado; portanto todas as 34 já podem ser investigadas aqui.

| product_id | n_rows | n_stores | min_discount | max_discount | above_one_rows | zero_rows | activity_rows |
|---|---|---|---|---|---|---|---|
| 37 | 7650 | 85 | 0.563000 | 1.088000 | 34 | 0 | 1060 |

Ocorrências completas (valores originais):

| product_id | store_id | dt | discount | activity_flag | sale_amount | stock_hour6_22_cnt |
|---|---|---|---|---|---|---|
| 37 | 293 | 2024-04-03 | 1.042000 | 0 | 0.500000 | 0 |
| 37 | 293 | 2024-04-10 | 1.088000 | 0 | 0.400000 | 0 |
| 37 | 293 | 2024-04-21 | 1.019000 | 0 | 0.800000 | 0 |
| 37 | 293 | 2024-04-25 | 1.088000 | 0 | 0.400000 | 0 |
| 37 | 293 | 2024-05-21 | 1.088000 | 0 | 0.400000 | 10 |
| 37 | 326 | 2024-04-28 | 1.088000 | 0 | 0.600000 | 0 |
| 37 | 326 | 2024-05-03 | 1.059000 | 0 | 1.000000 | 0 |
| 37 | 326 | 2024-05-04 | 1.059000 | 0 | 0.600000 | 4 |
| 37 | 326 | 2024-05-05 | 1.088000 | 0 | 0.400000 | 7 |
| 37 | 326 | 2024-05-07 | 1.088000 | 0 | 0.400000 | 11 |
| 37 | 326 | 2024-05-12 | 1.088000 | 0 | 0.600000 | 0 |
| 37 | 529 | 2024-04-13 | 1.088000 | 0 | 0.400000 | 0 |
| 37 | 529 | 2024-04-17 | 1.059000 | 0 | 0.700000 | 4 |
| 37 | 529 | 2024-05-12 | 1.033000 | 0 | 0.700000 | 8 |
| 37 | 529 | 2024-05-18 | 1.088000 | 0 | 0.400000 | 0 |
| 37 | 529 | 2024-05-20 | 1.088000 | 0 | 0.700000 | 0 |
| 37 | 529 | 2024-05-23 | 1.088000 | 0 | 0.500000 | 0 |
| 37 | 608 | 2024-04-04 | 1.088000 | 0 | 0.400000 | 0 |
| 37 | 608 | 2024-04-08 | 1.088000 | 0 | 0.600000 | 4 |
| 37 | 608 | 2024-04-16 | 1.044000 | 0 | 0.800000 | 5 |
| 37 | 608 | 2024-04-20 | 1.050000 | 0 | 0.700000 | 0 |
| 37 | 608 | 2024-04-25 | 1.043000 | 0 | 0.500000 | 0 |
| 37 | 608 | 2024-04-26 | 1.088000 | 0 | 0.400000 | 0 |
| 37 | 608 | 2024-04-29 | 1.088000 | 0 | 0.600000 | 0 |
| 37 | 608 | 2024-05-02 | 1.065000 | 0 | 1.400000 | 13 |
| 37 | 608 | 2024-05-18 | 1.070000 | 0 | 0.500000 | 0 |
| 37 | 608 | 2024-05-19 | 1.070000 | 0 | 0.500000 | 12 |
| 37 | 611 | 2024-05-23 | 1.050000 | 0 | 0.700000 | 0 |
| 37 | 611 | 2024-05-24 | 1.020000 | 0 | 2.500000 | 0 |
| 37 | 614 | 2024-04-08 | 1.088000 | 0 | 0.400000 | 3 |
| 37 | 614 | 2024-04-12 | 1.070000 | 0 | 0.500000 | 3 |
| 37 | 614 | 2024-04-18 | 1.088000 | 0 | 0.400000 | 4 |
| 37 | 614 | 2024-04-26 | 1.059000 | 0 | 0.600000 | 4 |
| 37 | 614 | 2024-05-04 | 1.088000 | 0 | 0.600000 | 0 |

A concentração por produto e a repetição de fatores sugerem um padrão específico de cadastro/cálculo do fator, a investigar com o publisher. Os dados não permitem distinguir erro de preço de referência, arredondamento ou outra convenção. Não há preço para validar essas hipóteses. Os valores foram preservados; não se conclui que sejam erro nem promoção.

## Exemplos por regra reproduzível

Alta/baixa venda e ruptura usam p75/p25 de train. Dentro dos filtros, escolhe-se a maior média (alta venda) ou menor média (baixa venda). Volatilidade/zeros usam o máximo válido. Desempate sempre por store_id e product_id; regras podem selecionar a mesma série.

| demand_q25 | demand_q75 | stockout_q25 | stockout_q75 | zero_q75 |
|---|---|---|---|---|
| 0.494222 | 1.054444 | 0.344444 | 0.522222 | 0.055556 |

| rule | store_id | product_id | mean_demand | coefficient_of_variation | zero_ratio | stockout_rate | adi |
|---|---|---|---|---|---|---|---|
| alta_venda_baixa_ruptura | 806 | 756 | 9.013333 | 0.444348 | 0.055556 | 0.200000 | 1.058824 |
| alta_venda_alta_ruptura | 50 | 267 | 19.074444 | 0.340508 | 0.000000 | 0.644444 | 1.000000 |
| baixa_venda_baixa_ruptura | 343 | 8 | 0.344444 | 1.140813 | 0.211111 | 0.311111 | 1.267606 |
| maior_volatilidade | 188 | 813 | 0.450000 | 3.007781 | 0.433333 | 0.322222 | 1.764706 |
| maior_proporcao_zeros | 230 | 757 | 0.363333 | 2.126501 | 0.722222 | 0.933333 | 3.600000 |

## Implicações e limites para as próximas fases

- A concentração deve orientar uma futura ABC por contribuição de venda/demanda normalizada, sem interpretação financeira. A distribuição empírica não determina sozinha uma regra 80/15/5.
- XYZ deve considerar CV, zeros/ADI, estabilidade semanal e exposição à ruptura. CV alto pode refletir censura ou promoção; CV baixo não comprova previsibilidade.
- ADI e zero_ratio são redundantes nesta janela completa; não devem contar duas vezes o mesmo sinal.
- Os perfis usam todo train e são descritivos ao corte final. Em backtesting futuro, refazer os perfis e os quantis em cada origem; não reutilizar o mart final em cortes anteriores.
- Não há reconstrução de demanda, decisão de threshold, causalidade, modelo, receita, estoque físico, política de reposição nem avaliação de holdout nesta fase.

## Artefatos e rastreabilidade

Fonte: `data/raw/train.parquet`; SHA-256 `6706832db892bbae4969c19d87e07975d2543d2ba7d7d4756360654785de5a3d`; revisão `08c1fab7f9257bc73679d415d65d644165d351d4`.

Runtime de geração: duckdb 1.5.6, pyarrow 25.0.1.

| name | path | rows | sha256 |
|---|---|---|---|
| profile | data/processed/mart_demand_profile.parquet | 50000 | 2f8a9da452f6d00f762d0c736eb343c8ae45303919ae2cc44073202f2bce077e |
| weekly | data/outputs/demand_understanding/series_weekly.parquet | 600000 | c87df47dfb5ec633282d7581c0ee3768ce560a2c656c47a2df7bfb6c9073f5f4 |
| weekday | data/outputs/demand_understanding/series_weekday.parquet | 350000 | 58e6c79751cfdec5947bc5941e12a7ba7f952ec32f6695cf982cbb4910b2c978 |
| concentration | data/outputs/demand_understanding/concentration.parquet | 51763 | 8009f58bfb1c5578c3e2cd884e42f928fdce62ded43ccb6d2f988b94576c0e83 |
| discount_anomalies | data/outputs/demand_understanding/discount_above_one.parquet | 34 | 1705f2197c8224aa1cff8d427164fea0bc0588e728121dd2a0865280b8c6774a |
| examples | data/outputs/demand_understanding/example_series.parquet | 450 | a83af9d0ba6056ededa7e532a04a9f2aa5d463a361ea281438fee5feafb6aad7 |

Resumo estruturado: `data/outputs/demand_understanding/summary.json`. Notebook: `notebooks/01_data_understanding.ipynb`, com nove figuras; consome apenas outputs. Metodologia e definições completas em `docs/methodology.md`. Reprodução bit a bit é verificada no runtime local registrado; outra versão de engine/formato pode mudar bytes.
