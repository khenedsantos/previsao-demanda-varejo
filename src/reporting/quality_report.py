"""Relatório Markdown factual derivado do JSON da Fase 1."""

from src.ingestion.source_manifest import ROOT


def table(headers, rows):
    def cell(value):
        if value is None:
            return "não confirmado"
        if isinstance(value, float):
            return f"{value:.8g}"
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"]*len(headers)) + "|"]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def write_markdown(report, root=ROOT):
    destination = root / "docs/data_quality_report.md"
    if "summary" not in report:
        destination.write_text(f"# Qualidade dos dados — Fase 1\n\nEstado: bloqueado.\n\n{report.get('error', 'Perfil incompleto.')}\n", encoding="utf-8")
        return
    source = report["source"]
    summaries = report["summary"]
    sections = [
        "# Qualidade dos dados — Fase 1",
        f"Estado: **{report['status']}**. Relatório reproduzível por `python scripts/validate_raw.py`. Nenhuma análise preditiva executada.",
        "## Fonte e rastreabilidade",
        f"[{source['dataset_identifier']}]({source['source_url']}), publisher {source['publisher']}, via {source['source_provider']}. Versão {source['dataset_version']}; licença [{source['license']}]({source['license_url']}).",
        f"Revisão congelada: `{source['source_revision']}`. Aquisição: {source['retrieval_date']}. Data de lançamento transcrita da fonte: `{source['release_date_as_documented']}`; interpretação de dia/mês não confirmada.",
        table(["Arquivo", "Bytes", "Linhas", "SHA-256"], [[e['name'],e['size_bytes'],e['num_rows'],f"`{e['sha256']}`"] for e in source['files']]),
        "Os arquivos oficiais são mantidos sem alterações em data/raw, com o nome original. Hash, tamanho, schema físico e contagem são verificados antes de qualquer profiling. Nenhum dado é versionado no Git.",
        "## Schema documentado × observado",
        "Os dois arquivos têm 19 colunas na mesma ordem. Nullable é a permissão no schema Parquet, não uma contagem de nulos. Todos os campos e elementos das listas permitem nulos no schema.",
        table(["Coluna", "Documentado", "Arrow observado", "Físico Parquet", "Nullable", "Train/eval"], [[f"`{r['column']}`",f"`{r['documented_type']}`",f"`{r['train']['arrow_type']}`",r['train']['physical_type'],r['train']['nullable'],"presente / presente"] for r in report['schema_comparison']]),
        "Divergência compreendida: hours_stock_status é list<int64>, enquanto a ficha declara Sequence(int32). Valores e tipo observado foram preservados. A identidade congelada impede aceitar mudanças futuras silenciosamente.",
        "## Volume, período e grão",
        table(["Conjunto", "Linhas", "Início", "Fim", "Dias", "Cidades", "Lojas", "Produtos", "Séries"], [[r[k] for k in ['scope','n_rows','first_date','last_date','n_dates','n_cities','n_stores','n_products','n_series']] for r in summaries]),
        "Grão confirmado: uma linha por data, loja e produto; chave (dt, store_id, product_id).",
        table(["Conjunto", "Chaves distintas", "Duplicatas excedentes", "Datas inválidas", "Chaves nulas"], [[r[k] for k in ['scope','distinct_daily_keys','duplicate_excess_rows','invalid_dates','null_keys']] for r in summaries]),
        "Duplicatas não são removidas automaticamente. Exemplos, quando existentes, ficam no JSON.",
        "## Nulos",
        table(["Coluna","Train","Eval","Total"], [[column,*[next(r for r in report['nulls'] if r['scope']==scope)[column] for scope in ['train','eval','all']]] for column in source['documented_schema']]),
        "## Cobertura temporal",
        "Por série: missing_days = dias entre primeira/última data (inclusive) menos datas distintas; coverage_ratio = datas distintas / dias calendários. Não se usa contagem de linhas para esconder lacunas com duplicatas.",
        table(["Conjunto","Séries","Mín. obs.","Mediana","Média","Máx. obs.","Completas","Com lacunas"], [[r[k] for k in ['scope','n_series','min_observations','median_observations','mean_observations','max_observations','complete_series','series_with_gaps']] for r in report['coverage_summary']]),
        table(["Conjunto","Observações/série","Dias calendário","Dias ausentes","Nº séries"], [[r[k] for k in ['scope','n_observations','n_calendar_days','missing_days','n_series']] for r in report['coverage_distribution']]),
        "Detalhe por store_id + product_id e conjunto: `data/outputs/series_coverage.parquet` (inclui first_date, last_date, n_observations, n_unique_dates, n_calendar_days, missing_days e coverage_ratio).",
        "## Relação train/eval",
        table(["Entidade","Compartilhadas","Somente train","Somente eval"], [[name,row['shared'],row['train_only'],row['eval_only']] for name,row in report['overlap'].items()]),
        "Os autores usam os 90 dias de train como histórico e os sete dias posteriores de eval para avaliar previsão. Seu baseline oficial pontua dias sem ruptura (stock_hour6_22_cnt=0). Nesta fase, eval foi usado somente para auditoria de estrutura/qualidade; não houve tuning ou seleção de modelo.",
        "Decisão: preservar a identificação original de split no staging; tratar eval como bloco temporal futuro reservado. O desenho do backtesting dentro de train e da avaliação final será definido em etapa posterior. Não considerar o staging combinado uma autorização para treinar com eval.",
        f"Referência do protocolo: [baseline oficial]({source['official_code_url']}/blob/main/demand_forecasting/SSA/ssa_forecasting.py).",
        "## Domínios e extremos",
        "Quantis exatos; nenhum corte, imputação ou remoção de extremos. A tabela resume o conjunto combinado; estatísticas de train/eval, todas as frequências e os valores distintos de discount estão no JSON.",
        table(["Variável","Distintos","Nulos","Negativos","Zeros","Mínimo","P01","Mediana","P99","Máximo"], [[name,r['n_distinct'],r['nulls'],r['negatives'],r['zeros'],r['minimum'],r['quantiles'][0],r['quantiles'][3],r['quantiles'][6],r['maximum']] for name in ['sale_amount','discount','precpt','avg_temperature','avg_humidity','avg_wind_level'] for r in report['numeric'][name] if r['scope']=='all']),
        "sale_amount e hours_sale representam vendas normalizadas por coeficiente global segundo a fonte. Não equivalem, de forma comprovada, a reais, unidades ou quilogramas. Unidades/escala meteorológicas não estão especificadas na ficha; extremos numéricos não foram rotulados como erros com base em limites arbitrários. Negativos e valores não finitos são medidos no JSON.",
        table(["Conjunto","Discount = 0","Discount > 1","Tratamento"], [[r['scope'],r['zero_rows'],r['greater_than_one_rows'],r['action']] for r in report.get('discount_review',[])]),
    ]
    for column in ['activity_flag','holiday_flag','stock_hour6_22_cnt']:
        sections.extend([f"### {column}", table(["Valor","Frequência total"], [[r['value'],r['n_rows']] for r in report['domains'][column] if r['scope']=='all'])])
    sections.extend([
        "## Ruptura × venda",
        "Definição operacional: com ruptura se stock_hour6_22_cnt > 0, sem ruptura nessa janela se igual a zero. O contador equivale à soma dos índices horários 6 a 21 (janela [06h,22h), 16 posições); 1 indica ruptura no vetor da fonte. Rupturas fora da janela são medidas separadamente. A máscara matemática de disponibilidade apresentada no artigo tem polaridade oposta; não é copiada para o indicador raw.",
        table(["Conjunto","Disponibilidade [06h,22h)","Venda","Observações"], [[r[k] for k in ['scope','availability','sales','n_rows']] for r in report['stockout_sales']]),
        table(["Conjunto","Dias com ruptura (%)","Séries com ruptura (%)","Média com","Mediana com","Média sem","Mediana sem"], [[r[k] for k in ['scope','stockout_rows_pct','stockout_series_pct','mean_sale_with_stockout','median_sale_with_stockout','mean_sale_without_stockout','median_sale_without_stockout']] for r in report['stockout_summary']]),
        "Os dados permitem estudar venda observada sob restrição de disponibilidade. As diferenças de venda entre os grupos são descritivas, não efeitos causais. Venda zero sem ruptura na janela não prova demanda zero; venda positiva não exclui ruptura parcial no dia.",
        "## Vetores horários",
        table(["Conjunto","Len vendas mín/máx","Len status mín/máx","Nulos internos vendas/status","Diferença máxima soma diária","Divergências soma diária","Divergências contador [06,22)","Ruptura somente fora da janela"], [[r['scope'],f"{r['sale_min_length']}/{r['sale_max_length']}",f"{r['stock_min_length']}/{r['stock_max_length']}",f"{r['sale_null_elements']}/{r['stock_null_elements']}",r['max_daily_hourly_sales_difference'],r['daily_hourly_sales_mismatches'],r['stock_count_mismatches_06_22_exclusive'],r['stockout_only_outside_06_22']] for r in report['hourly']]),
        table(["Conjunto","Horas com ruptura / 24h (%)","Horas com ruptura / [06,22) (%)"], [[r['scope'],100*r['stockout_hour_slots_24h']/r['total_hour_slots_24h'],100*r['stockout_hour_slots_06_22']/r['total_hour_slots_06_22']] for r in report['hourly']]),
        "Comparação de soma em ponto flutuante: tolerância absoluta 1e-9 + relativa 1e-12 × |sale_amount|. O contador inteiro é comparado exatamente. As listas permitem futura análise intradiária de disponibilidade; o grão principal permanece diário.",
        "## Staging",
    ])
    if report.get('staging'):
        stage = report['staging']
        sections.extend([
            f"`{stage['path']}`: {stage['input_rows']} linhas de entrada, {stage['output_rows']} de saída; diferença {stage['row_difference']}. {len(stage['columns'])} colunas.",
            "Transformações: dt de string ISO para date32; source_split/source_file adicionados como proveniência. As outras 18 colunas, inclusive listas, foram preservadas e comparadas integralmente em lotes. Não há features, filtros, previsões ou reconstrução de demanda.",
            f"SHA-256 do staging: `{stage['sha256']}`.",
        ])
    else:
        sections.append("Staging não publicado nesta execução.")
    if report.get('storage'):
        sections.extend(["## Disco", table(["Artefato","Bytes"], [[k,v] for k,v in report['storage'].items()])])
    sections.extend([
        "## Checks, diferenças e pendências",
        f"Checks: {sum(c['passed'] for c in report['checks'])}/{len(report['checks'])} aprovados. Hashes e schemas são validados antes desses checks.",
        "Diferenças documentais compreendidas: tipo int64 do vetor de ruptura versus int32 documentado; 865 produtos observados (a ficha atual cita 865, o artigo cita 863); 90 dias referem-se a train, enquanto train+eval cobrem 97 dias. Percentuais de dias com alguma ruptura e de horas com ruptura têm denominadores distintos; a aproximação de 20% na apresentação da fonte não é usada como regra de qualidade.",
        "Pendências para etapas futuras: significado de discount=0 ou >1 não explicado na ficha, unidades e coeficiente de normalização não divulgados, interpretação operacional do calendário local, desenho do backtesting e eventual tratamento de censura. Estoque físico em unidades e lead time não estão disponíveis. Nenhuma dessas pendências autoriza inferir estoque ou demanda latente nesta fase.",
        f"Fonte metodológica e atribuição: Wang et al. (2025), [FreshRetailNet-50K]({source['technical_report_url']}); dados de Dingdong-Inc, CC BY 4.0.",
    ])
    if report.get('error'):
        sections.append(f"Erro desta execução: {report['error']}")
    destination.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
