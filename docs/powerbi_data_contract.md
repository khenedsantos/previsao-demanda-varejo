# Fase 9 — Power BI data contract & semantic layer

## Objetivo e fronteira

Preparar seis tabelas pequenas em número de colunas, com grão explícito e métricas
preservadas, para consumo futuro. HEAD de partida: `c5f117861434ed10ba77d1c2c88b98aa47cab13a`.
Esta fase não cria PBIX, DAX, dashboard, páginas ou visuais e não abre Power BI.
Não recalibra forecasting, reposição ou flags. Não acessa raw/staging e não executa fitting.
Actuals do holdout já autorizado são **copiados do mart final**, exclusivamente para
preservar a avaliação existente; não fundamentam nova decisão analítica.

Construção e verificações ficam em `src/reporting/powerbi_layer.py`; schema e semântica
versionados em `src/reporting/powerbi_contract.py`. Nenhum pipeline das fases anteriores
é chamado. As seis tabelas são toda a camada de consumo; marts de referência e manifests
permanecem fora do modelo BI.

## Tabelas, grãos e chaves

| Tabela | CSV em `powerbi/data/` | Linhas | Colunas | Grão / PK | FK |
|---|---|---:|---:|---|---|
| DimSeries | dim_series.csv | 50.000 | 9 | series_key; chave natural store_id + product_id | — |
| DimDate | dim_date.csv | 7 | 10 | date | — |
| DimScenario | dim_scenario.csv | 3 | 5 | scenario | — |
| FactForecast | fact_forecast.csv | 700.000 | 12 | date + series_key + model | date → DimDate; series_key → DimSeries |
| FactReplenishment | fact_replenishment.csv | 150.000 | 15 | series_key + scenario | series_key → DimSeries; scenario → DimScenario |
| FactScenarioValidation | fact_scenario_validation.csv | 3 | 6 | scenario | scenario → DimScenario |

Todos os grãos e PK são únicos. As cinco FK têm **zero órfãos**. FactForecast contém
350.000 linhas ETS e 350.000 Seasonal Naive; FactReplenishment contém 50.000 por cenário.
As 129 linhas de resumo da Fase 8 são filtradas em Python para as três linhas globais da
validação fold4. O resumo completo e as tabelas de calibração não são exportados ao BI.

## Proveniência congelada

| Fonte | Uso | SHA-256 |
|---|---|---|
| data/processed/mart_holdout_forecast.parquet | FactForecast, calendário e conferência de cobertura das séries | fad7ab566c90ef41e8474b689d11186f2edc01d02bfe17b545e6bff4dd1ba3b8 |
| data/processed/mart_holdout_model_comparison.parquet | Somente referência para validar métricas globais; não exportado | 392fb14c9f60845500c590e21db201293f396df4199570988f1ae77ca35c17c7 |
| data/processed/mart_replenishment_simulation.parquet | DimSeries, DimScenario, FactReplenishment | 47d98eec77c2b23687d4453786b1b37a0f15b4a441cde7f8e479424e5713e7e4 |
| data/processed/mart_replenishment_summary.parquet | FactScenarioValidation e referência das médias finais | eb87e6a30afc2a3579d739920a870d8d8f10b2835826eda253e4eab750dec193 |

Hashes e contagens são verificados contra os manifests congelados das Fases 7/8 antes e
depois da exportação. Os quatro marts e os dois manifests são os únicos inputs de dados.
Nenhum forecast, actual, erro, buffer, quantil ou flag é recalculado para produção: campos
são copiados, selecionados ou renomeados. Identidades e métricas são reconstruídas apenas
para verificar transporte e consistência. Dimensões de calendário e chaves são transformações
de contrato, não novas análises.

## DimSeries e estabilidade da chave

Deduplicar `store_id + product_id` com seus seis atributos; exigir que os atributos sejam
idênticos nos três cenários. Ordenar numericamente `store_id ASC, product_id ASC` e atribuir
`series_key = 1..50.000`. Não utilizar hash ou ordem física de arquivo.

O teste embaralha todas as 150.000 linhas de entrada e exige a mesma dimensão e o mesmo
mapeamento. A estabilidade é para esta **população congelada**, cuja identidade consta
dos hashes. Não é promessa de invariância sob inclusão/exclusão de séries: essa extensão
exigiria nova versão do contrato e uma política persistente de chaves, fora desta fase.
O builder rejeita fonte com hash/grão divergente, evitando remapeamento silencioso.

ABC, XYZ, exposição e os dois sinais/risk_cell são o snapshot final de 25/06, disponível
em 26/06. São apropriados para o holdout final e o snapshot de reposição. Não descrevem
classes históricas de datas anteriores. Não carregar métricas contínuas na dimensão.

