"""Relatório final gerado exclusivamente dos outputs congelados e avaliados."""

import pandas as pd

from src.forecasting.holdout import ROOT, FOLDER, read_json
from src.reporting.forecast_report import markdown_table


def load_outputs(root=ROOT):
    s=read_json(root/FOLDER/"summary.json")
    data={"summary":s,"protocol":read_json(root/FOLDER/"protocol.json"),
        "population_performance":read_json(root/FOLDER/"population_performance.json"),
        "evaluation_performance":read_json(root/FOLDER/"evaluation_performance.json"),
        "opening":read_json(root/FOLDER/"eval_opening.json"),
        **{name:pd.read_parquet(root/item["path"]) for name,item in s["artifacts"].items()}}
    pairs=pd.read_parquet(root/"data/processed/mart_model_comparison.parquet",filters=[("level","=","fold")])
    frames=[]
    for suffix,model in [("ets","ets_ana"),("seasonal_naive","seasonal_naive")]:
        frame=pairs[["fold_id",*[m+"_"+suffix for m in ["mae","rmse","wape","bias","bias_pct"]]]].copy()
        frame.columns=["fold_id","mae","rmse","wape","bias","bias_pct"]
        frame["model"]=model
        frames.append(frame)
    data["backtest_folds"]=pd.concat(frames,ignore_index=True)
    for name in ["assessment","validation","notebook_performance"]:
        path=root/FOLDER/(name+".json")
        if path.exists():
            data[name]=read_json(path)
    return data


