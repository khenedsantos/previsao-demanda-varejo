# Qualidade dos dados — Fase 1

Estado: **passed**. Relatório reproduzível por `python scripts/validate_raw.py`. Nenhuma análise preditiva executada.

## Fonte e rastreabilidade

[Dingdong-Inc/FreshRetailNet-50K](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K), publisher Dingdong-Inc, via Hugging Face. Versão 1.0; licença [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).

Revisão congelada: `08c1fab7f9257bc73679d415d65d644165d351d4`. Aquisição: 2026-10-07. Data de lançamento transcrita da fonte: `05/08/2025`; interpretação de dia/mês não confirmada.

| Arquivo | Bytes | Linhas | SHA-256 |
|---|---|---|---|
| train.parquet | 106436287 | 4500000 | `6706832db892bbae4969c19d87e07975d2543d2ba7d7d4756360654785de5a3d` |
| eval.parquet | 8440124 | 350000 | `1b118840664280c6b88bffc84c80ee1f54c05d911e354b7599e5da10995e960e` |

Os arquivos oficiais são mantidos sem alterações em data/raw, com o nome original. Hash, tamanho, schema físico e contagem são verificados antes de qualquer profiling. Nenhum dado é versionado no Git.

## Schema documentado × observado

Os dois arquivos têm 19 colunas na mesma ordem. Nullable é a permissão no schema Parquet, não uma contagem de nulos. Todos os campos e elementos das listas permitem nulos no schema.

| Coluna | Documentado | Arrow observado | Físico Parquet | Nullable | Train/eval |
|---|---|---|---|---|---|
| `city_id` | `int64` | `int64` | INT64 | True | presente / presente |
| `store_id` | `int64` | `int64` | INT64 | True | presente / presente |
| `management_group_id` | `int64` | `int64` | INT64 | True | presente / presente |
| `first_category_id` | `int64` | `int64` | INT64 | True | presente / presente |
| `second_category_id` | `int64` | `int64` | INT64 | True | presente / presente |
| `third_category_id` | `int64` | `int64` | INT64 | True | presente / presente |
| `product_id` | `int64` | `int64` | INT64 | True | presente / presente |
| `dt` | `string` | `string` | BYTE_ARRAY | True | presente / presente |
| `sale_amount` | `float64` | `double` | DOUBLE | True | presente / presente |
| `hours_sale` | `list<float64>` | `list<element: double>` | DOUBLE | True | presente / presente |
| `stock_hour6_22_cnt` | `int32` | `int32` | INT32 | True | presente / presente |
| `hours_stock_status` | `list<int32>` | `list<element: int64>` | INT64 | True | presente / presente |
| `discount` | `float64` | `double` | DOUBLE | True | presente / presente |
| `holiday_flag` | `int32` | `int32` | INT32 | True | presente / presente |
| `activity_flag` | `int32` | `int32` | INT32 | True | presente / presente |
| `precpt` | `float64` | `double` | DOUBLE | True | presente / presente |
| `avg_temperature` | `float64` | `double` | DOUBLE | True | presente / presente |
| `avg_humidity` | `float64` | `double` | DOUBLE | True | presente / presente |
| `avg_wind_level` | `float64` | `double` | DOUBLE | True | presente / presente |

Divergência compreendida: hours_stock_status é list<int64>, enquanto a ficha declara Sequence(int32). Valores e tipo observado foram preservados. A identidade congelada impede aceitar mudanças futuras silenciosamente.

## Volume, período e grão

| Conjunto | Linhas | Início | Fim | Dias | Cidades | Lojas | Produtos | Séries |
|---|---|---|---|---|---|---|---|---|
| all | 4850000 | 2024-03-28 | 2024-07-02 | 97 | 18 | 898 | 865 | 50000 |
| eval | 350000 | 2024-06-26 | 2024-07-02 | 7 | 18 | 898 | 865 | 50000 |
| train | 4500000 | 2024-03-28 | 2024-06-25 | 90 | 18 | 898 | 865 | 50000 |

Grão confirmado: uma linha por data, loja e produto; chave (dt, store_id, product_id).

| Conjunto | Chaves distintas | Duplicatas excedentes | Datas inválidas | Chaves nulas |
|---|---|---|---|---|
| all | 4850000 | 0 | 0 | 0 |
| eval | 350000 | 0 | 0 | 0 |
| train | 4500000 | 0 | 0 | 0 |

Duplicatas não são removidas automaticamente. Exemplos, quando existentes, ficam no JSON.

## Nulos

| Coluna | Train | Eval | Total |
|---|---|---|---|
| city_id | 0 | 0 | 0 |
| store_id | 0 | 0 | 0 |
| management_group_id | 0 | 0 | 0 |
| first_category_id | 0 | 0 | 0 |
| second_category_id | 0 | 0 | 0 |
| third_category_id | 0 | 0 | 0 |
| product_id | 0 | 0 | 0 |
| dt | 0 | 0 | 0 |
| sale_amount | 0 | 0 | 0 |
| hours_sale | 0 | 0 | 0 |
| stock_hour6_22_cnt | 0 | 0 | 0 |
| hours_stock_status | 0 | 0 | 0 |
| discount | 0 | 0 | 0 |
| holiday_flag | 0 | 0 | 0 |
| activity_flag | 0 | 0 | 0 |
| precpt | 0 | 0 | 0 |
| avg_temperature | 0 | 0 | 0 |
| avg_humidity | 0 | 0 | 0 |
| avg_wind_level | 0 | 0 | 0 |