`city_id`, `management_group_id` e as três categorias não estavam disponíveis nos schemas
dos marts processados existentes. Permanecem ausentes: não acessar raw/staging para
enriquecimento, não preencher atributos desconhecidos e não criar dimensões adicionais.

## DimDate e DimScenario

Calendário diário completo somente para o horizonte necessário: **26/06/2024–02/07/2024**.
Datas são datas civis, sem hora/fuso. Mês e dia da semana usam português; segunda-feira=1,
domingo=7. Ordenar `month_name` por `month_number`, `day_of_week_name` por
`day_of_week_number`; `year_month` é YYYY-MM e `date_sort` é YYYYMMDD inteiro.
`is_weekend` indica sábado/domingo; nenhum feriado é inventado. Este calendário de sete
dias não oferece histórico para análises anuais ou inteligência temporal de longo prazo.

| Ordem | Cenário | Lead time hipotético | Target hipotético |
|---:|---|---:|---:|
| 1 | LEAN | 1 dia | 90% |
| 2 | BASE | 2 dias | 95% |
| 3 | PROTECTED | 3 dias | 98% |

Ordenar `scenario` por `scenario_order`. Os valores vêm do mart congelado e são conferidos
contra as três hipóteses aprovadas. Descrições identificam explicitamente a natureza
hipotética. `target_coverage_level` não é nível de serviço real, fill rate, OTIF ou garantia
de ausência de ruptura. Cenários são alternativas; PROTECTED não é automaticamente melhor.

## Fatos e conservação da capacidade de análise

FactForecast preserva `actual`, `forecast`, `forecast_unclipped`, `error`, `absolute_error`,
`squared_error`, `fallback_flag` e `negative_clipped`. Renomeia `dt` para `date`; mantém
`model_code` (`ets_ana`, `seasonal_naive`) e rótulo amigável `model` (`ETS`, `Seasonal Naive`).
`model` identifica o método solicitado, mesmo se houver fallback; a flag original permanece.
Campos técnicos de convergência, warnings, datas redundantes e motivos longos não são exportados.

FactReplenishment remove IDs naturais e os seis atributos já presentes em DimSeries.
Um teste reconstitui esses atributos via chave e exige igualdade com as 150.000 linhas
originais; portanto, filtros ABC/XYZ/exposição/flags mantêm a capacidade de análise.
Mantém os 15 campos contratados. `lead_time_days` e `target_coverage_level` são redundâncias
deliberadas solicitadas no fato, verificadas contra DimScenario; usar a dimensão para filtros.
Nenhuma quantidade de compra, estoque atual ou custo é criado.

FactScenarioValidation é **fato de resultado histórico**, não dimensão. Seleciona somente
`stage=validation_fold4` e `level=global`. Renomeia `normal_coverage_rate` para
`normal_reference_coverage` e `stage` para `validation_stage`. Os valores não são hardcoded
no exportador: vêm das três linhas congeladas. Não misturar com `final_snapshot` nem
atribuir cobertura realizada aos forecasts de planejamento.

## Relacionamentos previstos

| Lado 1 | Lado N | Cardinalidade declarada | Filtro |
|---|---|---|---|
| DimSeries[series_key] | FactForecast[series_key] | 1:N | Dimensão → fato, single |
| DimSeries[series_key] | FactReplenishment[series_key] | 1:N | Dimensão → fato, single |
| DimDate[date] | FactForecast[date] | 1:N | Dimensão → fato, single |
| DimScenario[scenario] | FactReplenishment[scenario] | 1:N | Dimensão → fato, single |
| DimScenario[scenario] | FactScenarioValidation[scenario] | 1:N | Dimensão → fato, single |

Não há relacionamento fato-fato, many-to-many ou bidirecional. FactScenarioValidation tem
hoje uma linha por cenário, embora seu papel seja o lado N do contrato. Não converter
automaticamente essa coincidência de unicidade atual em relacionamento 1:1 bidirecional;
na montagem posterior, conferir manualmente a cardinalidade e a direção declaradas.

Semântica dos filtros:

- Série, loja, produto, ABC, XYZ, exposição e sinais filtram os dois fatos detalhados.
- Data filtra apenas FactForecast, não o snapshot de reposição.
- Cenário filtra FactReplenishment e FactScenarioValidation, não FactForecast.
- Modelo pertence a FactForecast; reposição usa somente o ETS congelado.
- Cobertura histórica global não responde a série, classe, loja, produto ou data.
  Aplicar tais filtros ao detalhe não transforma a cobertura global em cobertura do segmento.
  Não criar relações adicionais para produzir essa impressão.

## Tipos e transporte CSV

