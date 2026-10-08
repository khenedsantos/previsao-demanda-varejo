"""Relatório da Fase 2 derivado dos outputs, sem acesso aos dados eval."""

from src.ingestion.source_manifest import ROOT


def fmt(value):
    if value is None:
        return "indefinido"
    if isinstance(value, float):
        return f"{value:.6f}"
    if isinstance(value, list):
        return ", ".join(fmt(item) for item in value)
    return str(value)


def table(rows, columns):
    return ["| " + " | ".join(columns) + " |",
            "|" + "|".join(["---"]*len(columns)) + "|"] + [
        "| " + " | ".join(fmt(row.get(c)) for c in columns) + " |" for row in rows]


def write_report(report, path=None):
    path = path or ROOT / "docs/demand_understanding_report.md"
    o, i, w = report["overview"], report["intermittency"], report["within_series"]
    lines = [
        "# Fase 2 — Entendimento da venda observada e disponibilidade", "",
        "Relatório gerado por `python scripts/build_demand_profile.py`. Fonte exclusiva: "
        "`data/raw/train.parquet`. Eval permanece reservado; nenhum dado dele entra neste relatório.", "",
        f"Janela: **{o['first_date']} a {o['last_date']}**; **{o['n_rows']:,} registros**, "
        f"**{o['n_series']:,} séries**, {o['n_stores']} lojas e {o['n_products']} produtos.", "",
        "Os nomes `*_demand` atendem ao contrato do mart, mas medem **venda observada normalizada**. "
        "Não são demanda latente, quantidade física, receita ou margem. Não há imputação, segmentação ou previsão.", "",
        "## Distribuições por série", "",
        f"Média diária global: {o['mean_daily_sale']:.6f}; mediana diária: {o['median_daily_sale']:.6f}; "
        f"soma normalizada: {o['total_sale']:.6f}. As distribuições abaixo atribuem peso igual a cada série.", "",
    ]
    distributions = []
    for metric, values in report["distributions"].items():
        quantiles = values["quantiles"] or [None]*7
        distributions.append({"métrica":metric,"válidas":values["valid"],"indefinidas":values["undefined"],
                              "mín":values["minimum"],"p25":quantiles[2],"p50":quantiles[3],
                              "p75":quantiles[4],"p95":quantiles[5],"máx":values["maximum"]})
    lines += table(distributions, ["métrica","válidas","indefinidas","mín","p25","p50","p75","p95","máx"])
    lines += ["", "CV usa desvio-padrão amostral; média ≤ 1e-9 gera valor indefinido. "
              "Essa tolerância é numérica, não uma regra de XYZ. Valores indefinidos não são preenchidos com zero.", "",
              "## Concentração", "",
              "Curvas ordenadas por soma da venda normalizada, com desempate por identificadores. "
              "As frações top 1%, 5% e 20% usam arredondamento para cima no número de entidades. "
              "A contagem até 80%/95% inclui a entidade que cruza a participação. Não são classes ABC. "
              "Contribuições agregadas também refletem o número de combinações loja-produto presentes; "
              "o painel não contém todo produto em toda loja.", ""]
    concentration_rows = []
    for row in report["concentration"]:
        concentration_rows.append({**row, "fraction_for_80pct":row["entities_for_80pct"]/row["n_entities"] if row["entities_for_80pct"] else None,
                                   "fraction_for_95pct":row["entities_for_95pct"]/row["n_entities"] if row["entities_for_95pct"] else None})
    lines += table(concentration_rows,["level","n_entities","top_1pct_share","top_5pct_share","top_20pct_share","entities_for_80pct","fraction_for_80pct","entities_for_95pct","fraction_for_95pct"])
    lines += ["", "## Zeros e intermitência", "",
              f"Zeros: **{o['zero_rows']:,} registros ({o['zero_row_ratio']:.2%})**. "
              f"{i['any_zeros']:,} séries têm algum zero; {i['no_zeros']:,} não têm zeros. "
              f"**{i['majority_zero_days']:,} séries ({i['majority_zero_days']/o['n_series']:.2%})** "
              "têm zeros na maioria dos dias (>50%): essa é uma contagem descritiva literal, não uma classe de intermitência. "
              f"Séries inteiramente zeradas: {i['all_zero']}; médias próximas de zero: {i['near_zero_mean']}.", "",
              "ADI = número de dias observados / número de dias com venda positiva; sem dias positivos, indefinido. "
              "É a medida agregada de intervalo médio usada aqui, não a média dos intervalos internos entre ocorrências. "
              "Como todas as séries têm o mesmo número de dias, ADI = 1/(1−zero_ratio) e não acrescenta informação "
              "independente aos zeros. CV² dos valores positivos descreve a variação de tamanho das ocorrências.", "",
              f"Dos zeros, {i['zero_rows_with_stockout']:,} coincidem com ruptura em [06h,22h) e "
              f"{i['zero_rows_without_stockout']:,} não coincidem nessa janela. "
              "Um zero observado não demonstra ausência de demanda, mesmo sem ruptura na janela operacional.", "",
              "A distribuição completa por número de dias zerados está em `summary.json` (`zero_days_distribution`); "
              "o notebook mostra sua distribuição acumulada, sem cortes de segmentação.", "",
              "## Padrão semanal", "",
              f"Semanas completas por série: {report['weekly']['min_complete_weeks']}–{report['weekly']['max_complete_weeks']}. "
              "Semanas são segunda a domingo; os trechos incompletos nas pontas não entram em totais/CV semanais "
              "nem no teste descritivo de estabilidade. O perfil por weekday usa todos os dias disponíveis "
              "e médias por observação, evitando confundir diferenças de contagem com nível de venda.", ""]
    lines += table(report["weekday"],["weekday","n_rows","mean_demand","stockout_rate","activity_rate","relative_series_quantiles"])
    lines += ["", "Weekday: 1 = segunda e 7 = domingo. Os três quantis relativos são p25/p50/p75 "
              "da média de cada weekday dividida pela média diária da própria série.", "",
              f"Correlação lag 7 positiva: {report['weekly']['positive_lag7']:,} séries; "
              f"correlação positiva entre perfis das duas metades: {report['weekly']['positive_half_correlation']:,}; "
              f"venda média maior no fim de semana: {report['weekly']['weekend_above_weekday']:,}.", "",
              "Lag 7 é a correlação de Pearson dos pares (venda em t, venda em t−7), exigindo pelo menos "
              "três pares e desvio-padrão >1e-9 nos dois vetores. Não é a ACF com denominador global. "
              "Na estabilidade, cada semana completa é dividida por sua média; comparam-se os sete valores "
              "médios das metades cronológicas (seis semanas em cada metade na janela completa). "
              "Exigem-se pelo menos duas semanas de média positiva em cada metade. Correlação fica indefinida "
              "para perfil constante; MAE de forma continua válida. Nenhuma dessas medidas é um teste de significância.", "",
              "As diferenças entre séries e a estabilidade imperfeita exigem avaliação temporal posterior. "
              "Tendência, promoções e disponibilidade podem influenciar lag 7. O padrão agregado não deve ser "
              "imposto a cada série. A janela não permite afirmar sazonalidade anual.", "",
              "## Ruptura × venda observada", "",
              f"Ruptura em **{o['stockout_row_rate']:.2%}** dos registros, definida como `stock_hour6_22_cnt > 0` "
              "em [06h,22h). Zero fora dessa definição não significa disponibilidade durante 24 horas.", ""]
    lines += table(report["stockout_comparison"],["stockout","n_rows","mean_demand","median_demand","zero_ratio"])
    lines += ["", f"Dentro das mesmas séries, {w['stockout_comparable_series']:,} têm dias com e sem ruptura; "
              f"em {w['stockout_higher_series']:,}, a média é maior nos dias com ruptura, e em "
              f"{w['stockout_lower_series']:,}, menor. Diferença mediana (com − sem): "
              f"{fmt(w['median_stockout_difference'])}; média das diferenças: {fmt(w['mean_stockout_difference'])}.", "",
              "A comparação dentro da série reduz diferenças fixas de nível entre produtos/lojas, "
              "mas não controla demanda latente, promoção, calendário ou duração da ruptura. "
              "Não identifica efeito causal nem vendas perdidas: demanda elevada também pode anteceder ruptura.", "",
              "### Grupos descritivos por frequência de ruptura", "",
              "Cortes nos quartis empíricos da taxa de ruptura; empates permanecem no mesmo grupo, "
              "portanto os tamanhos podem diferir. Não são segmentos XYZ.", ""]
    lines += table(report["stockout_quartiles"],["empirical_quartile","n_series","min_stockout_rate","max_stockout_rate","mean_zero_ratio","median_cv","fraction_zeros_with_stockout","median_within_series_difference"])
    overlap = report["censoring_overlap"]
    lines += ["", f"A interseção de taxa de ruptura ≥ p75 e proporção de zeros ≥ p75 contém "
              f"**{overlap['n_series']:,} séries**. Nela, a taxa média de ruptura é "
              f"{fmt(overlap['mean_stockout_rate'])}, a proporção média de zeros é {fmt(overlap['mean_zero_ratio'])} "
              f"e a fração de zeros coincidentes com ruptura é {fmt(overlap['fraction_zeros_with_stockout'])}. "
              "Esse cruzamento identifica observações especialmente expostas à possível censura, sem estimar "
              "demanda perdida ou atribuir uma classe. Os limites são os quantis de train descritos adiante.", "",
              "### Duração da ruptura", ""]
    lines += table(report["stockout_hours"],["stockout_hours","n_rows","mean_demand","zero_ratio"])
    full_day = next((row for row in report["stockout_hours"] if row["stockout_hours"]==16), None)
    if full_day:
        lines += ["", f"Nos {full_day['n_rows']:,} registros com as 16 horas da janela em ruptura, "
                  f"{full_day['zero_ratio']:.2%} apresentam venda diária zero. A média diária é "
                  f"{full_day['mean_demand']:.6f}; venda positiva ainda pode ocorrer fora da janela. "
                  "Esse é um sinal direto de exposição à possível censura, sem permitir quantificar a demanda latente."]
    lines += ["", "A relação com weekday está na tabela semanal; a relação com atividade está abaixo. "
              "As associações são descritivas e podem refletir seleção dos dias afetados.", "",
              "## Promoções e discount", "",
              f"Atividade promocional em **{o['activity_row_rate']:.2%}** dos registros.", ""]
    lines += table(report["activity_comparison"],["activity_flag","n_rows","mean_demand","median_demand","stockout_rate"])
    lines += ["", f"{w['activity_comparable_series']:,} séries têm dias com e sem atividade; "
              f"{w['activity_higher_series']:,} têm média maior nos dias de atividade. "
              f"Diferença mediana dentro da série: {fmt(w['median_activity_difference'])}; "
              f"média das diferenças: {fmt(w['mean_activity_difference'])}. Não representam uplift causal. "
              f"Dentro das mesmas séries, {w['activity_stockout_higher_series']:,} têm taxa de ruptura maior "
              f"nos dias de atividade; diferença mediana de taxa: {fmt(w['median_activity_stockout_difference'])}.", ""]
    lines += table([report["discount"]],["minimum","maximum","zero_rows","discount_rows","equal_one_rows","above_one_rows","quantiles"])
    lines += ["", "`discount_days` conta estritamente 0 < discount < 1. Zero e >1 são mantidos em "
              "contagens separadas; `mean_discount` preserva todos os valores. Atividade e fator de desconto "
              "são dimensões diferentes, sem equivalência presumida.", ""]
    lines += table(report["discount_activity"],["activity_flag","discount_group","n_rows"])
    lines += ["", "### Investigação de discount > 1", "",
              f"Train contém **{len(report['discount_anomalies'])} ocorrências**. A contagem foi apurada "
              "diretamente em train, sem consultar eval. A referência histórica da Fase 1 era 34 ocorrências "
              "no conjunto combinado; portanto todas as 34 já podem ser investigadas aqui.", ""]
    lines += table(report["anomalous_product_context"],["product_id","n_rows","n_stores","min_discount","max_discount","above_one_rows","zero_rows","activity_rows"])
    lines += ["", "Ocorrências completas (valores originais):", ""]
    lines += table(report["discount_anomalies"],["product_id","store_id","dt","discount","activity_flag","sale_amount","stock_hour6_22_cnt"])
    lines += ["", "A concentração por produto e a repetição de fatores sugerem um padrão específico "
              "de cadastro/cálculo do fator, a investigar com o publisher. Os dados não permitem distinguir "
              "erro de preço de referência, arredondamento ou outra convenção. Não há preço para validar "
              "essas hipóteses. Os valores foram preservados; não se conclui que sejam erro nem promoção.", "",
              "## Exemplos por regra reproduzível", "",
              "Alta/baixa venda e ruptura usam p75/p25 de train. Dentro dos filtros, escolhe-se a maior "
              "média (alta venda) ou menor média (baixa venda). Volatilidade/zeros usam o máximo válido. "
              "Desempate sempre por store_id e product_id; regras podem selecionar a mesma série.", ""]
    lines += table([report["example_thresholds"]],list(report["example_thresholds"]))
    lines += [""] + table(report["examples"],["rule","store_id","product_id","mean_demand","coefficient_of_variation","zero_ratio","stockout_rate","adi"])
    lines += ["", "## Implicações e limites para as próximas fases", "",
              "- A concentração deve orientar uma futura ABC por contribuição de venda/demanda normalizada, "
              "sem interpretação financeira. A distribuição empírica não determina sozinha uma regra 80/15/5.",
              "- XYZ deve considerar CV, zeros/ADI, estabilidade semanal e exposição à ruptura. "
              "CV alto pode refletir censura ou promoção; CV baixo não comprova previsibilidade.",
              "- ADI e zero_ratio são redundantes nesta janela completa; não devem contar duas vezes o mesmo sinal.",
              "- Os perfis usam todo train e são descritivos ao corte final. Em backtesting futuro, refazer "
              "os perfis e os quantis em cada origem; não reutilizar o mart final em cortes anteriores.",
              "- Não há reconstrução de demanda, decisão de threshold, causalidade, modelo, receita, "
              "estoque físico, política de reposição nem avaliação de holdout nesta fase.", "",
              "## Artefatos e rastreabilidade", "",
              f"Fonte: `{report['source']['path']}`; SHA-256 `{report['source']['sha256']}`; "
              f"revisão `{report['source']['revision']}`.", "",
              "Runtime de geração: " + ", ".join(f"{k} {v}" for k,v in report["runtime"].items()) + ".", ""]
    lines += table([{"name":name,**row} for name,row in report["artifacts"].items()],["name","path","rows","sha256"])
    lines += ["", "Resumo estruturado: `data/outputs/demand_understanding/summary.json`. "
              "Notebook: `notebooks/01_data_understanding.ipynb`, com nove figuras; consome apenas outputs. "
              "Metodologia e definições completas em `docs/methodology.md`. "
              "Reprodução bit a bit é verificada no runtime local registrado; outra versão de engine/formato pode mudar bytes.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