## Cobertura temporal

Por série: missing_days = dias entre primeira/última data (inclusive) menos datas distintas; coverage_ratio = datas distintas / dias calendários. Não se usa contagem de linhas para esconder lacunas com duplicatas.

| Conjunto | Séries | Mín. obs. | Mediana | Média | Máx. obs. | Completas | Com lacunas |
|---|---|---|---|---|---|---|---|
| all | 50000 | 97 | 97 | 97 | 97 | 50000 | 0 |
| eval | 50000 | 7 | 7 | 7 | 7 | 50000 | 0 |
| train | 50000 | 90 | 90 | 90 | 90 | 50000 | 0 |

| Conjunto | Observações/série | Dias calendário | Dias ausentes | Nº séries |
|---|---|---|---|---|
| all | 97 | 97 | 0 | 50000 |
| eval | 7 | 7 | 0 | 50000 |
| train | 90 | 90 | 0 | 50000 |

Detalhe por store_id + product_id e conjunto: `data/outputs/series_coverage.parquet` (inclui first_date, last_date, n_observations, n_unique_dates, n_calendar_days, missing_days e coverage_ratio).

## Relação train/eval

| Entidade | Compartilhadas | Somente train | Somente eval |
|---|---|---|---|
| dates | 0 | 90 | 7 |
| cities | 18 | 0 | 0 |
| stores | 898 | 0 | 0 |
| products | 865 | 0 | 0 |
| series | 50000 | 0 | 0 |
| daily_keys | 0 | 4500000 | 350000 |

Os autores usam os 90 dias de train como histórico e os sete dias posteriores de eval para avaliar previsão. Seu baseline oficial pontua dias sem ruptura (stock_hour6_22_cnt=0). Nesta fase, eval foi usado somente para auditoria de estrutura/qualidade; não houve tuning ou seleção de modelo.

Decisão: preservar a identificação original de split no staging; tratar eval como bloco temporal futuro reservado. O desenho do backtesting dentro de train e da avaliação final será definido em etapa posterior. Não considerar o staging combinado uma autorização para treinar com eval.

