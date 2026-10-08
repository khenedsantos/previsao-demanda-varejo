"""Relatório auditável das dimensões operacionais, calculadas apenas em train."""

from src.ingestion.source_manifest import ROOT


def fmt(value):
    if value is None:
        return "indefinido"
    if isinstance(value,float):
        return f"{value:.6f}"
    return str(value)


def table(rows,columns):
    return ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"]*len(columns)) + "|"] + [
        "| " + " | ".join(fmt(row.get(c)) for c in columns) + " |" for row in rows]


def write_report(s,path=None):
    path=path or ROOT / "docs/segmentation_report.md"
    t,e=s["xyz"]["thresholds"],s["exposure"]["thresholds"]
    lines=["# Fase 3 — Segmentação e perfil operacional", "",
           "Gerado por `python scripts/build_segmentation.py`. Três dimensões independentes: "
           "ABC por contribuição de venda normalizada do produto; XYZ por estabilidade observada da série; "
           "exposição à ruptura e flag de possível censura. **Não há score composto.**", "",
           f"Fonte exclusiva: train, 28/03/2024 a {s['as_of']}; {s['n_products']} produtos; "
           f"{s['n_series']:,} séries loja-produto. Eval não foi usado. "
           "Nenhum forecasting, backtesting, modelo, reposição ou dashboard foi implementado.", "",
           "## ABC — relevância do produto", "",
           "A contribuição é a soma de sale_amount no train, recalculada diretamente do arquivo oficial. "
           "Produtos são ordenados por contribuição decrescente e depois product_id crescente. "
           "Não representa receita, margem ou unidade física.", "",
           "**Fronteira:** seja P o acumulado antes do produto. A se P<0,80; B se 0,80≤P<0,95; "
           "C se P≥0,95. Assim, o produto que cruza o limite fica na classe cujo intervalo está sendo "
           "completado. Igualdade com uma fronteira, com tolerância absoluta de 1e-12 na participação, "
           "significa que o intervalo já está completo. Empates não são agrupados; product_id resolve a ordem. "
           "Não há cotas por contagem nem números de produtos hardcoded na classificação.", ""]
    lines+=table(s["abc"]["distribution"],["abc_class","n_products","normalized_sales_total","normalized_sales_share","n_series"])
    lines += ["", "Produtos que encerram cada classe:", ""]
    boundaries=[{**row,"normalized_sales_cumulative_share_before":f"{row['normalized_sales_cumulative_share_before']:.12f}",
                 "normalized_sales_cumulative_share":f"{row['normalized_sales_cumulative_share']:.12f}"}
                for row in s["abc"]["class_ending_products"]]
    lines+=table(boundaries,["abc_class","product_id","abc_rank","normalized_sales_cumulative_share_before","normalized_sales_cumulative_share"])
    lines += ["", "ABC é propagado por product_id para todas as séries daquele produto. "
              "Não é recalculado por loja-produto. A classe representa relevância global no painel observado; "
              "quantidade de lojas em que o produto aparece também influencia sua contribuição.", "",
              "## XYZ — métricas, redundância e escolha", "",
              "Avaliadas: CV diário, CV semanal, correlação e MAE entre os perfis semanais das metades, "
              "lag 7, zero_ratio e ADI. Matrizes calculadas por pares completos; as quatro séries sem "
              "estabilidade válida não são preenchidas. Cada célula tem contagem de pares no Parquet de suporte.", ""]
    labels={"coefficient_of_variation":"CV_dia","weekly_coefficient_of_variation":"CV_semana",
            "weekly_pattern_half_correlation":"corr_forma","weekly_pattern_half_mae":"MAE_forma",
            "autocorrelation_lag7":"lag7","zero_ratio":"zeros","adi":"ADI"}
    for method in ["pearson","spearman"]:
        rows=[]
        for metric,label in labels.items():
            row={"métrica":label}
            row.update({labels[r["metric_2"]]:r["correlation"] for r in s["correlations"]
                        if r["method"]==method and r["metric_1"]==metric})
            rows.append(row)
        lines += [f"### {method.title()}", ""] + table(rows,["métrica",*labels.values()])+[""]
    lines += ["CV diário e semanal têm Pearson ≈0,81 e Spearman ≈0,80: usar ambos como critérios "
              "principais duplicaria boa parte do sinal. CV semanal e correlação de forma têm associação "
              "linear/rank fraca (≈−0,10/−0,08), representando aspectos complementares. MAE de forma "
              "aumenta com CV diário (≈0,69) e se associa inversamente à correlação da forma (≈−0,50); "
              "fica como diagnóstico, sem adicionar um terceiro corte. Isso é parcimônia, não prova de equivalência entre métricas.", "",
              "**Conjunto mínimo escolhido: CV semanal + correlação do padrão entre metades.** "
              "O primeiro descreve variação dos totais entre semanas; o segundo, persistência da forma por weekday. "
              "Essa escolha evita penalizar automaticamente variação diária causada por um padrão semanal repetível. "
              "CV diário, MAE, lag 7, zeros e fim de semana continuam disponíveis para validação.", "",
              "Lag 7 não define classe: na Fase 2 ele também refletiu variação de nível. "
              "ADI é 1/(1−zero_ratio); Spearman=1, apesar de Pearson não ser exatamente 1 pela não linearidade. "
              "Zero_ratio permanece diagnóstico: as 74 séries com maioria de zeros já estão em Z pela regra escolhida. "
              "Não se adiciona uma exceção redundante nem se trata o painel como predominantemente intermitente.", "",
              "### Alternativas transparentes comparadas", "",
              "Todas usam Z se CV≥limite superior OU estabilidade≤limite inferior; X se CV≤limite baixo "
              "E estabilidade≥limite bom, após a regra Z; Y nos demais casos. Quantis são calculados somente "
              "em train, por interpolação linear. Mediana/caudas significa p50/p75 no CV e p25/p50 na estabilidade.", ""]
    comparisons=[]
    for candidate in s["xyz"]["candidates"]:
        ct=candidate["thresholds"]
        comparisons.append({"regra":candidate["name"],"CV_baixo":ct["variability_low"],"CV_alto":ct["variability_high"],
                            "forma_baixa":ct["stability_low"],"forma_boa":ct["stability_good"],
                            **candidate["class_counts"],"mudam_vs_escolhida":candidate["changed_vs_selected"]})
    lines+=table(comparisons,["regra","CV_baixo","CV_alto","forma_baixa","forma_boa","X","Y","Z","mudam_vs_escolhida"])
    lines += ["", "Escolhida **weekly_median_tail**: reserva X para desempenho simultaneamente favorável "
              "nas duas dimensões (metades melhores) e Z para uma cauda desfavorável (quartil). "
              "Quartis em ambos os lados restringem X a cerca de 7% do painel; tercis ampliam Z para mais "
              "da metade. A opção escolhida preserva separação descritiva entre classes sem impor tamanhos iguais. "
              "A alternativa de CV diário tem distribuição semelhante, mas mede também oscilação dentro da semana. "
              "Apesar das contagens próximas, a troca para CV diário muda 9.226 séries (18,45%): "
              "tamanhos semelhantes não implicam as mesmas séries em cada classe. "
              "Não existe quebra natural única demonstrada nas distribuições: os quantis são uma convenção "
              "relativa, explicitamente escolhida, e não limites físicos universais ou thresholds otimizados para erro preditivo.", "",
              "### Regra final e limites calculados", "",
              f"- **Z:** CV semanal ≥ **{t['variability_high']:.12f}** (p75) OU correlação da forma ≤ "
              f"**{t['stability_low']:.12f}** (p25).",
              f"- **X:** sem critério Z, CV semanal ≤ **{t['variability_low']:.12f}** (p50) E correlação "
              f"da forma ≥ **{t['stability_good']:.12f}** (p50).",
              "- **Y:** demais séries. Empates ficam juntos; Z tem prioridade se houver sobreposição de limites.", ""]
    lines+=table([{"xyz_class":c,"n_series":n,"series_share":n/s["n_series"]} for c,n in s["xyz"]["distribution"].items()],
                 ["xyz_class","n_series","series_share"])
    lines += ["", "### Casos indefinidos e razões auditáveis", "",
              "Uma métrica indefinida nunca é substituída por zero. Havendo evidência válida de Z na outra "
              "métrica, a série recebe Z com razão específica; sem essa evidência, recebe Y_INCOMPLETE_METRICS "
              "(classe provisória de revisão, sem presumir estabilidade). As quatro séries reais têm CV semanal "
              "acima de p75 e recebem Z_HIGH_CV_NO_PATTERN. Nenhuma série foi descartada.", ""]
    lines+=table(s["xyz"]["undefined_stability"],["store_id","product_id","weekly_coefficient_of_variation","xyz_class","xyz_reason"])
    lines += [""] + table([{"xyz_reason":k,"definição":v} for k,v in s["xyz"]["reasons"].items()],["xyz_reason","definição"])
    lines += ["", "### Validação do comportamento das classes", "",
              "Medianas por classe. A separação nas métricas que definem a regra é esperada por construção; "
              "não constitui validação preditiva independente. Quantis e contagens válidas estão no output de suporte.", ""]
    grouped={c:{"xyz_class":c} for c in ["X","Y","Z"]}
    for row in s["xyz"]["class_profiles"]:
        grouped[row["xyz_class"]][row["metric"]]=row["median"]
    lines+=table(list(grouped.values()),["xyz_class","coefficient_of_variation","weekly_coefficient_of_variation",
                                        "weekly_pattern_half_correlation","weekly_pattern_half_mae","autocorrelation_lag7",
                                        "zero_ratio","mean_demand","weekend_weekday_relative_difference"])
    lines += ["", "CV diário/semanal e MAE aumentam de X para Z; correlação de forma diminui. "
              "Lag 7 não segue essa ordem: sua mediana em Z é maior que em X. Portanto Z descreve "
              "instabilidade nos eixos escolhidos, não dificuldade de previsão comprovada. "
              "Somente a fase futura de forecast/backtesting poderá avaliar essa hipótese operacional.", "",
              "## Exposição à ruptura e possível censura", "",
              f"Métrica principal: stockout_rate, com p25=**{e['stockout_low']:.12f}** e "
              f"p75=**{e['stockout_high']:.12f}**. LOW se taxa≤p25; HIGH se taxa≥p75; MEDIUM entre eles. "
              "HIGH tem prioridade se os quantis coincidirem. São exposições relativas ao painel, "
              "não níveis absolutos aceitáveis de disponibilidade. LOW ainda pode ter ruptura frequente.", "",
              "Horas totais, maior sequência e duração média dos dias afetados validam a dimensão, "
              "sem pesos e sem alterar XYZ.", ""]
    lines+=table(s["exposure"]["distribution"],["stockout_exposure","n_series","normalized_sales_total",
                                               "mean_stockout_rate","median_stockout_rate","censoring_risk_count"])
    lines += ["", "Medianas das métricas de suporte:", ""]
    exposure_medians={c:{"stockout_exposure":c} for c in ["LOW","MEDIUM","HIGH"]}
    for row in s["exposure"]["metric_profiles"]:
        exposure_medians[row["stockout_exposure"]][row["metric"]]=row["median"]
    lines+=table(list(exposure_medians.values()),["stockout_exposure","stockout_rate","total_stockout_hours",
                                                 "maximum_consecutive_stockout_days","mean_stockout_hours_when_affected","zero_ratio"])
    lines += ["", "Horas totais e maior sequência medianas crescem de LOW para HIGH, mas a duração média "
              "por dia afetado não: sua mediana cai de 7,80 para 6,36 horas. Frequência e duração capturam "
              "aspectos diferentes. Por isso HIGH não é apresentado como índice completo de severidade, "
              "e LOW não é interpretado como ausência de problema de disponibilidade."]
    lines += ["", f"**censoring_risk_flag** = stockout_rate≥p75 E zero_ratio≥p75 "
              f"(**{e['zero_high']:.12f}**). Resultado recalculado: **{s['exposure']['censoring_count']:,} séries "
              f"({s['exposure']['censoring_share']:.2%})**, reproduzindo o achado da Fase 2. "
              f"Entre os zeros desse grupo, {s['exposure']['flagged_zero_stockout_fraction']:.2%} coincidem "
              "com ruptura em [06h,22h). É alta exposição à possível censura da venda observada, "
              "não demanda perdida comprovada. A ausência da flag não comprova ausência de censura.", "",
              "## Matriz ABC × XYZ", "",
              "Participação = venda da célula / venda total normalizada do train. Produtos podem aparecer "
              "em várias colunas XYZ por terem séries de classes diferentes; **n_products não é aditivo** "
              "entre células. Contagem/participação de censoring refere-se às séries dentro da célula.", ""]
    lines+=table(s["abc_xyz_matrix"],["abc_class","xyz_class","n_series","n_products","normalized_sales_total",
                                     "normalized_sales_share","mean_stockout_rate","median_stockout_rate",
                                     "censoring_risk_count","censoring_risk_share","high_exposure_count"])
    lines += ["", "## Perfis operacionais prioritários", "",
              "Os grupos abaixo se sobrepõem: A_CENSOR_FLAG pode estar nos demais perfis A. "
              "Não somar suas participações como uma partição.", ""]
    lines+=table(s["priority_profiles"],["profile","n_series","n_products","normalized_sales_total","normalized_sales_share",
                                        "median_stockout_rate","median_weekly_cv","median_pattern_correlation","censoring_risk_count"])
    lines += ["", "- **AX_HIGH:** produto relevante e série relativamente estável, mas alta frequência de ruptura. "
              "Investigar disponibilidade antes de interpretar a venda como demanda livre de restrição.",
              "- **AY_HIGH:** produto relevante com comportamento intermediário e exposição elevada. "
              "Preservar os dois diagnósticos ao avaliar métodos futuramente.",
              "- **AZ_HIGH:** relevância combinada a instabilidade observada e ruptura. "
              "Requer análise cuidadosa de censura e incerteza; não prova erro de forecast elevado.",
              "- **A_CENSOR_FLAG:** grupo relevante especialmente exposto à possível censura; "
              "prioridade de investigação da qualidade do alvo, sem quantificar venda perdida.",
              "- **CZ_LOW:** contribuição global menor e instabilidade apesar de exposição relativamente baixa. "
              "A baixa relevância não torna a série automaticamente simples de prever.", "",
              "## Exemplos reproduzíveis", "",
              "Maiores valores da métrica indicada dentro do filtro, com desempate por store_id e product_id. "
              "A_CENSOR_HIGH_STOCKOUT filtra A+flag e ordena por ruptura, depois zeros e identificadores; "
              "não é um score de risco. CX/CZ próximos da mediana minimizam a distância absoluta do CV "
              "semanal à mediana da combinação, sem reivindicar representatividade em todos os eixos. "
              "Regras podem selecionar a mesma série.", ""]
    lines+=table(s["examples"],["selection_rule","store_id","product_id","abc_class","xyz_class","stockout_exposure",
                                "censoring_risk_flag","total_demand","weekly_coefficient_of_variation",
                                "weekly_pattern_half_correlation","stockout_rate","zero_ratio"])
    lines += ["", "## Limites e uso temporal", "",
              "**No backtesting futuro, ABC, XYZ, thresholds e quantis não poderão ser reaproveitados "
              "retrospectivamente.** Recalcular somente com dados disponíveis até cada origem quando "
              "forem features ou critérios de decisão temporal. O pipeline recusa um mart da Fase 2 "
              "cujo corte seja diferente do solicitado.", "",
              "XYZ usa venda observada: separar disponibilidade da regra não remove seu efeito indireto "
              "nos valores de venda. Promoção e mudança de nível também podem afetar as métricas. "
              "O corte é curto, com 12 semanas completas; não há sazonalidade anual validada. "
              "Os limites por quantis são relativos e não universais. Nenhuma política de reposição foi definida.", "",
              "## Rastreabilidade e reprodução", "",
              f"Fonte train SHA-256: `{s['source']['sha256']}`; revisão `{s['source']['revision']}`. "
              f"Perfil da Fase 2 SHA-256: `{s['inputs']['profile_sha256']}`.", "",
              "Runtime: " + ", ".join(f"{k} {v}" for k,v in s["runtime"].items()) + ".", ""]
    lines+=table([{"name":name,**artifact} for name,artifact in s["artifacts"].items()],["name","path","rows","sha256"])
    lines += ["", "Resumo: `data/outputs/segmentation/summary.json`. Notebook: "
              "`notebooks/02_segmentation.ipynb`, com nove figuras baseadas nos outputs. "
              "Reprodução por hash é garantida no runtime registrado, sem timestamps ou caminhos absolutos "
              "nos artefatos tabulares. Regras, fórmulas e comandos em `docs/methodology.md`.", ""]
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text("\n".join(lines),encoding="utf-8")