O [dicionário](../powerbi/data_dictionary.csv) contém todas as **57 colunas**, com tipo,
definição, comportamento de agregação e observações. O manifesto também registra schema,
nulabilidade e contagem efetiva de nulos por coluna.

| Tipo lógico | Tipo esperado no consumo | Regra |
|---|---|---|
| integer | Número inteiro, 64 bits | Chaves e códigos não devem ser somados |
| decimal | Número decimal, float64 | Preservar precisão; não converter para moeda/decimal fixo de quatro casas |
| boolean | Verdadeiro/falso | CSV contém `true` ou `false`, sem nulos |
| date | Data | ISO YYYY-MM-DD; não texto nem datetime |
| text | Texto/categoria | Preservar rótulos e códigos |

CSV é transporte textual e não impõe tipos sozinho. Aplicar os tipos declarados no consumo;
não depender da inferência automática. Formato: **UTF-8 com BOM**, delimitador vírgula,
decimal ponto, sem separador de milhar, cabeçalho, sem índice, linhas LF. Importação numérica
deve interpretar ponto decimal (por exemplo, cultura en-US), independentemente da exibição
posterior em português. Datas devem continuar ISO. Booleans devem ser convertidos explicitamente.

Números são escritos com 17 algarismos significativos; a releitura controlada recupera
exatamente os float64 originais. A conferência da montagem futura do modelo continua
necessária: igualdade do CSV não substitui validação de importação/relacionamentos no BI.

Apenas `buffer_to_forecast_ratio` e `equivalent_coverage_days` aceitam nulos, quando seus
denominadores não são positivos. Nulo é campo vazio; não converter para zero. Nenhuma
outra coluna aceita nulo, infinito ou chave ausente.

## Aditividade e métricas que não podem ser somadas

`actual`, `forecast`, `safety_stock` e `reorder_point` estão na escala **normalizada da
fonte**. Não são receita, unidades físicas, estoque real ou demanda latente.

| Campo/grupo | Comportamento permitido | Risco de uso incorreto |
|---|---|---|
| actual | Somar datas/séries dentro de exatamente um modelo | O mesmo actual aparece em ETS e Seasonal Naive; somar modelos duplica vendas |
| forecast / forecast_unclipped | Somar datas/séries dentro de um modelo | Modelos são previsões alternativas; unclipped é diagnóstico |
| error / absolute_error / squared_error | Somas suficientes por modelo | Erro assinado não é WAPE; erro quadrático não é RMSE |
| lead_time_forecast / safety_stock / reorder_point | Somar séries em um único cenário e snapshot | Semiaditivos: não somar cenários ou snapshots alternativos |
| historical_error_std / empirical_multiplier | Não somar | Média descritiva não equivale à dispersão/multiplicador de um agregado |
| buffer_to_forecast_ratio | Não somar; agregado por ratio das somas | Média simples dos ratios não representa o ratio agregado |
| equivalent_coverage_days | Não somar | Não representa dias reais garantidos; média é apenas descritiva |
| target / observed coverage / gap / Normal coverage | Não somar nem combinar cenários | Target é hipótese; observed é resultado global histórico |
| calibration_n | Não somar | O mesmo pool se repete em muitas séries; não é tamanho efetivo independente |
| flags | Filtrar ou contar no grão explicitamente escolhido | Fallback por ajuste se repete nos sete dias; linhas não equivalem a ajustes |
| IDs, calendário, classes, lead time | Não somar | São chaves, categorias ou parâmetros |

As fórmulas abaixo documentam métricas existentes; **não são medidas DAX implementadas**:

- MAE = soma(absolute_error) / número de previsões.
- RMSE = raiz(soma(squared_error) / número de previsões).
- WAPE = soma(absolute_error) / soma(actual), com denominador positivo.
- Bias = soma(error) / número de previsões; bias_pct = soma(error) / soma(actual).
- Ratio agregado de buffer = soma(safety_stock) / soma(lead_time_forecast), dentro de um cenário.

Não tirar média de WAPEs/RMSEs de segmentos. Nunca substituir denominador zero por uma
porcentagem artificial. Fórmulas complexas de calibração, segmentação e buffer continuam
em Python; não duplicá-las futuramente em DAX. MAPE não é usado.

## Reconciliação dos valores congelados

| Modelo | MAE | RMSE | WAPE | bias_pct |
|---|---:|---:|---:|---:|
| ETS | 0,424983100 | 0,711310598 | 35,621479292% | −2,251620869% |
| Seasonal Naive | 0,499070806 | 0,835818696 | 41,831405477% | +0,277255573% |