Referência do protocolo: [baseline oficial](https://github.com/Dingdong-Inc/frn-50k-baseline/blob/main/demand_forecasting/SSA/ssa_forecasting.py).

## Domínios e extremos

Quantis exatos; nenhum corte, imputação ou remoção de extremos. A tabela resume o conjunto combinado; estatísticas de train/eval, todas as frequências e os valores distintos de discount estão no JSON.

| Variável | Distintos | Nulos | Negativos | Zeros | Mínimo | P01 | Mediana | P99 | Máximo |
|---|---|---|---|---|---|---|---|---|---|
| sale_amount | 1616 | 0 | 0 | 215323 | 0 | 0 | 0.7 | 5.9 | 49.9 |
| discount | 2773 | 0 | 0 | 17339 | 0 | 0.505 | 0.991 | 1 | 1.088 |
| precpt | 43633 | 0 | 0 | 8353 | 0 | 0.2792 | 2.424 | 16.2998 | 42.5 |
| avg_temperature | 1712 | 0 | 0 | 0 | 12.06 | 15.45 | 22.84 | 30.37 | 32.29 |
| avg_humidity | 4950 | 0 | 0 | 0 | 27.35 | 35.42 | 76.6 | 87.19 | 100 |
| avg_wind_level | 249 | 0 | 0 | 0 | 0.97 | 1.12 | 1.62 | 2.79 | 3.85 |

sale_amount e hours_sale representam vendas normalizadas por coeficiente global segundo a fonte. Não equivalem, de forma comprovada, a reais, unidades ou quilogramas. Unidades/escala meteorológicas não estão especificadas na ficha; extremos numéricos não foram rotulados como erros com base em limites arbitrários. Negativos e valores não finitos são medidos no JSON.

| Conjunto | Discount = 0 | Discount > 1 | Tratamento |
|---|---|---|---|
| all | 17339 | 34 | preservar; significado dos extremos não confirmado pela fonte |
| train | 16039 | 34 | preservar; significado dos extremos não confirmado pela fonte |
| eval | 1300 | 0 | preservar; significado dos extremos não confirmado pela fonte |

### activity_flag

| Valor | Frequência total |
|---|---|
| 0 | 3031715 |
| 1 | 1818285 |

### holiday_flag

| Valor | Frequência total |
|---|---|
| 0 | 3200000 |
| 1 | 1650000 |

### stock_hour6_22_cnt

| Valor | Frequência total |
|---|---|
| 0 | 2714556 |
| 1 | 164411 |
| 2 | 129275 |
| 3 | 153153 |
| 4 | 214315 |
| 5 | 259858 |
| 6 | 217449 |
| 7 | 152163 |
| 8 | 119486 |
| 9 | 109654 |
| 10 | 114700 |
| 11 | 116626 |
| 12 | 90343 |
| 13 | 57897 |
| 14 | 28717 |
| 15 | 13065 |
| 16 | 194332 |

## Ruptura × venda

Definição operacional: com ruptura se stock_hour6_22_cnt > 0, sem ruptura nessa janela se igual a zero. O contador equivale à soma dos índices horários 6 a 21 (janela [06h,22h), 16 posições); 1 indica ruptura no vetor da fonte. Rupturas fora da janela são medidas separadamente. A máscara matemática de disponibilidade apresentada no artigo tem polaridade oposta; não é copiada para o indicador raw.

| Conjunto | Disponibilidade [06h,22h) | Venda | Observações |
|---|---|---|---|
| all | with_stockout | positive | 1970857 |
| all | with_stockout | zero | 164587 |
| all | without_stockout | positive | 2663820 |
| all | without_stockout | zero | 50736 |
| eval | with_stockout | positive | 132667 |
| eval | with_stockout | zero | 10771 |
| eval | without_stockout | positive | 202770 |
| eval | without_stockout | zero | 3792 |
| train | with_stockout | positive | 1838190 |
| train | with_stockout | zero | 153816 |
| train | without_stockout | positive | 2461050 |
| train | without_stockout | zero | 46944 |

| Conjunto | Dias com ruptura (%) | Séries com ruptura (%) | Média com | Mediana com | Média sem | Mediana sem |
|---|---|---|---|---|---|---|
| all | 44.029773 | 100 | 1.0356636 | 0.7 | 0.99450065 | 0.7 |
| eval | 40.982286 | 88.252 | 1.1295981 | 0.8 | 1.2371164 | 0.7 |
| train | 44.2668 | 100 | 1.0288997 | 0.7 | 0.97451847 | 0.68 |

Os dados permitem estudar venda observada sob restrição de disponibilidade. As diferenças de venda entre os grupos são descritivas, não efeitos causais. Venda zero sem ruptura na janela não prova demanda zero; venda positiva não exclui ruptura parcial no dia.

## Vetores horários

| Conjunto | Len vendas mín/máx | Len status mín/máx | Nulos internos vendas/status | Diferença máxima soma diária | Divergências soma diária | Divergências contador [06,22) | Ruptura somente fora da janela |
|---|---|---|---|---|---|---|---|
| all | 24/24 | 24/24 | 0/0 | 1.4210855e-14 | 0 | 0 | 763399 |
| eval | 24/24 | 24/24 | 0/0 | 1.4210855e-14 | 0 | 0 | 54618 |
| train | 24/24 | 24/24 | 0/0 | 1.4210855e-14 | 0 | 0 | 708781 |

| Conjunto | Horas com ruptura / 24h (%) | Horas com ruptura / [06,22) (%) |
|---|---|---|
| all | 24.733221 | 19.749442 |
| eval | 22.774583 | 18.107696 |
| train | 24.885559 | 19.877133 |

Comparação de soma em ponto flutuante: tolerância absoluta 1e-9 + relativa 1e-12 × |sale_amount|. O contador inteiro é comparado exatamente. As listas permitem futura análise intradiária de disponibilidade; o grão principal permanece diário.

## Staging

`data/staging/fresh_retail_daily.parquet`: 4850000 linhas de entrada, 4850000 de saída; diferença 0. 21 colunas.

Transformações: dt de string ISO para date32; source_split/source_file adicionados como proveniência. As outras 18 colunas, inclusive listas, foram preservadas e comparadas integralmente em lotes. Não há features, filtros, previsões ou reconstrução de demanda.

SHA-256 do staging: `4e60a715e5a806cc51347cca1e46ec5505c220b7b8fa41c4e1c95d3fa1883f87`.

## Disco

| Artefato | Bytes |
|---|---|
| raw_bytes | 114876411 |
| staging_bytes | 45301416 |
| coverage_bytes | 92084 |

## Checks, diferenças e pendências

Checks: 106/106 aprovados. Hashes e schemas são validados antes desses checks.

Diferenças documentais compreendidas: tipo int64 do vetor de ruptura versus int32 documentado; 865 produtos observados (a ficha atual cita 865, o artigo cita 863); 90 dias referem-se a train, enquanto train+eval cobrem 97 dias. Percentuais de dias com alguma ruptura e de horas com ruptura têm denominadores distintos; a aproximação de 20% na apresentação da fonte não é usada como regra de qualidade.

Pendências para etapas futuras: significado de discount=0 ou >1 não explicado na ficha, unidades e coeficiente de normalização não divulgados, interpretação operacional do calendário local, desenho do backtesting e eventual tratamento de censura. Estoque físico em unidades e lead time não estão disponíveis. Nenhuma dessas pendências autoriza inferir estoque ou demanda latente nesta fase.

Fonte metodológica e atribuição: Wang et al. (2025), [FreshRetailNet-50K](https://arxiv.org/abs/2505.16319); dados de Dingdong-Inc, CC BY 4.0.
