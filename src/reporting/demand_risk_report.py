"""Relatório da Fase 6: somente outputs de erros já observados dentro de train."""

import json
import pandas as pd

from src.ingestion.source_manifest import ROOT
from src.reporting.forecast_report import markdown_table


def load_outputs(root=ROOT):
    folder=root / "data/outputs/forecast_uncertainty"
    summary=json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    return {"summary":summary,**{name:pd.read_parquet(root/item["path"]) for name,item in summary["artifacts"].items()}}


def write_report(root=ROOT):
    data=load_outputs(root)
    s=data["summary"]
    c=data["calibration"]
    p=data["risk_profile"]
    matrix=data["risk_matrix"]
    metrics={"n_series":"Séries","n_forecasts":"Previsões","actual_total":"D actual",
        "mae":"MAE","rmse":"RMSE","wape":"WAPE","bias":"Bias","bias_pct":"Bias %",
        "error_std":"Desvio erro","p90_absolute_error":"p90 absoluto","p95_absolute_error":"p95 absoluto",
        "underforecast_rate":"Dias subprevistos"}
    perc={"wape","bias_pct","underforecast_rate","train_normalized_sales_share","backtest_actual_share","series_share"}
    sections=["# Fase 6 — Forecast uncertainty & stockout-aware demand risk",
        "## Objetivo e limites de uso",
        "Caracterização empírica de 1.400.000 erros ETS A/N/A já produzidos: 50.000 séries × quatro folds × sete dias. "
        "**Nenhum ajuste foi executado, nenhum point forecast alterado e nenhum arquivo raw aberto pela Fase 6.** "
        "Eval permanece fechado. Target é venda observada normalizada, não demanda latente, unidades físicas ou receita. "
        "Não se estimam lost sales, intervalos probabilísticos, safety stock, reorder point ou compra.",
        "**Corte dos perfis: 25/06/2024; disponíveis a partir de 26/06/2024.** Os forecasts continuam sendo os "
        "backtests prospectivos da Fase 5. Para o diagnóstico desta fase, seus erros são agrupados pelas classes "
        "finais da Fase 3, conhecidas em 25/06, sem recalcular ABC, XYZ, exposição ou flag de censura. "
        "Essa é uma descrição retrospectiva para uma decisão futura: **não é uma reavaliação prospectiva dos folds**, "
        "e os perfis não podem ser usados em origens anteriores. Por isso, tabelas segmentadas podem diferir da "
        "Fase 5, que usava rótulos diferentes em cada origem; o agregado global e o erro de cada série são iguais.",
        "## Inputs e integridade",
        markdown_table(pd.DataFrame([{"input":k,**v} for k,v in s["inputs"].items()]),
            {"input":"Origem","path":"Mart verificado","sha256":"SHA-256"}),
        "Os SHA-256 dos marts são verificados contra os resumos das fases aprovadas. Os resumos têm seu "
        "escopo/fonte conferidos contra a identidade train do manifesto, e seus hashes são registrados para proveniência. "
        "A fase lê apenas esses marts/resumos e o manifesto; não precisa de raw, staging, eval ou novo fitting. "
        "Os campos `source_split`, `as_of`, `available_from` e `analysis_view` documentam o limite temporal dos perfis.",
        "## Fórmulas e perfil de erro",
        "Preserva-se `error = forecast − actual`. Subprevisão: error<0; superprevisão: error>0; erro exatamente "
        "zero é contado separadamente. `underforecast_amount=max(actual−forecast,0)` é derivada, não substitui error. "
        "MAE=Σ|error|/N; RMSE=√(Σerror²/N); WAPE=Σ|error|/Σactual; bias=Σerror/N; bias_pct=Σerror/Σactual. "
        "WAPE/bias_pct ficam nulos se D=0. A média do underforecast positivo é nula quando não há dia subprevisto. "
        "Não há MAPE nem preenchimento de percentuais indefinidos com zero.",
        "`error_std` e `absolute_error_std` são desvios amostrais (`ddof=1`). Quantis usam interpolação linear "
        "tipo 7: p50/p90/p95 de |error| e q10/q25/q50/q75/q90 do erro assinado. Cada perfil tem 28 forecasts, "
        "actual_total/forecast_total, dias/taxas de sub e superprevisão e total/média positiva de underforecast. "
        "As agregações de segmentos usam as observações originais, nunca médias de WAPEs, RMSEs, desvios ou quantis por série.",
        markdown_table(c.loc[c.level.eq("global")],metrics,perc),
        "## Distribuições por série",
        markdown_table(data["series_distributions"],{"metric":"Métrica","n_valid":"Válidos","min":"Mínimo",
            "p05":"p05","p25":"p25","median":"Mediana","p75":"p75","p95":"p95","max":"Máximo"}),
        f"Bias negativo em **{s['n_negative_bias']:,} séries ({s['n_negative_bias']/s['n_series']:.3%})**. "
        "Os quantis acima dão peso igual a cada série; não equivalem à distribuição dos 1,4 milhão de erros agrupados. "
        "Bias negativo, sozinho, não demonstra ruptura, demanda perdida ou estoque insuficiente: pode refletir nível, "
        "ruído, promoção, erro do modelo ou censura, entre outras explicações.",
        "## Persistência temporal do bias",
        "Regra solicitada e preservada após diagnóstico: **bias consolidado <0 E bias negativo em pelo menos "
        "três dos quatro folds**. Não há score ponderado. Cada fold tem sete previsões, sem pesos desiguais. "
        "Um fold com bias zero não conta como negativo. A condição consolidada evita classificar séries cuja "
        "superprevisão em uma janela supera as subprevisões das outras.",
        markdown_table(data["persistence_distribution"],{"negative_bias_fold_count":"Folds negativos",
            "n_series":"Séries","persistent_series":"Persistentes","train_sales":"Venda normalizada train"}),
        f"São **{s['n_persistent']:,} séries persistentes ({s['n_persistent']/s['n_series']:.3%})**. "
        "Das 13.020 séries com três folds negativos, 12.161 também têm bias consolidado negativo; "
        "as 4.368 com quatro folds negativos cumprem ambos os critérios. Isso é persistência observada, não previsão de persistência futura.",
        "Sensibilidade ao número de folds, sem substituir a regra oficial:",
        markdown_table(data["persistence_sensitivity"],{"minimum_negative_folds":"Mínimo folds negativos",
            "n_series":"Séries","series_share":"Participação","double_risk_series":"Com flag censura",
            "train_sales_share":"Venda train"},{"series_share","train_sales_share"}),
        "## Medidas candidatas de incerteza",
        "Desvio do erro mede dispersão ao redor do bias; RMSE incorpora dispersão e deslocamento sistemático. "
        "Para N=28, error_std² = 28/27 × (RMSE² − bias²). Quantis absolutos descrevem magnitude de cauda, "
        "mas perdem direção; os quantis assinados e underforecast_amount preservam essa informação. "
        "Nenhuma dessas medidas é intervalo de previsão, probabilidade calibrada, erro acumulado de lead time ou "
        "fórmula de estoque de segurança. Preservar as quatro como entradas candidatas, com bias separado.",
        markdown_table(data["metric_correlations"].loc[lambda f:f.abc_scope.eq("ALL")&f.method.eq("spearman")],
            {"metric_1":"Medida 1","metric_2":"Medida 2","correlation":"Spearman","n_series":"Séries"}),
        "As medidas são fortemente associadas (Spearman desvio/RMSE ≈0,994), sem equivalência de significado. "
        "**28 observações por série são insuficientes para estabilizar caudas**: no tipo 7, p90 depende sobretudo "
        "das posições 25–26 e p95 das posições 26–27 na ordenação de 28 erros. As amostras agregadas aumentam "
        "o número de observações, mas misturam escalas e dependências de loja/produto/calendário; não são observações independentes."]
    for level,title,dims in [("abc","ABC",{"abc_class":"ABC"}),("xyz","XYZ",{"xyz_class":"XYZ"}),
        ("abc_xyz","ABC × XYZ",{"abc_class":"ABC","xyz_class":"XYZ"}),
        ("stockout_exposure","Exposição à ruptura",{"stockout_exposure":"Exposição"}),
        ("censoring_risk_flag","Flag de possível censura",{"censoring_risk_flag":"Flag"}),
        ("abc_xyz_exposure","ABC × XYZ × exposição",{"abc_class":"ABC","xyz_class":"XYZ","stockout_exposure":"Exposição"})]:
        sections.extend([f"## Calibração descritiva por {title}",markdown_table(c.loc[c.level.eq(level)],{**dims,**metrics},perc)])
    fine=c.loc[c.level.eq("abc_xyz_exposure")]
    sections.extend([f"As {len(fine)} células ABC×XYZ×exposição têm no mínimo {int(fine.n_series.min())} séries "
        f"e {int(fine.n_forecasts.min())} forecasts. Todas superam o critério operacional descritivo declarado "
        f"de {s['minimum_matrix_series_descriptive']} séries. Esse critério serve para não interpretar uma célula minúscula; "
        "não garante independência, precisão probabilística ou transferibilidade. Não foram criadas combinações adicionais.",
        "### Interpretação de disponibilidade e escala",
        "HIGH tem MAE 0,5107, RMSE 0,9377 e desvio 0,9351, superiores a LOW (0,3473; 0,5212; 0,5212). "
        "Seu bias é mais negativo (−0,0701 contra −0,0045), e a frequência de subprevisão é 52,57% contra 48,02%. "
        "Apesar disso, seu WAPE é menor (31,66% contra 43,13%), por diferenças no denominador/escala. "
        "Não se conclui que HIGH é intrinsecamente mais previsível ou que ruptura causou os erros.",
        "Flag=True tem RMSE 0,9101, desvio 0,9081 e bias −0,0600, contra 0,6565, 0,6561 e −0,0215 sem flag. "
        "**A frequência de subprevisão é praticamente igual, ligeiramente menor com flag: 50,09% contra 50,23%.** "
        "A diferença de bias não deve ser descrita como maior número de dias subprevistos; frequência e magnitude são distintas. "
        "A definição da flag de censura da Fase 3 foi preservada integralmente.",
        "## Matriz transparente de dois sinais",
        "`demand_observation_risk_cell` combina censoring_risk_flag e persistent_underforecast_flag: "
        "NEITHER, UNDERFORECAST_ONLY, CENSORING_ONLY, CENSORING_AND_UNDERFORECAST. "
        "NEITHER significa ausência desses dois sinais específicos; pode haver bias negativo não persistente, "
        "incerteza ou ruptura observada. A flag de censura não comprova lost sales. "
        "As diferenças de bias entre células são parcialmente mecânicas, pois bias integra sua definição; "
        "não validam de maneira independente poder preditivo ou causalidade.",
        "Participação de venda principal = soma da venda normalizada dos 90 dias de train na célula / total train. "
        "A coluna de participação dos actuals do backtest usa os 28 dias; os denominadores não se confundem.",
        markdown_table(matrix.loc[matrix.level.eq("risk_cell")],{"demand_observation_risk_cell":"Célula",
            "series_share":"% séries","train_normalized_sales_share":"Venda train","backtest_actual_share":"Venda backtest",**metrics},perc),
        "## Matriz e prioridade ABC",
        markdown_table(matrix.loc[matrix.level.eq("risk_abc")],{"demand_observation_risk_cell":"Célula","abc_class":"ABC",
            "train_normalized_sales_share":"Venda train","backtest_actual_share":"Venda backtest",**metrics},perc),
        "**Duplo sinal: 1.028 séries (2,056%), 1,982% da venda normalizada train e 2,637% dos actuals do backtest.** "
        "A reúne 706 séries, 1,641% da venda train total; B reúne 258, 0,286% da venda train total. "
        "Juntas são 964 séries e 1,927% da venda train. São recortes para estudar na futura simulação, não recomendações de compra. "
        "A + duplo sinal tem bias −0,2500, RMSE 1,0788 e desvio 1,0495. Esses números não estimam demanda perdida.",
        "## Composição XYZ e exposição da matriz",
        markdown_table(matrix.loc[matrix.level.eq("risk_xyz")],{"demand_observation_risk_cell":"Célula","xyz_class":"XYZ",
            "n_series":"Séries","train_normalized_sales_share":"Venda train","error_std":"Desvio erro"},perc),
        markdown_table(matrix.loc[matrix.level.eq("risk_exposure")],{"demand_observation_risk_cell":"Célula","stockout_exposure":"Exposição",
            "n_series":"Séries","train_normalized_sales_share":"Venda train","error_std":"Desvio erro"},perc),
        "Células com censura só aparecem em HIGH, por construção da flag. As combinações ausentes são estruturais, "
        "não classes nulas ou séries descartadas. Essa relação não constitui nova descoberta empírica.",
        "## Duplo sinal e elevada incerteza",
        "Para quantificar sobreposição, usam-se os p75 globais por série de cada uma das quatro medidas, "
        "somente como diagnóstico. Não é criada uma flag de compra, um score ou uma nova célula da matriz. "
        "Os thresholds são conhecidos após 25/06 e não podem retroagir nos folds.",
        markdown_table(data["high_uncertainty_diagnostics"].loc[lambda f:f.group.isin(["CENSORING_AND_UNDERFORECAST","A_DOUBLE","B_DOUBLE"])],
            {"group":"Grupo","metric":"Medida","global_p75_threshold":"p75 global","n_series":"Séries",
             "n_at_or_above_p75":"Acima ou igual p75","share_at_or_above_p75":"Proporção"},{"share_at_or_above_p75"}),
        "São 518 séries com duplo sinal e desvio do erro ≥0,55057; 398 delas em A e 118 em B. "
        "A proporção é 50,39% no duplo sinal e 56,37% em A + duplo sinal. As alternativas RMSE/p90/p95 "
        "também são exibidas para evitar escolher a medida apenas pelo resultado favorável.",
        "## Robustez temporal",
        markdown_table(data["fold_diagnostics"].loc[lambda f:f.level.eq("global")],{"fold_id":"Fold",**metrics},perc),
        markdown_table(data["fold_diagnostics"].loc[lambda f:f.level.eq("stockout_exposure")],
            {"fold_id":"Fold","stockout_exposure":"Exposição","rmse":"RMSE","bias_pct":"Bias %","underforecast_rate":"Dias subprevistos"},perc),
        markdown_table(data["fold_diagnostics"].loc[lambda f:f.level.eq("censoring_risk_flag")],
            {"fold_id":"Fold","censoring_risk_flag":"Flag","rmse":"RMSE","bias_pct":"Bias %","underforecast_rate":"Dias subprevistos"},perc),
        "HIGH tem RMSE maior que LOW e MEDIUM em todos os folds; flag=True também tem RMSE maior que False "
        "nas quatro janelas. Isso sustenta a associação descritiva de magnitude, mas não um sinal de bias universal: "
        "HIGH tem bias positivo nos folds 1 e 3, e flag=True no fold 1. A frequência de subprevisão da flag "
        "é maior nos folds 1–3 e menor no fold 4. O duplo sinal tem bias agregado negativo nos quatro folds, "
        "lembrando que a seleção das séries usa o conjunto desses erros.",
        markdown_table(data["robustness"].loc[lambda f:f.scope.eq("global")],{"scenario":"Cenário",**metrics},perc),
        markdown_table(data["persistence_retention"],{"omitted_fold":"Fold omitido","official_persistent_series":"Persistentes oficiais",
            "still_negative_consolidated":"Mantêm bias<0","negative_in_all_three_remaining":"3 restantes negativos",
            "negative_in_at_least_two_remaining":"≥2 restantes negativos"}),
        "**O sinal do bias global depende do fold 4:** ao omiti-lo, passa de −0,02354 para +0,01029. "
        "Não se deve afirmar subprevisão global uniforme ao longo do tempo. Entretanto, entre as 16.529 séries "
        "persistentes oficiais, 14.974 (90,59%) continuam com bias consolidado negativo sem o fold 4; "
        "ao omitir qualquer outro fold, a retenção do sinal é de 93,39%–94,82%. "
        "Essa verificação não inventa uma regra equivalente para três folds nem substitui a classificação de quatro folds.",
        "A sensibilidade central p1–p99 do erro mantém 98% das observações: RMSE cai de 0,6723 para 0,4705 "
        "e desvio de 0,6719 para 0,4701, mostrando influência importante das caudas. Bias continua negativo. "
        "As quatro células de risco também são comparadas nesse cenário no artefato de robustez. "
        "O duplo sinal mantém bias negativo (−0,1792) e RMSE maior que NEITHER (0,6092 contra 0,4499), "
        "mas fica praticamente empatado com CENSORING_ONLY (0,6102): a ordenação fina de RMSE depende das caudas. "
        "Excluir extremos condicionado ao próprio erro muda o estimando; esses números não substituem o resultado oficial. "
        "Nenhum outlier foi removido dos marts principais.",
        "## Baixa escala e WAPE",
        markdown_table(data["low_scale_diagnostics"],{"group":"Grupo","n_series":"Séries","actual_total":"D total","actual_share":"% actual",
            "persistent_series":"Persistentes","median_wape":"WAPE mediano","p95_wape":"WAPE p95","median_error_std":"Desvio mediano"},
            {"actual_share","median_wape","p95_wape"}),
        "O p05 da soma actual por série é 10,13; inclui empates e 2.501 séries (1,386% da venda do backtest). "
        "Seu WAPE mediano é 61,13%, contra 37,19% nas demais, mas desvio mediano menor: 0,2224 contra 0,3618. "
        "Há 230 persistentes nesse recorte. Nenhuma série é escolhida como risco somente pelo WAPE. "
        "Nenhum D por série é zero (mínimo 1,1); há 263 série×fold com D=0, cujos percentuais continuam nulos.",
        "## Atividade promocional — análise complementar",
        markdown_table(data["activity_associations"],{"abc_scope":"Escopo ABC","metric":"Métrica",
            "spearman_with_activity_rate":"Spearman com activity_rate","n_series":"Séries"}),
        "Não se criaram bandas arbitrárias de atividade. Associação contínua com MAE/desvio é fraca no conjunto "
        "(≈−0,049/−0,046); em A é ≈−0,152. A comparação entre séries não equivale à associação diária "
        "da Fase 2 entre atividade, venda e ruptura. Não há uplift causal, novo modelo ou decisão baseada nesse sinal. "
        "Mantém-se como complemento e limitação, sem alterar a matriz.",
        "## Exemplos reproduzíveis",
        markdown_table(data["example_selection"],{"selection_rule":"Regra","store_id":"Loja","product_id":"Produto","xyz_class":"XYZ",
            "actual_total":"D 28 dias","bias":"Bias","error_std":"Desvio erro","underforecast_rate":"Dias subprevistos","stockout_rate":"Ruptura histórica"},
            {"underforecast_rate","stockout_rate"}),
        "Para cada célula entre séries A, escolhe-se a série mais próxima do desvio mediano daquela célula. "
        "Outros exemplos: maior desvio em A, maior taxa de subprevisão em A, menor MAE entre LOW. "
        "Todos os empates são resolvidos por loja/produto. O último exemplo é de baixa exposição relativa, "
        "não ausência de ruptura, e tem baixa escala. Exemplos não definem thresholds nem representam universalmente as células.",
        "## Artefatos, notebook e reprodução",
        markdown_table(pd.DataFrame([{"name":k,**v} for k,v in s["artifacts"].items()]),{"name":"Artefato","path":"Caminho","rows":"Linhas","sha256":"SHA-256"}),
        "Os marts de incerteza e risco têm grão store_id+product_id. O mart de calibração tem grão "
        "`level` + dimensões aplicáveis; contém 48 linhas, com dimensões não aplicáveis nulas. Filtrar level antes de agregar. "
        "Esses nulos estruturais não existem nas classes do mart de risco. Não há score numérico ou fórmula de safety stock.",
        "```powershell\n.\\.venv\\Scripts\\python.exe scripts/build_forecast_risk_profile.py\n"
        ".\\.venv\\Scripts\\python.exe scripts/render_forecast_uncertainty.py\n"
        ".\\.venv\\Scripts\\python.exe -m pytest --basetemp=.tmp/pytest-phase6-final --deselect=tests/test_raw_quality.py::test_raw_files_manifest_hashes_and_schema --deselect=tests/test_raw_quality.py::test_staging_reproducible_from_full_raw\n"
        ".\\.venv\\Scripts\\python.exe -m pip check\ngit diff --check\ngit status\n```",
        "Notebook `05_forecast_uncertainty_and_risk.ipynb`: dez figuras consumindo somente outputs; "
        "nenhuma transformação crítica exclusiva de célula. A reprodução compara todos os Parquet e summary.json "
        "em uma raiz sem raw/eval e bloqueia chamadas de ajuste ETS. Tempo e pico de memória não entram na igualdade dos hashes.",
        "## Limitações e implicações para a próxima decisão",
        "Quatro folds não cobrem outras estações ou regimes. As 28 observações limitam caudas por série; "
        "amostras agregadas misturam escalas e dependências. Agrupar por labels de 25/06 é válido para diagnóstico "
        "e preparação de decisão posterior, não prova prospectiva em origens anteriores. A matriz combina sinais "
        "observados e parcialmente definidos pelo próprio erro, sem causalidade ou validação externa de risco futuro. "
        "O bias global é sensível à última janela e medidas quadráticas às caudas. Não corrigir forecasts a partir desses sinais.",
        "Preservar error_std, RMSE, p90/p95 absolutos, bias, quantis assinados e underforecast_amount como possíveis "
        "entradas da futura simulação. Nenhuma medida foi escolhida para uma fórmula, e não se agregou erro de lead time "
        "sem testar dependência temporal. A/B com duplo sinal merecem investigação na etapa que vier a ser autorizada, "
        "sem compra, lost sales, reposição ou Power BI nesta entrega."])
    folder=root / "data/outputs/forecast_uncertainty"
    performance=json.loads((folder / "performance.json").read_text(encoding="utf-8"))
    sections.append(f"Execução tabular: {performance['seconds']:.2f} s; pico {performance['peak_working_set_bytes']/2**20:.2f} MiB; "
        f"Parquet: {performance['parquet_bytes']:,} bytes. Nenhum novo fitting. HEAD de partida `6a7ccec`; sem commit.")
    if (folder / "validation.json").exists():
        v=json.loads((folder / "validation.json").read_text(encoding="utf-8"))
        sections.extend(["## Validação final e recomendação",v["result"],
            "**Recomendação técnica: Fase 6 aprovada para revisão como diagnóstico descritivo.** "
            "A regra de persistência proposta foi mantida; suas sensibilidades e limites estão explícitos. "
            "Aprovação desta entrega não autoriza holdout, reposição, estimativa de censura ou avanço automático."])
    (root / "docs/forecast_uncertainty_and_risk_report.md").write_text("\n\n".join(sections)+"\n",encoding="utf-8")
