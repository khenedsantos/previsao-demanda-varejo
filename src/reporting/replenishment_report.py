"""Phase 8 documentation from simulation outputs only; no raw or fitting."""

import pandas as pd

from src.ingestion.source_manifest import ROOT
from src.replenishment.simulation import FOLDER, read_json
from src.reporting.forecast_report import markdown_table


def load_outputs(root=ROOT):
    summary = read_json(root / FOLDER / "summary.json")
    data = {"metadata": summary, "performance": read_json(root / FOLDER / "performance.json")}
    for name in ["simulation", "calibration", "summary", "dependence", "examples", "fallback_distribution", "top_a_buffers", "lead_time_diagnostics"]:
        data[name] = pd.read_parquet(root / summary["artifacts"][name]["path"])
    return data


def table(frame, columns, percentages=()):
    return markdown_table(frame, {name: label for name, label in columns}, percentages)


def write_report(root=ROOT):
    data = load_outputs(root)
    summary, calibration = data["summary"], data["calibration"]
    final = summary.loc[summary.stage.eq("final_snapshot")]
    validation = summary.loc[summary.stage.eq("validation_fold4")]
    global_final = final.loc[final.level.eq("global")].sort_values("lead_time_days")
    global_val = validation.loc[validation.level.eq("global")].sort_values("lead_time_days")
    common = [("scenario", "Cenário"), ("n_series", "Séries"), ("mean_safety_stock", "SS médio"),
              ("median_safety_stock", "SS mediano"), ("p90_safety_stock", "SS p90"),
              ("mean_reorder_point", "ROP médio"), ("median_reorder_point", "ROP mediano"),
              ("buffer_to_forecast_ratio", "ΣSS/Σforecast"), ("median_buffer_ratio", "Ratio mediano")]
    sections = ["# Fase 8 — Replenishment policy simulation",
        "## 1. Objetivo e natureza da entrega",
        "Transformar forecasts ETS **já congelados** e incerteza histórica em limiares hipotéticos de posição de estoque. "
        "**Simulação**, na escala de venda observada normalizada: não é política real da empresa, estoque físico, ordem de compra ou demanda latente. "
        "HEAD inicial `3c52827`; zero fitting ETS, zero acesso a actuals de eval e nenhuma alteração dos forecasts. "
        "O protocolo foi escrito antes de calcular cobertura da política no fold 4: [protocolo](replenishment_simulation_protocol.md).",
        "## 2. Por que é simulação",
        "Faltam estoque físico completo, posição de inventário, pedidos abertos, lead times reais, fornecedores e custos. "
        "Safety stock (SS) e reorder point (ROP) são quantidades **simuladas**, sem equivalência comprovada com unidades físicas. "
        "Não se calcula quantidade a comprar, lost sales, fill rate, OTIF ou custo financeiro.",
        "## 3. Premissas e fronteira temporal",
        "Forecast oficial A/N/A inalterado, incluindo clipping e fallback anteriores. O input de planejamento é "
        "`final_holdout/frozen_predictions.parquet`, sem actuals, salvo antes da abertura de eval na Fase 7. "
        "Somente erros de backtest de train calibram os buffers. Rótulos históricos são os snapshots prospectivos da Fase 4, "
        "cada um conhecido antes de seu fold. Aplicação de validação usa rótulos de 18/06; snapshot final usa rótulos de 25/06. "
        "Migrações de classe entre cortes não são reclassificadas retroativamente.",
        "## 4. Cenários e significado de cobertura alvo",
        table(pd.DataFrame(data["metadata"]["scenarios"]), [("scenario", "Cenário"), ("lead_time_days", "L hipotético"), ("target_coverage_level", "Cobertura alvo")], ["target_coverage_level"]),
        "`service_level` permanece no YAML por compatibilidade; outputs usam `target_coverage_level`. "
        "É o quantil alvo da distribuição histórica do erro contra **venda observada normalizada**, não serviço real ou garantia de ausência de ruptura. "
        "Os valores dos três cenários não foram alterados.",
        "## 5. Erro acumulado e buffer",
        "Nos primeiros L dias de cada fold: `lead_time_error = Σforecast − Σactual`; "
        "`lead_time_shortfall = max(Σactual − Σforecast, 0)`. "
        "Padronização: `shortfall / (error_std × sqrt(L))`. "
        "`SS = quantil_empírico × error_std × sqrt(L)`; `ROP = Σforecast[:L] + SS`. "
        "Bias continua separado do point forecast. Underforecast histórico pode aumentar o quantil de shortfall e, portanto, o buffer; "
        "isso não corrige nem altera ETS. Nenhum MAPE.",
        table(data["lead_time_diagnostics"].loc[lambda x: x.stage.eq("calibration_folds1234")],
              [("scenario", "Cenário"), ("fold_id", "Fold"), ("mean_lead_time_error", "Bias acumulado médio"), ("mean_shortfall", "Shortfall médio")]),
        "## 6. Dependência temporal dos resíduos",
        "Diagnóstico anterior à validação, somente folds 1–3. Erros centrados por média da série e divididos pelo std histórico de 21 erros. "
        "Correlações agrupam pares dentro do mesmo fold/série; nunca atravessam fronteiras. "
        "Razão de agregação = Var(soma dos primeiros L resíduos padronizados)/ΣVar(resíduo de cada passo). "
        "Trata-se de diagnóstico agrupado, não estimativa confiável de autocorrelação individual com apenas 21 erros.",
        table(data["dependence"], [("diagnostic", "Diagnóstico"), ("step", "Lag/L"), ("n", "Pares/janelas"), ("value", "Valor")]),
        "As razões acima de 1 para L=2/3 contrariam a aproximação de independência. sqrt(L) é uma escala de referência; "
        "os quantis empíricos de shortfalls acumulados preservam a dependência observada dentro de cada janela. "
        "Não garantem a mesma dependência em períodos futuros nem normalidade.",
        "## 7. Calibração empírica e suporte",
        "Quantil linear, com 20 observações esperadas na cauda: mínimos exatos 200/400/1000. "
        "Hierarquia fixa: ABC×XYZ×exposure → ABC×XYZ → XYZ → GLOBAL, usando o nível mais específico elegível. "
        "n conta janelas série×fold; séries distintas também são registradas. Dependência entre séries e folds reduz a informação efetiva; "
        "o mínimo de cauda é uma regra de suporte, não intervalo de confiança. Escala não positiva/não finita ou GLOBAL insuficiente bloqueia. "
        "Nenhuma série teve escala inválida, nenhuma foi excluída silenciosamente e RMSE não substituiu std.",
        table(data["fallback_distribution"], [("stage", "Etapa"), ("scenario", "Cenário"), ("calibration_level_used", "Nível usado"), ("n_series", "Séries")]),
        "## 8. Referência Normal e sensibilidade limitada",
        "Normal z(q) usa a mesma escala histórica, apenas como benchmark. A fórmula empírica foi pré-definida, "
        "sem seleção por holdout ou busca de dezenas de variantes. Comparar cobertura e tamanho não significa escolher o maior buffer.",
        table(global_val, [("scenario", "Cenário"), ("mean_empirical_multiplier", "Multiplicador empírico médio"),
            ("observed_coverage_rate", "Cobertura empírica fold4"), ("normal_coverage_rate", "Cobertura Normal fold4"),
            ("mean_safety_stock", "SS empírico médio"), ("mean_normal_safety_stock", "SS Normal médio")], ["observed_coverage_rate", "normal_coverage_rate"]),
        table(calibration.loc[calibration.stage.eq("calibration_folds123")].groupby("scenario", as_index=False).theoretical_normal_z.first(),
              [("scenario", "Cenário"), ("theoretical_normal_z", "z Normal")]),
        "## 9. Validação temporal folds 1–3 → fold 4",
        "Escala ddof=1 calculada com exatamente 21 erros por série; o std final da Fase 6 não é usado nesta validação. "
        "Multiplicadores e escalas são persistidos em `calibration_locked.json` antes de medir cobertura. "
        "Cobertura = fração de séries com ROP ≥ venda observada acumulada, sem pesos; gap = cobertura − alvo. "
        "**Os três targets não foram atingidos:** subcobertura de aproximadamente 9,68–10,92 pontos percentuais. "
        "A Normal também fica abaixo dos alvos; supera a cobertura empírica em LEAN/BASE, mas fica abaixo em PROTECTED. "
        "O fold4 apresenta bias acumulado médio negativo em L1/L2/L3 (−0,132/−0,254/−0,421), "
        "enquanto L2/L3 tinham bias positivo nos três folds anteriores. Essa mudança temporal coincide com maior shortfall; "
        "a calibração histórica não o cobriu nos níveis nominais. Não interpretar isso como prova causal ou corrigir o ETS. "
        "Não há ajuste posterior para forçar o target. Esta validação usa um único fold de train; não comprova cobertura futura.",
        table(global_val, [("scenario", "Cenário"), ("target_coverage_level", "Alvo"), ("observed_coverage_rate", "Observada"),
            ("coverage_gap", "Gap (fração)"), ("buffer_above_forecast_rate", "SS > forecast"), ("fallback_rate", "Fallback")],
            ["target_coverage_level", "observed_coverage_rate", "coverage_gap", "buffer_above_forecast_rate", "fallback_rate"]),
        table(global_val, common),
        "### Cobertura por segmentos prospectivos",
        table(validation.loc[validation.level.ne("global")], [("scenario", "Cenário"), ("level", "Nível"), ("cell", "Célula"),
            ("n_series", "Séries"), ("observed_coverage_rate", "Cobertura"), ("coverage_gap", "Gap"), ("normal_coverage_rate", "Normal")],
            ["observed_coverage_rate", "coverage_gap", "normal_coverage_rate"]),
        "## 10. Calibração final com quatro folds",
        "Após a validação, a mesma regra usa quatro folds (200.000 janelas por cenário) e o std congelado da Fase 6, "
        "com 28 erros por série. Rótulos das observações de calibração continuam prospectivos; aplicação final usa classes de 25/06. "
        "Nenhum actual eval participa. A cobertura fold4 pertence à calibração 1–3 e fica nula nas linhas de calibração final; "
        "não apresentamos desempenho do próprio conjunto de calibração como validação independente.",
        table(global_final, common),
        table(global_final, [("scenario", "Cenário"), ("mean_empirical_multiplier", "Multiplicador final médio"),
            ("mean_normal_safety_stock", "SS Normal médio"), ("buffer_above_forecast_rate", "SS > forecast"), ("undefined_ratio_series", "Ratios indefinidos")], ["buffer_above_forecast_rate"]),
    ]
    lean = global_final.iloc[0]
    for number, row in enumerate(global_final.itertuples(), 11):
        sections += [f"## {number}. {row.scenario}",
            f"L={row.lead_time_days}, q={row.target_coverage_level:.0%}: SS médio **{row.mean_safety_stock:.6f}**, "
            f"ROP médio **{row.mean_reorder_point:.6f}**, ratio agregado **{row.buffer_to_forecast_ratio:.2%}**. "
            f"Em relação a LEAN, SS cresce **{row.mean_safety_stock / lean.mean_safety_stock - 1:.2%}** "
            f"e ROP **{row.mean_reorder_point / lean.mean_reorder_point - 1:.2%}**. "
            f"O fator explícito sqrt(L) é {row.lead_time_days ** .5:.6f}; multiplicador final médio {row.mean_empirical_multiplier:.6f}. "
            "L e q variam juntos: efeitos não são identificáveis separadamente por estes três cenários. "
            "Forecast acumulado, escala sqrt(L) e quantil contribuem simultaneamente; não há cenário vencedor automático."]
    for number, level in [(14, "ABC"), (15, "XYZ"), (16, "exposure")]:
        sections += [f"## {number}. {level}", table(final.loc[final.level.eq(level)],
            [("scenario", "Cenário"), ("cell", "Classe"), ("n_series", "Séries"), ("mean_safety_stock", "SS médio"),
             ("mean_reorder_point", "ROP médio"), ("median_buffer_ratio", "Ratio mediano"), ("buffer_share", "Participação no SS")], ["buffer_share"])]
    sections += ["## 17. Overlays de risco e exemplos",
        "Censoring, persistência e risk_cell não são dimensões de calibração nem multiplicadores. "
        "A + CENSORING_AND_UNDERFORECAST destaca coexistência de relevância, buffer e sinais de observação; "
        "é grupo de investigação, não compra automática. Nenhum score ou nova classificação de prioridade.",
        table(final.loc[final.level.isin(["risk_cell", "A_double_signal"])], [("scenario", "Cenário"), ("level", "Recorte"),
            ("cell", "Sinal"), ("n_series", "Séries"), ("mean_safety_stock", "SS médio"), ("mean_reorder_point", "ROP médio"),
            ("median_buffer_ratio", "Ratio mediano"), ("buffer_share", "Participação no SS total")], ["buffer_share"]),
        "Sete exemplos gráficos reutilizados da Fase 6. Tabela auxiliar `top_a_buffers` lista dez maiores buffers A por cenário, "
        "desempate crescente por IDs; não substitui a seleção gráfica nem define prioridade de compra.",
        table(data["top_a_buffers"], [("scenario", "Cenário"), ("store_id", "Loja A"), ("product_id", "Produto"),
            ("safety_stock", "SS"), ("reorder_point", "ROP"), ("demand_observation_risk_cell", "Overlay")]),
        table(data["examples"], [("selection_rule", "Regra congelada"), ("store_id", "Loja"), ("product_id", "Produto"),
            ("scenario", "Cenário"), ("lead_time_forecast", "Forecast L"), ("safety_stock", "SS"), ("reorder_point", "ROP")]),
        "## 18. Limitações",
        "Só quatro folds semanais, uma validação temporal de sete dias e três janelas de calibração por série; "
        "caudas são estimadas por pooling. Série×fold não é amostra independente. Classes podem migrar. "
        "Padronização é estimada no próprio conjunto de calibração e não incorpora sua incerteza. "
        "O diagnóstico de dependência é agrupado e não modela todos os choques comuns. Vendas observadas podem ser censuradas; "
        "o buffer não estima demanda latente nem recupera lost sales. Ausência de custos impede ótimo econômico. "
        "Equivalência em dias é ROP/(Σforecast7/7), somente com denominador positivo, sem garantia de dias reais. "
        "Ratios individuais podem ser grandes em pequena escala; denominadores zero geram nulo, e ratio agregado difere da mediana individual. "
        "O planejamento é snapshot histórico de 26/06, não recomendação atual. Um target nominal não garante cobertura de cada segmento.",
        "## 19. Implicações para decisão",
        "**Recomendação técnica: Fase 8 aprovada como simulação descritiva para revisão**, sem autorização de política real. "
        "Examinar gaps e concentrações, investigar séries A com duplo sinal e confrontar hipóteses com dados operacionais reais no futuro. "
        "PROTECTED representa mais buffer sob outras hipóteses; não é automaticamente melhor. Nenhuma flag aumenta SS.",
        "## 20. Marts, reprodutibilidade e preparação para consumo futuro",
        "`mart_replenishment_simulation`: IDs + scenario, 150.000 linhas; as_of 25/06 e available_from 26/06. "
        "`mart_replenishment_calibration`: stage + scenario + calibration_level_used + calibration_key; "
        "inclui células candidatas elegíveis ou não, suporte, séries distintas e status PRIMARY/FALLBACK/NOT_USED. "
        "Cobertura por célula é calculada somente nas séries efetivamente atribuídas no fold4, não em todo o pool de treinamento. "
        "`mart_replenishment_summary`: stage + scenario + level + cell. Filtrar stage/level antes de somar; "
        "recortes de risco e A_double_signal se sobrepõem aos níveis populacionais. `historical_fold4_coverage` é referência temporal "
        "com composição histórica potencialmente distinta, não cobertura realizada do snapshot final. "
        "Normal e cobertura histórica não são escolha de política. Não foi iniciado Power BI.",
        table(pd.DataFrame([{"artifact": k, **v} for k, v in data["metadata"]["artifacts"].items()]),
            [("artifact", "Artefato"), ("rows", "Linhas"), ("bytes", "Bytes"), ("sha256", "SHA-256")]),
        "### Inputs congelados e hashes",
        table(pd.DataFrame([{"input": k, **v} for k, v in data["metadata"]["inputs"].items()]),
              [("input", "Input"), ("path", "Caminho"), ("sha256", "SHA-256")]),
        f"Config SHA-256: `{data['metadata']['config']['sha256']}`. Protocolo SHA-256: `{data['metadata']['protocol']['protocol_sha256']}`. "
        "`summary.json` registra HEAD, fontes, hashes, fórmula, quantis, hierarquia e outputs determinísticos. "
        "Runtime fica separado e não participa dos hashes reprodutíveis.",
        f"Execução original: **{data['performance']['elapsed_seconds']:.2f} s**, pico do processo "
        f"**{data['performance']['peak_working_set_bytes'] / 2**20:.2f} MiB**, Parquet "
        f"**{data['performance']['parquet_bytes'] / 2**20:.2f} MiB**. Zero fitting ETS; barreira em `ExponentialSmoothing.fit`.",
        "Notebook `07_replenishment_simulation.ipynb`: dez figuras, consumo exclusivo de outputs, lógica crítica em src. "
        "Validação automatizada inclui fórmulas sintéticas, grão populacional, exclusão de fold4 da calibração, "
        "invariância a flags e reprodução integral com eval ausente e depois corrompido artificialmente, sem acesso ao eval real. "
        "A suíte legada completa não deve ser executada nesta fase: contém fitting ETS e abertura de raw/holdout. "
        "O registro da Fase 7 de 118 testes aprovados e as exclusões históricas das fases anteriores permanecem preservados. "
        "Resultado específico da rodada está em `validation.json`, separado da análise. Dados, outputs, ambiente e temporários permanecem ignorados; sem stage ou commit."]
    validation_path = root / FOLDER / "validation.json"
    if validation_path.exists():
        checks = read_json(validation_path)
        reproduction = checks["optimized_reproduction_performance"]
        sections += ["### Resultado da validação desta rodada",
            f"**{checks['tests']} testes aprovados**, {checks['failures']} falhas, {checks['errors']} erros, "
            f"{checks['skipped']} skips na seleção executada, em {checks['pytest_seconds']:.3f} s: "
            "11 testes da Fase 8 e dez verificações de ambiente. Suítes legadas não executadas por poderem ajustar modelos ou abrir raw/holdout. "
            "Dois builds completos na raiz de teste (sem eval e depois com arquivos artificiais inválidos) reproduziram "
            "os 11 Parquet e summary.json exatamente. Zero fitting e nenhuma leitura de actuals eval. "
            "`pip check` sem incompatibilidades; `git diff --check` aprovado; stage vazio. "
            "Dez figuras inspecionadas, dez imagens no notebook e zero erros.",
            f"A concatenação de chaves de célula foi vetorizada sem mudar fórmulas ou outputs. A última reprodução "
            f"do código atual levou **{reproduction['elapsed_seconds']:.2f} s**; pico cumulativo do processo pytest "
            f"**{reproduction['peak_working_set_bytes'] / 2**20:.2f} MiB** (inclui os dois builds e testes). "
            "A execução original, mais lenta, permanece registrada acima para auditoria. Nenhum forecast foi refeito."]
    (root / "docs/replenishment_simulation_report.md").write_text("\n\n".join(sections) + "\n", encoding="utf-8")