def write_report(root=ROOT):
    d=load_outputs(root)
    s=d["summary"]
    comparison=d["model_comparison"]
    cols={"model":"Modelo","n_series":"Séries","n_forecasts":"Previsões","actual_total":"Actual total",
        "mae":"MAE","rmse":"RMSE","wape":"WAPE","bias":"Bias","bias_pct":"Bias %","underforecast_rate":"Dias subprevistos"}
    pct={"wape","bias_pct","underforecast_rate","negative_holdout_bias_rate",
        "improvement_mae","improvement_rmse","improvement_wape","improvement_p25","improvement_median","improvement_p75"}
    sections=["# Fase 7 — Final holdout evaluation",
        "## Objetivo, autorização e protocolo congelado",
        "Esta é a **primeira abertura analítica autorizada de eval**, após aprovação e commit das fases 0–6 em "
        "`d6681aa`. Verificações anteriores de ingestão/schema não constituíram avaliação preditiva. "
        "O holdout 26/06–02/07/2024 foi reservado para avaliar a metodologia, sem seleção, tuning ou recalibração. "
        "[Protocolo registrado antes da abertura](final_holdout_protocol.md). Target: venda observada normalizada, "
        "não demanda latente, receita ou unidades físicas. Esta fase não implementa reposição.",
        "ETS A/N/A usa todo train de 28/03 a 25/06: 90 dias, sazonalidade aditiva de período sete, sem tendência, "
        "estados iniciais estimados, SLSQP/maxiter=200/ftol=1e-6/use_brute=False/remove_bias=False, uma thread numérica. "
        "Previsão direta de sete passos, sem atualização no horizonte. Seasonal Naive usa exclusivamente 19–25/06. "
        "Reutilizou-se a função ETS congelada, incluindo fallback e projeção de negativos em zero.",
        f"As 700.000 previsões sem actuals foram finalizadas em `{d['population_performance']['finished_utc']}`; "
        f"a abertura analítica foi registrada em `{d['opening']['first_analytical_opening_started_utc']}`. "
        f"Hash anterior à abertura: `{s['prediction_sha256']}`. "
        "Releituras para testes/reprodução não criam outra seleção de modelo: a metodologia e as previsões permanecem iguais.",
        "## Integridade e proveniência",
        markdown_table(pd.DataFrame([s["integrity"]]),{"rows":"Linhas eval","n_series":"Séries","n_dates":"Datas",
            "start":"Início","end":"Fim","unique_grain":"Grão único","schema_and_hash_verified":"Schema/hash","sha256":"SHA-256 eval"}),
        f"SHA-256 train: `{s['source_hashes']['train']}`. SHA-256 protocolo: `{s['protocol_sha256']}`. "
        "Foram verificados os 53 artefatos protegidos das fases 3–6; nenhum foi sobrescrito. Cobertura de eval "
        "coincide exatamente com as 50.000 séries conhecidas. Labels e métricas históricas vêm dos marts de 25/06, "
        "agora disponíveis legitimamente antes da origem 26/06. Não foram recalculados usando eval.",
        "## Métricas e comparação global",
        "Erro=forecast−actual. MAE=Σ|e|/N; RMSE=√(Σe²/N); WAPE=Σ|e|/Σactual; bias=Σe/N; "
        "bias_pct=Σe/Σactual. Percentuais com denominador zero são nulos. Sem MAPE. Agregação pelas observações, "
        "sem média de WAPEs ou RMSEs por série. Improvement=(SN−ETS)/SN para MAE/RMSE/WAPE; referência zero "
        "mantém improvement nulo. Não há improvement relativo de bias assinado.",
        markdown_table(comparison.loc[comparison.level.eq("global")],cols,pct),
        markdown_table(d["paired_comparison"].loc[lambda x:x.level.eq("global")],
            {"improvement_mae":"Improvement MAE","improvement_rmse":"Improvement RMSE","improvement_wape":"Improvement WAPE"},pct),
        "Não existe threshold prévio de aceitabilidade operacional do bias. Sua direção/magnitude são reportadas, "
        "sem declarar aceitabilidade para uma política de estoque ainda inexistente.",
        "## Comparação com os quatro folds",
        markdown_table(d["backtest_folds"],{"model":"Modelo","fold_id":"Fold","mae":"MAE","rmse":"RMSE","wape":"WAPE","bias":"Bias","bias_pct":"Bias %"},pct),
        markdown_table(d["backtest_comparison"],{"model":"Modelo","metric":"Métrica","backtest_pooled":"Agregado backtest",
            "fold_mean":"Média folds","fold_min":"Mínimo","fold_max":"Máximo","fold_std_ddof1":"Desvio amostral",
            "fold4":"Fold 4","holdout":"Holdout","change_vs_fold4":"Delta fold 4","change_vs_pooled":"Delta agregado",
            "outside_fold_range":"Fora do intervalo"}),
        "Na tabela de estabilidade, percentuais estão em proporção (0,01=1 ponto percentual); deltas são diferenças "
        "assinadas. Mínimo/máximo dos quatro folds não é intervalo de confiança. Apenas uma semana final foi avaliada."]
    for level,title,dimension in [("abc","ABC",["abc_class"]),("xyz","XYZ",["xyz_class"]),
        ("abc_xyz","ABC × XYZ",["abc_class","xyz_class"]),("stockout_exposure","Exposição histórica",["stockout_exposure"]),
        ("censoring_risk_flag","Possível censura histórica",["censoring_risk_flag"]),
        ("persistent_underforecast_flag","Persistência pré-holdout",["persistent_underforecast_flag"]),
        ("risk_cell","Matriz de risco pré-holdout",["demand_observation_risk_cell"]),
        ("a_double_signal","As 706 séries A com duplo sinal",[])]:
        sections.extend([f"## {title}",markdown_table(comparison.loc[comparison.level.eq(level)],{**{k:k for k in dimension},**cols},pct)])
    sections.extend(["## Persistência: retenção prospectiva do sinal",
        markdown_table(d["persistence_retention"],{"persistent_underforecast_flag":"Flag prévia","n_series":"Séries",
            "negative_holdout_bias_series":"Bias holdout negativo","negative_holdout_bias_rate":"Proporção","zero_actual_series":"Actual zero"},pct),
        "Regra histórica preservada: bias consolidado negativo e ≥3 dos quatro folds com bias negativo. "
        "As 16.529 séries foram definidas antes de eval. A matriz cruza essa flag com possível censura: "
        "NEITHER, UNDERFORECAST_ONLY, CENSORING_ONLY, CENSORING_AND_UNDERFORECAST. Os 1.028 casos de duplo sinal "
        "e os 706 casos A não foram selecionados novamente. A retenção de sinal em sete dias é evidência "
        "descritiva; não significa demanda perdida, causalidade ou insuficiência comprovada de estoque.",
        "## Incerteza histórica versus erro futuro",
        markdown_table(d["uncertainty_association"],{"historical_metric":"Medida histórica","holdout_metric":"Erro holdout",
            "n_series":"Séries","spearman":"Spearman"}),
        markdown_table(d["uncertainty_quartiles"],{"historical_metric":"Medida histórica","historical_quartile":"Quartil",
            "cut_q25":"Corte q25","cut_q50":"Corte q50","cut_q75":"Corte q75",**cols},pct),
        "Cortes calculados e registrados exclusivamente nos perfis históricos antes da abertura: empates ficam "
        "juntos, sem forçar tamanhos iguais. Associações podem refletir escala de venda e dependência entre séries. "
        "Não se convertem em intervalo preditivo, nível de serviço ou fórmula de estoque; nenhuma medida foi recalibrada.",
        "## Baixa escala",
        markdown_table(d["low_scale"],{"historical_low_scale":"Baixa escala histórica",**cols},pct),
        f"Baixa escala usa actual_total histórico ≤10,13 nos 28 dias da Fase 6; não usa um novo corte de eval. "
        f"Há {s['zero_actual_series']} séries com actual total zero no holdout; seus WAPE/bias_pct ficam nulos. "
        "Métricas absolutas acompanham WAPE; nenhum outlier foi removido e não se define risco somente pelo percentual.",
        "## Ruptura contemporânea — análise separada",
        markdown_table(d["contemporary_stockout"],{"eval_stockout":"Ruptura no próprio dia eval",**cols},pct),
        "Este agrupamento usa stock_hour6_22_cnt>0 observado **depois** das previsões, somente para descrição. "
        "É por observação: uma série pode participar dos dois grupos, cujas contagens de séries não são aditivas. "
        "Não é validação prospectiva de uma nova feature. Não modifica forecast, exposição/flag histórica ou thresholds, "
        "e não permite estimar lost sales.",
        "## Exemplos e distribuição de vantagem por série",
        markdown_table(d["example_forecasts"][["selection_rule","store_id","product_id"]].drop_duplicates(),
            {"selection_rule":"Regra da Fase 6","store_id":"Loja","product_id":"Produto"}),
        "Foram reutilizados todos os sete exemplos da Fase 6, sem seleção por resultado interessante em eval. "
        "Eles são ilustrativos, não amostra representativa; escalas e denominadores diferem.",
        markdown_table(d["win_rates"],{"metric":"Métrica","valid_series":"Séries válidas","ets_wins":"ETS vence",
            "sn_wins":"SN vence","ties":"Empates","undefined":"Indefinidas","valid_improvements":"Improvement válido",
            "improvement_p25":"p25","improvement_median":"Mediana","improvement_p75":"p75"},pct),
        "Empates usam atol=1e-12/rtol=1e-10, preservando a Fase 5. Comparação direta pode ser definida quando "
        "improvement relativo não é (referência zero); por isso os denominadores são separados.",
        "## Fallback, clipping e custo",
        f"{s['n_fits']:,} ajustes solicitados; {s['n_fallbacks']} fallbacks; razões: `{s['fallback_reasons']}`. "
        f"Clipping negativo em {s['negative_clipped_forecasts']} forecasts ETS, envolvendo {s['negative_clipped_series']} séries. "
        "Modelo solicitado/usado, motivo, forecast matemático original e indicador de clipping permanecem por linha.",
        f"Ajustes: {d['population_performance']['fit_seconds']:.2f} s; população com I/O: "
        f"{d['population_performance']['population_seconds']:.2f} s; avaliação: {d['evaluation_performance']['evaluation_seconds']:.2f} s. "
        f"Pico população: {d['population_performance']['peak_working_set_bytes']/2**20:.2f} MiB; "
        f"pico avaliação: {d['evaluation_performance']['peak_working_set_bytes']/2**20:.2f} MiB. "
        f"Parquet de avaliação: {d['evaluation_performance']['parquet_bytes']:,} bytes; previsões pré-eval: "
        f"{d['population_performance']['prediction_bytes']:,} bytes. Limite DuckDB não equivale à memória do processo inteiro.",
        "## Artefatos e reprodução",
        markdown_table(pd.DataFrame([{"name":k,**v} for k,v in s["artifacts"].items()]),
            {"name":"Artefato","path":"Caminho","rows":"Linhas","sha256":"SHA-256"}),
        "Grãos: forecast = dt+loja+produto+modelo (700.000 linhas); série = loja+produto+modelo (100.000); "
        "comparação = level+dimensões aplicáveis+modelo. Filtrar level; dimensões não aplicáveis são nulos estruturais. "
        "A_DOUBLE é subconjunto adicional e não deve ser somado aos níveis populacionais. "
        "O mart de comparação guarda métricas de ambos os modelos; paired_comparison guarda improvements pareados.",
        "```powershell\n# Somente primeira execução autorizada, antes de abrir eval:\n"
        ".\\.venv\\Scripts\\python.exe scripts/run_final_holdout.py --fit-only\n"
        "# Reproduzir avaliação sem repetir ajustes:\n"
        ".\\.venv\\Scripts\\python.exe scripts/run_final_holdout.py --evaluate-only\n"
        ".\\.venv\\Scripts\\python.exe scripts/render_final_holdout.py\n"
        ".\\.venv\\Scripts\\python.exe -m pytest --basetemp=.tmp/pytest-phase7-final\n"
        ".\\.venv\\Scripts\\python.exe -m pip check\ngit diff --check\ngit status\n```",
        "O runner recusa nova execução se existem previsões, parcial ou execução registrada. A avaliação é "
        "reproduzida em raiz sem train, com fitting bloqueado; hashes dos Parquet e summary.json devem coincidir. "
        "Tempos/timestamps ficam separados. Código congelado e 53 artefatos anteriores são verificados.",
        "## Limitações e conclusão",
        "Uma única semana não cobre sazonalidades longas, mudanças de regime ou condições operacionais futuras. "
        "Erros são medidos contra venda possivelmente censurada, não demanda latente. Classes históricas são "
        "conhecidas na origem, mas relações prospectivas são descritivas, com dependência entre lojas/produtos/dias. "
        "As medidas de incerteza partem de 28 erros por série; Spearman e quartis podem refletir escala. "
        "Eval deixou de ser holdout intocado: não pode orientar retuning e depois ser apresentado como novo teste "
        "independente. Nova seleção exigiria desenho de validação futuro. Nenhuma política de estoque foi criada."])
    if "assessment" in d:
        sections.extend([f"**Classificação: {d['assessment']['classification']}.**",d["assessment"]["reasoning"],d["assessment"]["risk_interpretation"]])
    if "notebook_performance" in d:
        sections.append(f"Notebook executado: dez figuras, {d['notebook_performance']['seconds']:.2f} s, "
            f"{d['notebook_performance']['notebook_bytes']:,} bytes; sem ajustes ou leitura de raw nas células.")
    if "validation" in d:
        sections.extend(["## Validação final",d["validation"]["result"]])
    (root/"docs/final_holdout_evaluation_report.md").write_text("\n\n".join(sections)+"\n",encoding="utf-8")
