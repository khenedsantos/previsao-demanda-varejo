"""Relatório populacional a partir dos resultados auditáveis, sem refazer ajustes."""

import json
import pandas as pd

from src.ingestion.source_manifest import ROOT
from src.reporting.forecast_report import markdown_table


def write_report(root=ROOT):
    folder=root / "data/outputs/statistical_forecasting"
    def read(name):
        return json.loads((folder / name).read_text(encoding="utf-8"))
    summary=read("summary.json")
    population=read("population_performance.json")
    performance=read("comparison_performance.json")
    benchmark=read("benchmark.json")
    metrics=pd.DataFrame(summary["metrics"])
    pairs=pd.DataFrame(summary["comparisons"])
    sections=["# Fase 5 — Comparação populacional ETS A/N/A versus Seasonal Naive",
        "## Escopo e proveniência",
        "Execução autorizada de **50.000 séries × quatro folds = 200.000 ajustes solicitados**, "
        "com sete previsões por ajuste. Somente A/N/A foi executado nesta continuação. "
        "O limite de engenharia inicial de 30 minutos foi explicitamente revogado pelo usuário. "
        "O benchmark anterior permanece como proveniência; não foi repetido. HEAD de partida: `4dfaa9d`; sem commit nesta fase.",
        "Target `sale_amount`: **venda observada normalizada**, não demanda latente, unidades físicas ou receita. "
        "Eval não participa de ajuste, segmentação, métricas, escolha, exemplos ou notebook. "
        "A verificação de fonte seleciona exclusivamente a entrada train do manifesto. "
        "Os snapshots prospectivos e forecasts Seasonal Naive da Fase 4 são verificados por SHA-256 e reutilizados, "
        "sem duplicar o mart de forecasts daquela fase.",
        markdown_table(pd.DataFrame(summary["folds"]),{"fold_id":"Fold","cutoff_date":"Cutoff", "history_days":"Dias de histórico",
            "forecast_origin":"Origem","test_end":"Último target"}),
        "Origem é o primeiro dia previsto, antes de observar sua venda. Históricos começam em 28/03/2024; "
        "o filtro até o cutoff acontece na SQL antes da agregação. Actuals futuros só são unidos depois do forecast pronto. "
        "Não se usa a segmentação full-train dos 90 dias nas decisões prospectivas.",
        "## Modelo, fallback e clipping",
        "Holt-Winters A/N/A: sem tendência; sazonalidade aditiva; `seasonal_periods=7`; inicialização estimada. "
        "SLSQP, `maxiter=200`, `ftol=1e-6`, `use_brute=False`, `remove_bias=False`, sem Box-Cox. "
        "O módulo `ets.py` e sua configuração permanecem os mesmos do benchmark. Não houve tuning ou avaliação de A/A/A nesta execução.",
        "Fallback Seasonal Naive usa somente os últimos sete dias disponíveis. Motivos possíveis: histórico constante, "
        "sazonal insuficiente, não convergência, forecast não finito ou exceção numérica de ajuste. Histórico inválido bloqueia "
        "o cálculo. `model_requested`, `model_used`, `fallback_flag`, `fallback_reason`, convergência e avisos são preservados. "
        "O candidato é avaliado incluindo fallback, sem descartar séries.",
        "Projeção de negativos em zero preserva `forecast_unclipped` e `negative_clipped`. Não altera o histórico "
        "nem representa falha. A magnitude abaixo é o aumento da previsão provocado exclusivamente por essa projeção."]
    diag=pd.DataFrame(summary["fit_diagnostics"])
    sections.append(markdown_table(diag.loc[diag.level.isin(["global","fold"])],{
        "level":"Nível","fold_id":"Fold","n_fits":"Solicitados","fallback_fits":"Fallback", "fallback_rate":"Taxa fallback",
        "clipped_forecasts":"Forecasts clipping","clipped_fits":"Ajustes com clipping","clipping_rate":"Taxa clipping",
        "minimum_unclipped":"Menor original","mean_clip_magnitude":"Magnitude média","total_upward_projection":"Projeção total"},
        {"fallback_rate","clipping_rate"}))
    sections.append("Motivos observados: "+("nenhum fallback populacional." if not summary["fallback_reasons"] else
        "\n\n"+markdown_table(pd.DataFrame(summary["fallback_reasons"]),{"fold_id":"Fold","fallback_reason":"Motivo","n_fits":"Ajustes"})))
    sections.extend(["## Métricas e denominadores",
        "Para e = forecast − actual, N = número de previsões e D = soma(actual): MAE = soma(abs(e))/N; "
        "RMSE = sqrt(soma(e²)/N); WAPE = soma(abs(e))/D; bias = soma(e)/N; bias_pct = soma(e)/D. "
        "Bias negativo significa subprevisão. WAPE/bias_pct são nulos quando D=0; os erros absolutos continuam definidos. "
        "Não há MAPE. Consolidar significa somar erros e actuals, nunca tirar média ingênua dos WAPEs ou RMSEs das séries.",
        "Melhoria = (Seasonal Naive − ETS) / Seasonal Naive, somente para MAE/RMSE/WAPE. "
        "Referência zero torna a melhoria indefinida. Não há melhoria relativa de bias assinado. "
        "`mart_model_comparison` guarda os dois valores, somas suficientes, denominadores, melhoria e vencedor pareados. "
        "Dimensões não aplicáveis ficam nulas; sempre filtrar `level` antes de agregar."])
    columns={"model":"Modelo","n_forecasts":"N","actual_sum":"D","mae":"MAE","rmse":"RMSE","wape":"WAPE","bias":"Bias","bias_pct":"Bias %"}
    improvement={"improvement_mae":"Ganho MAE","improvement_rmse":"Ganho RMSE","improvement_wape":"Ganho WAPE"}
    percentages={"wape","bias_pct",*improvement}
    sections.extend(["## Global",markdown_table(metrics.loc[metrics.level.eq("global")],columns,percentages),
        markdown_table(pairs.loc[pairs.level.eq("global")],improvement,percentages)])
    for level,title,dims in [("fold","Quatro folds",{"fold_id":"Fold"}),
        ("abc","ABC",{"abc_class":"ABC"}),("xyz","XYZ",{"xyz_class":"XYZ"}),
        ("abc_xyz","ABC × XYZ",{"abc_class":"ABC","xyz_class":"XYZ"}),
        ("stockout_exposure","Exposição à ruptura",{"stockout_exposure":"Exposição"}),
        ("censoring_risk_flag","Flag de possível censura",{"censoring_risk_flag":"Flag"})]:
        sections.extend([f"## {title}",
            markdown_table(metrics.loc[metrics.level.eq(level)].sort_values([*dims,"model"]),{**dims,**columns},percentages),
            markdown_table(pairs.loc[pairs.level.eq(level)].sort_values(list(dims)),{**dims,**improvement},percentages)])
    sections.append("Vitórias por fold: "+json.dumps(summary["fold_wins"],ensure_ascii=False)+". "
        "Todos os segmentos predefinidos são exibidos, incluindo A/B, AX/AY/AZ, BX/BY/BZ, HIGH e flag=True, independentemente do sinal do resultado.")
    stability=pd.read_parquet(folder / "fold_stability.parquet")
    sections.extend(["## Estabilidade entre folds",
        markdown_table(stability.loc[stability.level.eq("global")],{"model":"Modelo","wape_mean":"Média WAPE","wape_std":"Desvio WAPE",
            "wape_min":"Mínimo WAPE","wape_max":"Máximo WAPE","wape_cv":"CV WAPE","bias_pct_std":"Desvio bias %"},
            {"wape_mean","wape_std","wape_min","wape_max","wape_cv","bias_pct_std"}),
        "Desvio amostral, ddof=1, sobre quatro folds. Não é intervalo de confiança; média por fold não substitui WAPE global. "
        "O Parquet de estabilidade também contém os segmentos prospectivos e as cinco métricas.",
        "## Bias por série",
        "Os 28 dias são agregados por série antes dos quantis; séries têm peso igual. "
        "Bias global e por ABC/XYZ/exposição/flag constam nas tabelas anteriores. Nenhuma correção posterior de bias foi aplicada."])
    bias=[]
    for row in summary["bias_distribution"]:
        bias.append({"model":row["model"],"negative":row["negative_bias_series"],"fraction":row["negative_bias_fraction"],
            **{f"bias_{q}":v for q,v in zip(["p05","p25","median","p75","p95"],row["bias_quantiles"])},
            **{f"pct_{q}":v for q,v in zip(["p05","p25","median","p75","p95"],row["bias_pct_quantiles"])}})
    sections.append(markdown_table(pd.DataFrame(bias),{"model":"Modelo","negative":"Séries bias<0","fraction":"Proporção",
        "bias_p25":"Bias p25","bias_median":"Bias mediano","bias_p75":"Bias p75",
        "pct_p05":"Bias % p05","pct_median":"Bias % mediano","pct_p95":"Bias % p95"},
        {"fraction","pct_p05","pct_median","pct_p95"}))
    sections.extend(["## Win rate pareado por série",
        "Global agrega os quatro folds por série. ABC/XYZ agregam cada série apenas nos folds em que pertencia à classe "
        "prospectiva correspondente: uma série pode aparecer em várias classes; as contagens por classe não são aditivas. "
        "Não se atribui retrospectivamente o rótulo do último fold ou do train completo. "
        "Empate numérico: atol=1e-12, rtol=1e-10. Win rate e materialidade não constituem critérios isolados de aprovação.",
        markdown_table(pd.DataFrame(summary["win_rates"]),{"level":"Nível","segment":"Classe","metric":"Métrica",
            "n_series_cases":"Casos","valid_cases":"Válidos","undefined_cases":"Indefinidos","min_folds":"Mín. folds","max_folds":"Máx. folds",
            "ets_count":"ETS vence","seasonal_naive_count":"SN vence","tie_count":"Empata","ets_rate":"Taxa ETS"},{"ets_rate"}),
        "## Distribuição da melhoria e materialidade",
        "Cada série recebe o mesmo peso e agrega os quatro folds. Percentuais a seguir são descritivos; "
        "não configuram automaticamente uma política. MAE e WAPE têm a mesma melhoria por série quando D>0.",
        markdown_table(pd.DataFrame(summary["materiality"]),{"metric":"Métrica","valid_series":"Séries válidas","undefined_reference":"Referência indefinida",
            "p25":"p25","median":"Mediana","p75":"p75","positive_fraction":">0","improvement_ge_01":"≥1%",
            "improvement_ge_05":"≥5%","improvement_ge_10":"≥10%","decline_le_minus_01":"≤−1%",
            "decline_le_minus_05":"≤−5%","decline_le_minus_10":"≤−10%"},
            {"p25","median","p75","positive_fraction","improvement_ge_01","improvement_ge_05","improvement_ge_10",
             "decline_le_minus_01","decline_le_minus_05","decline_le_minus_10"}),
        "## Potencial híbrido sem consultar o próprio erro futuro",
        "Regra definida antes da leitura dos resultados populacionais: exigir pelo menos dois folds anteriores concluídos "
        "no segmento ABC×XYZ, todos com melhoria de WAPE, nenhum com perda de RMSE e magnitude do bias consolidado "
        "anterior não maior que a de SN. Caso contrário, escolher SN. Os dois primeiros folds usam SN; "
        "a classe do fold corrente vem do snapshot conhecido na origem. Nenhuma escolha por série ou ajuste da regra a posteriori. "
        "Isso é análise de potencial, não política operacional final.",
        markdown_table(pd.DataFrame(summary["hybrid_metrics"]),{"level":"Nível","fold_id":"Fold","n_forecasts":"N","actual_sum":"D",
            "mae":"MAE","rmse":"RMSE","wape":"WAPE","bias":"Bias","bias_pct":"Bias %"},percentages),
        markdown_table(pd.read_parquet(folder / "hybrid_choices.parquet"),{"fold_id":"Fold","abc_class":"ABC","xyz_class":"XYZ",
            "completed_folds":"Folds anteriores","model_used":"Escolha analítica","reason":"Motivo"}),
        "## Exemplos e baixa escala",
        markdown_table(pd.DataFrame(summary["examples"]),{"selection_rule":"Regra","fold_id":"Fold","store_id":"Loja","product_id":"Produto",
            "abc_class":"ABC","xyz_class":"XYZ","actual_sum":"D","wape_seasonal_naive":"WAPE SN","wape_ets":"WAPE ETS",
            "improvement_wape":"Ganho WAPE","bias_seasonal_naive":"Bias SN","bias_ets":"Bias ETS"},
            {"wape_seasonal_naive","wape_ets","improvement_wape"}),
        "Regras no último fold: maior ganho/piora WAPE em AX, maior ganho em AZ, maior redução de subprevisão mantendo "
        "bias não positivo, maior aumento da subprevisão e maior piora WAPE geral. Desempate por IDs. "
        "Fallback só é exemplificado se existir, na origem mais recente com ocorrência. Extremos descritivos, não representativos.",
        markdown_table(pd.DataFrame(summary["denominator_diagnostics"]),{"level":"Nível","n_pairs":"Pares",
            "zero_denominator_pairs":"D=0","minimum_positive_actual_sum":"Menor D positivo","zero_reference_mae":"MAE SN zero",
            "undefined_improvement_wape":"Ganho WAPE indefinido"}),
        "Pequenos denominadores amplificam WAPE e sua variação. Os nulos permanecem visíveis; nenhum caso é excluído de MAE/RMSE/bias.",
        "## Benchmark preservado e custo real",
        "Amostra inicial: 135 séries, cinco em cada ABC×XYZ×tercil de escala conhecido no primeiro corte, "
        "selecionadas por hash de semente+IDs; quatro folds e 540 ajustes por configuração. A/N/A era o candidato "
        "principal antes dos erros. A/A/A foi apenas medido no benchmark anterior, sem nova execução. "
        "Projeção ponderada pela população dos estratos: 29,99 minutos de ajustes A/N/A; "
        "1,25 × ajuste projetado + 92,88 s de overhead estimado = **39,03 minutos**. "
        "A margem de 25% não é intervalo estatístico. Benchmark: 21,03 s, pico 528,20 MiB; zero fallback em ambas as amostras.",
        markdown_table(pd.DataFrame(benchmark["results"]),{"specification":"Configuração no benchmark",
            "n_fits":"Ajustes","mean_seconds_per_fit":"Média s/ajuste","p95_seconds_per_fit":"p95 s/ajuste",
            "projected_fit_seconds_200000":"Ajustes projetados s","projected_total_with_margin_seconds":"Total projetado s",
            "fallback_count":"Fallback","failure_count":"Falhas","negative_clipped_forecasts":"Clipping"}),
        f"Amostra SHA-256: `{benchmark['sample_sha256']}`. Benchmark JSON SHA-256: "
        f"`{summary['benchmark_sha256']}`. Não confundir seus resultados de custo com as métricas populacionais desta entrega.",
        f"População: **{population['population_seconds']/60:.3f} min**; ajustes: {population['fit_seconds']/60:.3f} min; "
        f"overhead populacional: {population['population_overhead_seconds']:.3f} s. "
        f"Comparação: {performance['comparison_seconds']:.3f} s. "
        f"**População + comparação: {performance['population_plus_comparison_seconds']/60:.3f} min**, "
        f"com {performance['overhead_population_plus_comparison_seconds']:.3f} s de overhead total. "
        "Esses tempos não incluem desenvolvimento, testes ou renderização posterior do notebook.",
        f"Início UTC: {population['started_utc']}; fim populacional UTC: {population['finished_utc']}. "
        f"Pico do processo de ajustes: {population['peak_working_set_bytes']/2**20:.2f} MiB; "
        f"pico do processo de comparação: {performance['comparison_peak_working_set_bytes']/2**20:.2f} MiB. "
        f"Parquet populacionais e auxiliares: {performance['parquet_bytes']:,} bytes. "
        "Picos são por processo, não soma de processos concorrentes nem memória física total da máquina.",
        "A primeira tentativa de ler todos os históricos juntos excedeu o limite de memória DuckDB antes de qualquer ajuste. "
        "A correção necessária foi carregar 2.500 séries por lote, usando as mesmas chaves prospectivas e o mesmo filtro temporal. "
        "Modelo, parâmetros e fórmulas não mudaram. A tentativa sem ajustes está registrada em `execution_prebatch_attempt.json`. "
        "O tempo real difere da projeção porque há margem conservadora e porque overhead e custo por ajuste "
        "foram medidos em carga e organização de I/O diferentes; não foi alterado o modelo para atingir um limite.",
        "## Artefatos e reprodução",
        markdown_table(pd.DataFrame([{"name":name,**item} for name,item in summary["artifacts"].items()]),
            {"name":"Artefato","path":"Caminho relativo","rows":"Linhas","sha256":"SHA-256"}),
        "Além dos Parquet: summary.json, execution.json, progress.json, population_performance.json e comparison_performance.json. "
        "O notebook `notebooks/04_statistical_forecasting.ipynb` consome somente outputs e contém dez figuras; "
        "PNGs e telemetria do notebook permanecem ignorados em data/outputs. Nenhum modelo treinado é serializado.",
        "```powershell\n.\\.venv\\Scripts\\python.exe scripts/run_statistical_forecast.py --compare-only\n"
        ".\\.venv\\Scripts\\python.exe scripts/render_statistical_forecasting.py\n"
        ".\\.venv\\Scripts\\python.exe -m pip check\ngit diff --check\ngit status\n```",
        "O comando sem `--compare-only` executa população apenas quando não existe mart final ou parcial. "
        "Nesta entrega não foi repetida a população. Reprodução valida contratos, hashes da fonte e Fase 4, "
        "métricas de SN idênticas às anteriores e seis ajustes determinísticos do último fold. "
        "Telemetria não exige igualdade de bytes; dependências e runtime constam em execution.json.",
        "## Limites da evidência",
        "Quatro folds, 28 dias avaliados e 62–83 dias de histórico não demonstram generalização sazonal ou em novas séries. "
        "As séries compartilham produtos/lojas; não são 50.000 experimentos independentes. Não há teste de significância "
        "nem evidência causal de disponibilidade. Classes relativas mudam entre origens. Vantagem em erro não basta "
        "para justificar custo ou piora de bias; a classificação final precisa considerar todos esses critérios. "
        "Não houve abertura do holdout, correção de censura, reposição ou Power BI."])
    sections.extend(["## Interpretação da execução aprovada",
        "**A) ETS claramente superior no backtesting observado.** Não é uma afirmação de dominância em toda série "
        "ou de desempenho garantido no holdout. A conclusão conjunta se apoia em redução global de MAE/WAPE de "
        "14,82% e de RMSE de 13,32%, vitória nas três métricas nos quatro folds, ganho em todos os segmentos "
        "predefinidos e bias global mais próximo de zero. O resultado não depende de uma janela isolada: "
        "o ganho WAPE por fold varia de 12,42% a 18,71%. Nas 36 combinações ABC×XYZ×fold, ETS vence "
        "em WAPE e RMSE; a menor melhoria WAPE é 10,81%.",
        "A e B melhoram WAPE em 14,39% e 15,74%. Os recortes prioritários AX/AY/AZ melhoram "
        "14,90%/13,53%/14,70%; BX/BY/BZ, 16,39%/17,33%/14,69%. HIGH melhora 12,79% e flag=True "
        "13,98%, mas mantém subprevisão importante. C também melhora: 17,44%; não há evidência "
        "para restringir a vantagem de erro apenas a alguns segmentos nesta população.",
        "**O ganho global não veio à custa de maior subprevisão global:** bias_pct passa de −3,27% para −2,17%; "
        "a proporção de séries com bias negativo cai de 61,40% para 55,33%. Contudo, isso não significa melhor "
        "calibração em todas as séries. O p05 do bias_pct fica mais negativo (−20,58% → −23,86%) e o p95 "
        "mais positivo (18,00% → 29,43%): a distribuição se alarga. Nos folds 1 e 3, ETS supera o nível "
        "observado em agregado; a magnitude do bias piora nos folds 1, 2 e 3. No fold 2 também há maior "
        "subprevisão (−0,84% → −1,04%). No fold 4, ela melhora, mas permanece elevada (−11,59% → −10,45%). "
        "Em HIGH, bias_pct passa de −4,82% para −4,08%; na flag=True, de −7,90% para −7,68%. "
        "Esses sinais exigem atenção, sem inferir ruptura causada pelo forecast.",
        "Nenhum dos grupos consolidados predefinidos piora a magnitude do bias, mas o recorte por fold revela "
        "pioras relevantes: AZ no fold 2 passa de −1,98% para −4,50%; HIGH no fold 2, de −2,65% para −4,28%; "
        "flag=True no fold 2, de −8,75% para −10,77%. AY no fold 3 passa de −0,20% para +3,67%, "
        "uma sobreprevisão maior em magnitude. São ressalvas explícitas à melhora média, mantendo todos "
        "os grupos e origens no summary.json e nas métricas segmento×fold.",
        "ETS tem menor WAPE em cada fold, mas **maior dispersão entre folds**: desvio de 1,72 ponto percentual "
        "contra 1,39 de SN; CV de 4,79% contra 3,27%. Menor nível de erro não equivale a menor volatilidade temporal. "
        "Os quatro folds não permitem afirmar significância ou estabilidade em outras estações.",
        "O ganho é amplamente distribuído: ETS vence MAE/WAPE em 44.203 séries (88,406%), SN em 5.797, sem empates. "
        "A melhoria mediana é 16,53%; 69,802% das séries melhoram pelo menos 10%. Ainda assim, 4,256% pioram "
        "pelo menos 10%; uma escolha uniforme não beneficia cada série. A classificação A reflete o conjunto "
        "da evidência, incluindo essas perdas e o custo local de 29,08 minutos para população e comparação.",
        "A regra híbrida conservadora usa ETS em BZ/CX/CY no fold 3 e AZ/BZ/CX/CY no fold 4. "
        "Gera WAPE global de 41,38%, ganho de 2,15% sobre SN, e RMSE de 0,759773, ganho de 2,04%. "
        "É inferior ao ETS uniforme neste backtest. A exigência de bias histórico bloqueia vários grupos "
        "apesar dos ganhos de erro; não foi relaxada após observar os resultados. Não há evidência de que "
        "essa regra seja necessária ou superior ao candidato único, nem base para selecionar séries pelo erro futuro.",
        "**Próxima decisão recomendada:** revisar A/N/A como candidato principal, preservando Seasonal Naive como "
        "referência e fallback. Adoção operacional, validação no holdout e eventual reprodução integral adicional "
        "exigem decisão posterior; não foram executadas. Nenhum modelo adicional, política de reposição ou commit foi criado. "
        "Com a validação final aprovada, a recomendação técnica é **Fase 5 aprovada para revisão e encerramento desta etapa**, "
        "sem bloqueio metodológico remanescente e sem autorizar abertura do holdout."])
    validation_path=folder / "validation.json"
    if validation_path.exists():
        validation=read("validation.json")
        sections.extend(["## Validação final da continuação",
            f"Pytest: **{validation['pytest_passed']} aprovados, {validation['pytest_deselected']} desmarcados**, "
            f"em {validation['pytest_seconds']:.2f} s. Os 92 testes anteriores foram preservados; oito foram adicionados. "
            "Os dois desmarcados abrem o raw eval para contratos de ingestão/staging e não foram executados nesta rodada. "
            "As demais validações, incluindo reprodução integral das Fases 2/3/4 sem eval e os novos contratos "
            "populacionais, passaram. Não se repete o fitting populacional da Fase 5.",
            "```powershell\n"+validation["pytest_command"]+"\n```",
            "A primeira rodada teve 97 aprovações e uma diferença de reprodução numérica em seis ajustes (máximo "
            "absoluto de 0,00012431). Com a mesma configuração de uma thread do runner, os seis ajustes foram "
            "reproduzidos exatamente. O teste agora aplica threadpoolctl no contexto de ajuste; a dependência "
            "já fazia parte da stack. Nenhuma tolerância foi relaxada, modelo alterado ou previsão substituída.",
            "`pip check`: sem dependências quebradas. `git diff --check`: sem erros. "
            "Stage vazio, HEAD `4dfaa9d`, sem commit. Dados, outputs, .venv e .env permanecem ignorados; "
            "somente os .gitkeep preexistentes estão rastreados nos diretórios de dados."])
    if (folder / "notebook_performance.json").exists():
        notebook=read("notebook_performance.json")
        kernel=read("notebook_kernel_performance.json")
        sections.extend(["## Apresentação executada",
            f"Notebook com dez figuras, doze células de código executadas e nenhum erro; inspeção visual concluída. "
            f"Última renderização: {notebook['seconds']:.2f} s; {notebook['notebook_bytes']:,} bytes. "
            f"Pico do kernel: {kernel['peak_working_set_bytes']/2**20:.2f} MiB. "
            "Uma tentativa no sandbox foi bloqueada por ACL do arquivo temporário do Jupyter (WinError 5). "
            "A execução fora do sandbox foi autorizada; a tentativa bloqueada e o kernel concluído foram encerrados. "
            "Não foi desabilitada a proteção de arquivos do Jupyter."])
    (root / "docs/statistical_forecasting_report.md").write_text("\n\n".join(sections)+"\n",encoding="utf-8")


if __name__=="__main__":
    write_report()
