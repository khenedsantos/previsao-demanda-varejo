"""Relatório da Fase 4 a partir dos outputs auditáveis, sem refazer previsões."""

import pandas as pd

from src.ingestion.source_manifest import ROOT


LABELS = {"naive":"Naive", "seasonal_naive":"Seasonal Naive"}


def value(item, percent=False):
    if pd.isna(item):
        return "indefinido"
    if isinstance(item, bool):
        return str(item)
    if isinstance(item, int):
        return str(item)
    if isinstance(item, (int, float)):
        return f"{item*100:.2f}%" if percent else f"{item:.6f}"
    return str(item)


def markdown_table(frame, columns, percentages=()):
    lines=["| " + " | ".join(columns.values()) + " |", "|" + "---|"*len(columns)]
    for row in frame.to_dict("records"):
        lines.append("| " + " | ".join(value(row[key], key in percentages) for key in columns) + " |")
    return "\n".join(lines)


def write_report(summary, performance, root=ROOT):
    folder=root / "data/outputs/forecasting_baselines"
    metrics=pd.DataFrame(summary["metrics"])
    improvement=pd.read_parquet(folder / "relative_improvement.parquet")
    stability=pd.read_parquet(folder / "fold_stability.parquet")
    examples=pd.read_parquet(folder / "example_selection.parquet")
    sections=["# Fase 4 — Forecasting baselines e backtesting temporal",
        "Análise **prospectiva, exclusivamente dentro de train**, sobre `sale_amount`: venda observada "
        "normalizada. Não representa demanda latente, unidades físicas ou receita. Eval permanece "
        "congelado como holdout final; não participa da execução, seleção ou segmentação.",
        "## Desenho temporal e baselines",
        "Quatro folds com histórico crescente e sete dias de horizonte, sem sobreposição dos testes. "
        "Todos começam o histórico em 28/03/2024. O primeiro tem 62 dias e oito semanas completas, "
        "preservando histórico para a regra XYZ; os demais acrescentam uma semana. Quatro folds "
        "equilibram essa exigência e a avaliação em mais de uma janela dentro dos 90 dias.",
        markdown_table(pd.DataFrame(summary["folds"]),{"fold_id":"Fold","history_start":"Início histórico",
            "history_end":"Fim histórico","history_days":"Dias","test_start":"Origem / início teste","test_end":"Fim teste"}),
        "`forecast_origin` é o **primeiro dia previsto, antes de observar sua venda**. `cutoff_date = origin − 1 dia`. "
        "Naive repete o actual do cutoff nos sete dias. Seasonal Naive usa, para cada target_date, "
        "o actual exatamente de target_date − 7 dias. Nenhum deles se atualiza com actuals do próprio horizonte.",
        f"São **{summary['n_series']:,} séries × 4 folds × 7 dias × 2 modelos = {summary['n_forecasts']:,} previsões**. "
        "Cada modelo tem 1.400.000 previsões; a cobertura é completa, sem exclusão de zeros ou séries.",
        "## Métricas, sinal e agregação",
        "Para `e = forecast − actual`, N observações e D = soma(actual):\n\n"
        "- MAE = soma(abs(e))/N; RMSE = sqrt(soma(e²)/N).\n"
        "- WAPE = soma(abs(e))/D; bias = soma(e)/N; bias_pct = soma(e)/D.\n"
        "- Bias é **assinado**, apesar de estar na escala absoluta da venda: positivo indica superprevisão, "
        "negativo subprevisão. Não é abs(bias).\n"
        "- D=0 mantém WAPE e bias_pct nulos; MAE/RMSE/bias continuam definidos. MAPE não é calculado.\n"
        "- Métricas consolidadas são calculadas das somas suficientes, nunca da média dos WAPEs/RMSEs das séries. "
        "MAE/RMSE dão peso a cada previsão; WAPE global pondera as escalas de venda.\n"
        "- Melhoria relativa = (métrica Naive − métrica Seasonal Naive)/métrica Naive, para MAE/RMSE/WAPE. "
        "Referência zero torna a melhoria indefinida. Não se aplica essa divisão ao bias assinado.",
        "## Resultado global e baseline de referência"]
    metric_columns={"model":"Modelo","n_forecasts":"Previsões","actual_sum":"D = soma actual",
                    "mae":"MAE","rmse":"RMSE","wape":"WAPE","bias":"Bias","bias_pct":"Bias %"}
    percentages={"wape","bias_pct"}
    sections.append(markdown_table(metrics.loc[metrics.level.eq("global")],metric_columns,percentages))
    sections.append(markdown_table(improvement.loc[improvement.level.eq("global")],
        {"metric":"Métrica","naive":"Naive","seasonal_naive":"Seasonal Naive","relative_improvement":"Melhoria relativa"},
        {"relative_improvement"}))
    sections.append(f"**Referência: {LABELS[summary['reference_baseline']]}**, pelo menor WAPE global consolidado. "
        "Também reduz MAE e RMSE e aproxima o bias de zero. Vence em WAPE nos quatro folds, "
        "mas sua dispersão global de WAPE é ligeiramente maior: não domina todos os critérios nem todos os grupos.")
    for level, title, dimensions in [
        ("abc","ABC",{"abc_class":"ABC"}),
        ("xyz","XYZ",{"xyz_class":"XYZ"}),
        ("abc_xyz","ABC × XYZ",{"abc_class":"ABC","xyz_class":"XYZ"}),
        ("stockout_exposure","Exposição à ruptura",{"stockout_exposure":"Exposição"}),
        ("censoring_risk_flag","Flag de possível censura",{"censoring_risk_flag":"Flag"}),
    ]:
        sections.extend([f"## Performance por {title}",
            markdown_table(metrics.loc[metrics.level.eq(level)].sort_values([*dimensions,"model"]),
                           {**dimensions,**metric_columns},percentages),
            markdown_table(improvement.loc[improvement.level.eq(level)].sort_values([*dimensions,"metric"]),
                           {**dimensions,"metric":"Métrica","relative_improvement":"Melhoria relativa SN"},
                           {"relative_improvement"})])
    sections.extend(["### Interpretação dos segmentos",
        "ABC usa a contribuição global do produto até cada corte, propagada às séries. A tem MAE maior, "
        "mas WAPE menor que B/C, evidenciando a diferença de escala. O ganho relativo de WAPE é maior "
        "em B (7,39%); B–Z chega a 8,44%. C–Z piora 0,28% em WAPE e C piora ligeiramente em RMSE.",
        "X tem menor WAPE que Y e Z nos dois baselines; também tem MAE/RMSE menores que Z. "
        "Isso apoia parcialmente a hipótese preditiva, sem estabelecer uma ordem universal: Y tem MAE/RMSE "
        "menores que X e, no Seasonal Naive, Z tem **menor desvio e CV do WAPE entre folds** que X. "
        "As regras XYZ não foram ajustadas ao resultado. Os grupos são prospectivos e sua composição pode mudar entre folds.",
        "HIGH tem maior MAE/RMSE e bias mais negativo, porém WAPE menor que LOW: vende mais em escala "
        "normalizada, e o denominador muda a comparação. A flag tem WAPE e subprevisão maiores que o "
        "grupo sem flag. Dentro da flag, Seasonal Naive piora MAE/WAPE em 0,55%, embora melhore RMSE "
        "e bias. Essas associações não demonstram que ruptura causou o erro, não estimam demanda perdida "
        "e não convertem bias negativo automaticamente em risco de ruptura.",
        "## Bias por série e por segmento",
        "A distribuição abaixo agrega os 28 dias previstos por série e modelo. Quantis são calculados "
        "sobre séries com mesmo peso. Não equivalem ao bias percentual global ponderado. "
        "As tabelas anteriores contêm bias e bias_pct por ABC, XYZ, exposição e flag."])
    bias_rows=[]
    for row in summary["bias_distribution"]:
        bias_rows.append({"model":row["model"],"negative":row["underforecast_series"],
            "positive":row["overforecast_series"],"zero":row["n_series"]-row["underforecast_series"]-row["overforecast_series"],
            "p05":row["bias_quantiles"][1],"median":row["bias_quantiles"][3],"p95":row["bias_quantiles"][5],
            "pct_p05":row["bias_pct_quantiles"][1],"pct_median":row["bias_pct_quantiles"][3],
            "pct_p95":row["bias_pct_quantiles"][5]})
    sections.extend([markdown_table(pd.DataFrame(bias_rows),{"model":"Modelo","negative":"Bias < 0",
        "positive":"Bias > 0","zero":"Bias = 0","p05":"Bias p05","median":"Bias mediana","p95":"Bias p95",
        "pct_p05":"Bias % p05","pct_median":"Bias % mediana","pct_p95":"Bias % p95"},
        {"pct_p05","pct_median","pct_p95"}),
        "Naive subprevê em 63,38% das séries; Seasonal Naive em 61,40%. O bias percentual global cai "
        "em magnitude de −7,50% para −3,27%, mas a subprevisão continua, especialmente no quarto fold "
        "(−12,15% e −11,59%). Pode ser operacionalmente indesejável, sem identificar a causa ou uma política de compra.",
        "## Folds e estabilidade",
        markdown_table(metrics.loc[metrics.level.eq("fold")],{"fold_id":"Fold",**metric_columns},percentages),
        "Desvio amostral (ddof=1) entre quatro folds; CV = desvio/média apenas para métricas de erro "
        "com média positiva. Bias mantém sinal e não recebe CV. Média dos WAPEs dos folds é "
        "apresentada separadamente do WAPE global consolidado."])
    for level,dim in [("global",{}),("xyz",{"xyz_class":"XYZ"})]:
        part=stability.loc[stability.level.eq(level)]
        for metric in ["mae","rmse","wape","bias"]:
            columns={**dim,"model":"Modelo",f"{metric}_mean":f"{metric} média",f"{metric}_std":"Desvio",
                     f"{metric}_min":"Mínimo",f"{metric}_max":"Máximo"}
            if metric!="bias":
                columns[f"{metric}_cv"]="CV"
            sections.append(markdown_table(part,columns))
    sections.extend(["A amplitude do WAPE global é 42,40–45,01% no Naive e 41,08–43,88% no Seasonal Naive. "
        "Os desvios são 1,317 e 1,386 pontos percentuais (CV 3,03% e 3,27%). O segundo é melhor em "
        "nível de erro, sem vantagem de estabilidade global. Quatro folds não sustentam inferência de significância.",
        "## Denominadores, zeros e baixa escala",
        markdown_table(pd.DataFrame(summary["denominator_diagnostics"]),{
            "level":"Nível","model":"Modelo","n_cases":"Casos","undefined_wape_cases":"D=0",
            "min_positive_actual_sum":"Menor D positivo","positive_p05":"p05 de D>0",
            "low_scale_cases":"Casos D≤p05","low_scale_median_wape":"WAPE mediano baixo D",
            "low_scale_max_wape":"WAPE máximo baixo D"},{"low_scale_median_wape","low_scale_max_wape"}),
        "Há 263 séries×fold com D=0 por modelo (526 linhas de métricas), mantendo WAPE/bias_pct indefinidos. "
        "Nenhuma série tem D=0 ao agregar os quatro folds. O p05 empírico dos denominadores positivos "
        "serve somente ao diagnóstico: não filtra a avaliação nem define um limite operacional. "
        "WAPE extremo com D=0,1 é matematicamente válido, mas pouco estável. Os denominadores por "
        "grupo estão nas tabelas e no mart; não se faz média de WAPE para contornar o problema.",
        "## Exemplos selecionados por regra",
        "Seleção no **último fold** para manter uma única origem e segmento por exemplo. Melhor/pior "
        "significa menor/maior WAPE válido; subprevisão usa menor bias assinado. HIGH escolhe maior "
        "WAPE; flag escolhe menor bias negativo; Naive supera SN escolhe maior WAPE(SN)−WAPE(Naive)>0. "
        "Empates por store_id e product_id. São extremos, não exemplos representativos, e sua seleção "
        "após medir erro é apenas descritiva, sem efeito em previsão ou escolha de classes.",
        markdown_table(examples,{"selection_rule":"Regra","store_id":"Loja","product_id":"Produto",
            "abc_class":"ABC","xyz_class":"XYZ","actual_sum":"D","wape":"WAPE SN","bias":"Bias SN"},{"wape"}),
        "O pior AX tem D=1,4, o HIGH de maior WAPE e o caso em que Naive mais supera SN têm D=0,1. "
        "Essa dependência da escala deve acompanhar a leitura dos gráficos. O notebook mostra 14 dias "
        "de histórico e sete previstos, com ambos os modelos, actual e marcação de dias afetados por ruptura.",
        "## Controle temporal, proveniência e contratos",
        "Cada fold filtra train **antes** do perfil, ABC, XYZ, quantis de exposição e flag. "
        "O pipeline não lê os marts finais da Fase 2/3, staging ou eval. Actuals do horizonte são unidos "
        "somente depois da geração das previsões. `source_observation_date` permite auditar a fonte de "
        "cada previsão. Os snapshots registram cutoff/origem e os thresholds de cada fold ficam no JSON.",
        markdown_table(pd.DataFrame([{"fold":f["fold_id"],"weeks":f["complete_weeks"][0],
            "no_pattern":f["undefined_pattern_count"],"no_stockout":f["no_stockout_history_count"],
            "cv50":f["xyz_thresholds"]["variability_low"],"cv75":f["xyz_thresholds"]["variability_high"],
            "stock25":f["exposure_thresholds"]["stockout_low"],"stock75":f["exposure_thresholds"]["stockout_high"]}
            for f in summary["folds"]]),{"fold":"Fold","weeks":"Semanas completas","no_pattern":"Forma indefinida",
                "no_stockout":"Sem ruptura","cv50":"CV semanal p50","cv75":"CV semanal p75",
                "stock25":"Ruptura p25","stock75":"Ruptura p75"}),
        "Duas séries no fold 1 e uma no fold 2 não têm ruptura histórica: duração média nos dias afetados "
        "é legitimamente nula. A validação de suporte aceita esse caso somente se frequência, horas totais "
        "e maior sequência forem zero; não imputa duração nem altera regras de classificação da Fase 3.",
        "O mart de previsões tem chave loja+produto+origem+target_date+modelo (fold_id adicional), "
        "horizon_step, cutoff, data da fonte, actual, forecast e error. O mart de métricas usa `level` "
        "para discriminar série×fold, série, fold, global, ABC, XYZ, exposição, flag e ABC×XYZ; inclui "
        "cinco níveis segmento×fold apenas para estabilidade. Dimensões não aplicáveis são nulas. "
        "Sempre filtrar level antes de somar. O nível série consolidado não recebe um segmento único: "
        "a classificação pode mudar. Contagens de séries/produtos distintos entre grupos/folds não são aditivas.",
        markdown_table(pd.DataFrame([{"artifact":key,"path":entry["path"],"rows":entry["rows"]}
            for key,entry in summary["artifacts"].items()]),{"artifact":"Output","path":"Caminho","rows":"Linhas"}),
        f"Fonte verificada: `{summary['source']['path']}`, revisão `{summary['source']['revision']}`, "
        f"SHA-256 `{summary['source']['sha256']}`. Hashes de nove Parquet e versões do runtime ficam "
        "em summary.json. A reprodução exige igualdade dos nove Parquet e do próprio resumo na mesma versão; "
        "performance.json contém telemetria variável e fica fora da comparação determinística.",
        "## Reprodução e testes",
        "```powershell\n.\\.venv\\Scripts\\python.exe scripts/run_baseline_backtest.py\n"
        ".\\.venv\\Scripts\\python.exe scripts/render_forecasting_baselines.py\n"
        ".\\.venv\\Scripts\\python.exe -m pytest\n.\\.venv\\Scripts\\python.exe -m pip check\n"
        "git diff --check\ngit status\n```",
        "Testes cobrem valores conhecidos, sinais, denominador zero, agregação por somas, fontes antes "
        "da origem, t−7, cobertura e unicidade real, thresholds por corte e mutação de todo o futuro "
        "(venda/disponibilidade/atividade/desconto) sem alterar forecasts ou segmentos. A integração "
        "reconstrói os outputs em uma raiz contendo apenas train e as configurações, sem eval, staging "
        "ou marts prévios. Testes das fases anteriores continuam validando seus contratos; a "
        "checagem estrutural de eval da Fase 1 não o usa no backtest.",
        "## Custo computacional",
        f"Execução tabular: {performance['pipeline_seconds']:.2f} s. Nove Parquet: "
        f"{performance['parquet_bytes']:,} bytes ({performance['parquet_bytes']/2**20:.2f} MiB); "
        f"resumo: {performance['summary_bytes']:,} bytes. Pico de working set do processo: "
        f"{performance['process_peak_working_set_bytes']/2**30:.2f} GiB. DuckDB limitado a 1 GB, "
        "uma thread e spill por fold de até 2 GB; esse limite não inclui objetos pandas/PyArrow/Python. "
        "Loops são por fold ou pequenos grupos, sem loop por linha nas 2,8 milhões de previsões. "
        "Tempo/memória excluem notebook, figuras e relatório, cujos tamanhos são contabilizados separadamente na entrega.",
        "## Limitações e recomendação",
        "A janela é curta (90 dias, 28 avaliados) e contém somente quatro origens. Não se avaliam "
        "outras estações, horizontes, novos produtos/lojas ou significância das diferenças. A normalização "
        "da fonte limita comparações de escala; disponibilidade, promoção e mudanças de nível podem "
        "afetar vendas e segmentos. Nenhuma perda por censura foi corrigida ou identificada. As médias "
        "dos grupos misturam séries e composição variável; associação não é causalidade.",
        "Seasonal Naive fica como referência global a superar, preservando Naive como comparação "
        "e as exceções C–Z/flag. A Fase 4 é elegível para aprovação após as validações finais; "
        "a próxima fase poderá comparar modelos adicionais sob este mesmo protocolo, somente mediante "
        "autorização. Nenhum modelo estatístico, tuning, reposição ou dashboard é implementado aqui."])
    path=root / "docs/forecasting_baselines_report.md"
    path.write_text("\n\n".join(sections)+"\n",encoding="utf-8")
    return path