| Cenário | SS médio final | ROP médio final | Target | Cobertura fold4 | Gap (p.p.) | Normal fold4 |
|---|---:|---:|---:|---:|---:|---:|
| LEAN | 0,572305714 | 1,646254434 | 90% | 79,648% | −10,352 | 83,640% |
| BASE | 1,147686576 | 3,263576280 | 95% | 84,084% | −10,916 | 86,136% |
| PROTECTED | 2,024078854 | 5,239064350 | 98% | 88,322% | −9,678 | 87,204% |

Agregações são comparadas aos marts estruturados com `rtol=1e-10, atol=1e-12`;
pequenas diferenças de ordem de soma em ponto flutuante não alteram os números.
Coverage é comparada com `atol=1e-12`. Valores individuais de todas as tabelas devem
ser exatamente iguais antes/depois da serialização. Divergência bloqueia a publicação:
primeiro escrever `.csv.tmp`, reler, validar e somente depois publicar os seis CSVs e manifesto.

Os três alvos da política **não foram atingidos** no fold4. Aprovação da camada semântica
significa transporte fiel, não validação de serviço real ou recomendação de compra.
ABC/XYZ/flags permanecem diagnósticos congelados. Não utilizar os actuals exportados para
retuning, ajuste de buffers ou seleção de cenários.

## Reprodutibilidade e arquivos

```powershell
.\.venv\Scripts\python.exe scripts/build_powerbi_layer.py
.\.venv\Scripts\python.exe -m pytest tests/test_powerbi_layer.py --basetemp=.tmp/pytest-phase9-final --junitxml=.tmp/phase9-final-results.xml -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
git diff --cached --name-only
git status
```

Não executar pipelines ou suítes legadas que refaçam forecasting. A suíte desta fase cobre
contagens, PK/FK, datas, grãos, estabilidade das chaves, modelos/cenários, métricas,
reconstrução de atributos, tipos, nulos, hashes e reprodução a partir somente dos inputs
autorizados. Sentinelas artificiais e leitores protegidos impedem acesso a raw/staging;
funções de forecasting e fitting são bloqueadas nos testes. O builder também bloqueia
`ExponentialSmoothing.fit` antes de qualquer possível otimização.

`powerbi/data_manifest.json` registra HEAD de partida, hashes dos quatro marts e dois
manifests, schema, PK/FK, métricas reconciliadas, hashes/tamanhos dos seis CSVs e do
dicionário. É determinístico; timestamp e duração ficam separados em
`powerbi/build_performance.json`. O manifesto não é uma sétima tabela do modelo.

Os seis CSVs totalizam **142.679.095 bytes** (aproximadamente 136,07 MiB):

| CSV | Bytes |
|---|---:|
| dim_series.csv | 2.340.478 |
| dim_date.csv | 550 |
| dim_scenario.csv | 377 |
| fact_forecast.csv | 108.230.063 |
| fact_replenishment.csv | 32.107.199 |
| fact_scenario_validation.csv | 428 |

Versionar somente código, teste, contrato, dicionário de documentação e `.gitkeep`.
`powerbi/data/*`, `powerbi/data_manifest.json` e `powerbi/build_performance.json` são outputs
reproduzíveis ignorados. As regras anteriores de dados, ambiente, segredos e temporários
permanecem. Nenhum artefato analítico das Fases 0–8 é sobrescrito. Sem stage ou commit.

## Limites e próxima fronteira

O pacote não implementa relacionamentos dentro do aplicativo; declara e testa o contrato
que deverá ser aplicado e validado posteriormente com o usuário. Nenhuma medida, visual,
layout ou narrativa de dashboard foi escolhida. O calendário é curto e a população é fixa.
Não há cidade/categoria confiável nesta camada, estoque atual, pedidos ou custos.
Somente os seis arquivos de dados devem ser importados; não importar pasta com temporários,
manifesto, dicionário ou fontes técnicas como fatos adicionais.

A construção posterior deverá respeitar a sequência autorizada: dados → modelo →
relacionamentos → medidas → validação → visuais → narrativa executiva. Esta entrega
termina no contrato e nos dados, sem avançar automaticamente.

## Resultado da rodada

**Camada BI aprovada como contrato e exportação auditável.** Foram aprovados **19 testes**
da Fase 9 em **70,07 s**, sem falhas, erros ou skips. Duas reproduções em raiz de teste
com somente os quatro marts e dois manifests autorizados produziram os mesmos hashes
dos seis CSVs, do dicionário e do manifesto. Acesso a raw/staging e execução de forecasting
estavam bloqueados. `pip check`: nenhuma dependência incompatível.

Build inicial: **29,81 s**; 900.013 linhas somando as seis tabelas. Nenhum fitting,
nenhuma recalibração e nenhum arquivo analítico anterior alterado. `git diff --check`
aprovado; stage vazio. As aprovações de transporte não substituem a validação futura
dos tipos e relacionamentos dentro do Power BI nem tornam os targets da Fase 8 atingidos.
