"""Versioned schema and documentation for the six-table BI export contract."""

STARTING_HEAD = "c5f117861434ed10ba77d1c2c88b98aa47cab13a"
KEYS = ["store_id", "product_id"]
ATTRIBUTES = ["abc_class", "xyz_class", "stockout_exposure", "censoring_risk_flag",
              "persistent_underforecast_flag", "demand_observation_risk_cell"]
MODEL_NAMES = {"ets_ana": "ETS", "seasonal_naive": "Seasonal Naive"}
SCENARIOS = ["LEAN", "BASE", "PROTECTED"]
NULLABLE = {("FactReplenishment", "buffer_to_forecast_ratio"),
            ("FactReplenishment", "equivalent_coverage_days")}

# name, logical type, definition, aggregation behavior, caveat/sort instruction.
SCHEMAS = {
    "DimSeries": [
        ("series_key", "integer", "Chave determinística da série na população congelada de 50.000 pares.", "KEY", "1 a 50.000, ordenando store_id e product_id; não depende da ordem de leitura."),
        ("store_id", "integer", "Identificador anonimizado da loja.", "KEY", "Não representa quantidade; compõe a chave natural."),
        ("product_id", "integer", "Identificador anonimizado do produto.", "KEY", "Não representa quantidade; compõe a chave natural."),
        ("abc_class", "text", "Classe ABC congelada em 25/06/2024.", "CATEGORY", "Relevância de venda observada normalizada, não receita; snapshot final."),
        ("xyz_class", "text", "Classe XYZ congelada em 25/06/2024.", "CATEGORY", "Regra anterior preservada, sem reclassificação."),
        ("stockout_exposure", "text", "Exposição histórica à ruptura: LOW, MEDIUM ou HIGH.", "CATEGORY", "Contexto histórico, não estoque atual."),
        ("censoring_risk_flag", "boolean", "Sinal histórico de risco de censura da venda observada.", "BOOLEAN", "Não estima demanda latente nem multiplica buffer."),
        ("persistent_underforecast_flag", "boolean", "Sinal histórico congelado de subprevisão persistente.", "BOOLEAN", "Não é garantia de subprevisão futura nem multiplicador de buffer."),
        ("demand_observation_risk_cell", "text", "Combinação dos sinais de censura e subprevisão.", "CATEGORY", "Overlay descritivo; não autoriza compra automática."),
    ],
    "DimDate": [
        ("date", "date", "Data do horizonte final avaliado.", "KEY", "ISO YYYY-MM-DD; somente 26/06/2024 a 02/07/2024."),
        ("year", "integer", "Ano civil da data.", "DO_NOT_SUM", "Atributo de calendário."),
        ("month_number", "integer", "Mês civil, de 1 a 12.", "DO_NOT_SUM", "Ordena month_name."),
        ("month_name", "text", "Nome do mês em português.", "CATEGORY", "Ordenar por month_number."),
        ("year_month", "text", "Ano e mês no formato YYYY-MM.", "CATEGORY", "Ordem lexical equivale à cronológica."),
        ("day", "integer", "Dia do mês, de 1 a 31.", "DO_NOT_SUM", "Atributo de calendário."),
        ("day_of_week_number", "integer", "Dia da semana: segunda=1 até domingo=7.", "DO_NOT_SUM", "Ordena day_of_week_name."),
        ("day_of_week_name", "text", "Nome do dia da semana em português.", "CATEGORY", "Ordenar por day_of_week_number."),
        ("is_weekend", "boolean", "Indicador de sábado ou domingo.", "BOOLEAN", "Não é indicador de feriado; nenhum feriado foi inferido."),
        ("date_sort", "integer", "Data como inteiro YYYYMMDD para ordenação.", "DO_NOT_SUM", "Chave de ordenação, não medida."),
    ],
    "DimScenario": [
        ("scenario", "text", "Cenário hipotético LEAN, BASE ou PROTECTED.", "KEY", "Ordenar por scenario_order."),
        ("scenario_order", "integer", "Ordem de apresentação: 1 LEAN, 2 BASE, 3 PROTECTED.", "DO_NOT_SUM", "Não indica superioridade ou recomendação."),
        ("lead_time_days", "integer", "Lead time hipotético: 1, 2 ou 3 dias.", "DO_NOT_SUM", "Não é prazo observado de fornecedor."),
        ("target_coverage_level", "decimal", "Cobertura alvo hipotética da distribuição histórica do erro.", "DO_NOT_SUM", "Fração 0–1; não é fill rate, OTIF ou service level real."),
        ("scenario_description", "text", "Descrição explícita de lead time e target hipotéticos.", "CATEGORY", "Nenhum cenário é automaticamente melhor."),
    ],
    "FactForecast": [
        ("date", "date", "Data prevista e avaliada no holdout final.", "KEY", "FK DimDate; compõe PK com série e modelo."),
        ("series_key", "integer", "Série loja-produto avaliada.", "KEY", "FK DimSeries."),
        ("model", "text", "Nome amigável: ETS ou Seasonal Naive.", "CATEGORY", "Selecionar exatamente um modelo ao somar actual; actual aparece nos dois modelos."),
        ("model_code", "text", "Código congelado do modelo solicitado: ets_ana ou seasonal_naive.", "CATEGORY", "Mapeamento 1:1 com model; fallback_flag mantém indicação do fallback original."),
        ("actual", "decimal", "Venda observada normalizada do holdout, copiada do mart.", "SUM", "Aditiva em datas/séries para UM modelo; duplicada entre modelos. Não é receita/unidade física."),
        ("forecast", "decimal", "Previsão final congelada após clipping/fallback originais.", "SUM", "Somar dentro de um modelo; não recomputar nem somar modelos alternativos."),
        ("forecast_unclipped", "decimal", "Previsão original antes do clipping a zero.", "SUM", "Diagnóstico por modelo; pode ser negativa. Não substituir o forecast oficial."),
        ("error", "decimal", "Erro assinado congelado: forecast menos actual.", "SUM", "Soma é numerador do bias_pct; bias é média. Negativo indica subprevisão."),
        ("absolute_error", "decimal", "Erro absoluto congelado.", "SUM", "MAE=média; WAPE=soma dividida por soma(actual), com um modelo selecionado."),
        ("squared_error", "decimal", "Erro quadrático congelado.", "SUM", "RMSE=raiz da média; não tirar média de RMSEs agregados."),
        ("fallback_flag", "boolean", "Fallback registrado na previsão original.", "BOOLEAN", "Repete-se nos sete dias da série/modelo; contagem de linhas não é número de ajustes."),
        ("negative_clipped", "boolean", "Previsão diária negativa projetada para zero.", "BOOLEAN", "Flag por previsão diária; não somar como quantidade de venda."),
    ],
    "FactReplenishment": [
        ("series_key", "integer", "Série loja-produto do snapshot simulado.", "KEY", "FK DimSeries; compõe PK com scenario."),
        ("scenario", "text", "Cenário hipotético aplicado à série.", "KEY", "FK DimScenario; cenários são alternativas, não parcelas aditivas."),
        ("lead_time_days", "integer", "Lead time hipotético congelado do cenário.", "DO_NOT_SUM", "Redundância controlada: idêntico à DimScenario; preferir a dimensão para filtros."),
        ("target_coverage_level", "decimal", "Cobertura alvo hipotética do cenário.", "DO_NOT_SUM", "Idêntico à DimScenario; não confundir com cobertura observada."),
        ("lead_time_forecast", "decimal", "Soma das previsões ETS congeladas dos primeiros L dias.", "SUM", "Aditiva entre séries dentro de UM cenário/snapshot; escala normalizada."),
        ("historical_error_std", "decimal", "Desvio-padrão histórico por série, congelado na Fase 6.", "DO_NOT_SUM", "Dispersão com ddof=1; não é aditiva, nem desvio-padrão de um agregado."),
        ("empirical_multiplier", "decimal", "Multiplicador empírico final da Fase 8.", "DO_NOT_SUM", "Não recalibrar em BI; média descritiva não é multiplicador de uma população."),
        ("safety_stock", "decimal", "Buffer simulado de proteção na escala normalizada.", "SUM", "Somar séries somente dentro de um cenário/snapshot. Não é estoque físico nem quantidade a comprar."),
        ("reorder_point", "decimal", "Limiar simulado: lead_time_forecast mais safety_stock.", "SUM", "Sem estoque atual ou pedidos; não somar cenários/snapshots alternativos."),
        ("buffer_to_forecast_ratio", "decimal", "Ratio individual safety_stock/lead_time_forecast.", "DO_NOT_SUM", "Nullable se denominador zero; ratio agregado usa soma(SS)/soma(forecast), não média dos ratios."),
        ("equivalent_coverage_days", "decimal", "ROP dividido pela média prevista dos sete dias.", "DO_NOT_SUM", "Nullable se média zero; equivalência descritiva, não dias reais garantidos."),
        ("calibration_level_used", "text", "Nível da hierarquia de calibração efetivamente utilizado.", "CATEGORY", "Regra congelada por suporte; não escolher pela performance no BI."),
        ("calibration_n", "integer", "Número de janelas série×fold no pool de calibração.", "DO_NOT_SUM", "Repetido nas séries da célula; não somar nem interpretar como amostra independente."),
        ("as_of", "date", "Corte histórico do snapshot: 25/06/2024.", "DO_NOT_SUM", "Sem relacionamento com DimDate nesta camada."),
        ("available_from", "date", "Disponibilidade do snapshot: 26/06/2024.", "DO_NOT_SUM", "Não é data de compra ou entrega; sem relacionamento com DimDate."),
    ],
    "FactScenarioValidation": [
        ("scenario", "text", "Cenário da validação temporal congelada.", "KEY", "PK atual e FK DimScenario; é fato de resultado, não dimensão."),
        ("target_coverage_level", "decimal", "Cobertura alvo hipotética avaliada.", "DO_NOT_SUM", "Idêntica à DimScenario; não é cobertura atingida."),
        ("observed_coverage_rate", "decimal", "Cobertura global no fold4 com calibração dos folds 1–3.", "DO_NOT_SUM", "Fração 0–1; não responde a filtros de série, classe ou data neste modelo."),
        ("coverage_gap", "decimal", "Cobertura observada menos alvo.", "DO_NOT_SUM", "Fração assinada; multiplicar por 100 somente para exibir pontos percentuais."),
        ("normal_reference_coverage", "decimal", "Cobertura global da referência Normal no fold4.", "DO_NOT_SUM", "Benchmark congelado, sem seleção automática de fórmula."),
        ("validation_stage", "text", "Etapa histórica do resultado: validation_fold4.", "CATEGORY", "Não representa cobertura realizada do snapshot final de 26/06."),
    ],
}

TABLES = {
    "DimSeries": ("dim_series.csv", 50000, ["series_key"]),
    "DimDate": ("dim_date.csv", 7, ["date"]),
    "DimScenario": ("dim_scenario.csv", 3, ["scenario"]),
    "FactForecast": ("fact_forecast.csv", 700000, ["date", "series_key", "model"]),
    "FactReplenishment": ("fact_replenishment.csv", 150000, ["series_key", "scenario"]),
    "FactScenarioValidation": ("fact_scenario_validation.csv", 3, ["scenario"]),
}

RELATIONSHIPS = [
    {"dimension": dimension, "fact": fact, "column": column,
     "cardinality": "1:N", "filter_direction": "single_dimension_to_fact"}
    for dimension, fact, column in [
        ("DimSeries", "FactForecast", "series_key"),
        ("DimSeries", "FactReplenishment", "series_key"),
        ("DimDate", "FactForecast", "date"),
        ("DimScenario", "FactReplenishment", "scenario"),
        ("DimScenario", "FactScenarioValidation", "scenario"),
    ]
]
