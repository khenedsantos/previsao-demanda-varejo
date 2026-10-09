# Previsão de demanda e planejamento de reposição no varejo

## Problema de negócio

Como usar o histórico de vendas para prever demanda, identificar risco operacional e apoiar decisões de reposição no varejo?

## Objetivo

Apoiar decisões de negócio com previsões de curto prazo, avaliação temporal e comunicação de incerteza, conectando demanda e planejamento de reposição.

## Dataset escolhido

FreshRetailNet-50K, publicado por Dingdong-Inc no Hugging Face (versão 1.0, CC BY 4.0). Arquivos Parquet oficiais congelados por revisão e SHA-256 em [source_manifest.yaml](config/source_manifest.yaml).

## Status

Em desenvolvimento. Fases 0 a 6 aprovadas e commitadas: fundação, ingestão/qualidade, entendimento
de train, segmentação, baselines, ETS e diagnóstico de incerteza/risco. A Fase 4 contém Naive, Seasonal Naive e
quatro folds temporais com segmentação prospectiva. Resultados em
[forecasting_baselines_report.md](docs/forecasting_baselines_report.md). Seasonal Naive é a referência
global de comparação, com exceções por segmento. A primeira abertura analítica de eval foi
autorizada e realizada na Fase 7, após congelamento das decisões anteriores; reposição continua fora do escopo.

Fase 4 aprovada e commitada em `4dfaa9d`. A continuação autorizada da Fase 5 executa somente
Holt-Winters A/N/A na população, agora concluída: 50.000 séries, quatro folds e 200.000 ajustes, com comparação
pareada contra Seasonal Naive. A projeção inicial foi 39,03 minutos; o antigo limite de engenharia
de 30 minutos foi revogado pelo usuário. Fase 5 aprovada e commitada em `6a7ccec`.
Detalhes em [statistical_forecasting_report.md](docs/statistical_forecasting_report.md).

Resultado observado: **A — ETS claramente superior neste backtest**, com ganho global de
14,82% em MAE/WAPE e 13,32% em RMSE, nos quatro folds e em todos os segmentos predefinidos.
Bias global melhora, mas sua dispersão por série aumenta. Zero fallback; população e comparação
em 29,08 minutos. Essa evidência não equivale a adoção operacional nem validação no holdout.

A Fase 6 acrescenta perfis de erro e risco usando as previsões congeladas, sem novo ajuste.
São 16.529 séries com subprevisão persistente e 1.028 com duplo sinal de censura e persistência.
Os perfis estão disponíveis após 25/06/2024 e não podem ser reutilizados retrospectivamente
nos folds. Relatório: [forecast_uncertainty_and_risk_report.md](docs/forecast_uncertainty_and_risk_report.md).
Fase 6 aprovada estritamente como diagnóstico descritivo e commitada em `d6681aa`.

## Arquitetura resumida

- `data/raw/`: dados de origem imutáveis.
- `data/staging/`, `data/processed/` e `data/outputs/`: dados intermediários, tratados e saídas; não versionados.
- `src/`: lógica definitiva, organizada por etapa; `sql/`: consultas DuckDB.
- `notebooks/`: exploração; `config/`: parâmetros; `tests/`: validações; `scripts/`: execução auxiliar.
- `powerbi/`: futura camada de comunicação e decisão; `docs/`: documentação e decisões metodológicas.

## Política de reposição simulada

A política de reposição será simulada porque lead time e estoque físico não são fornecidos pela fonte. Esses parâmetros não serão apresentados como fatos observados.

## Reproduzir a Fase 1

Com Python 3.12 e o ambiente local ativo, execute na raiz:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/ingest_data.py
python scripts/validate_raw.py
python -m pytest --basetemp=.tmp/pytest
python -m pip check
```

Em um clone novo, crie `.venv` com `python -m venv .venv` e instale as dependências com `python -m pip install .`. A primeira ingestão exige internet; reexecuções verificam os arquivos locais e não os sobrescrevem. Os testes de integração exigem a ingestão e a validação concluídas. Os scripts resolvem os caminhos a partir do repositório, sem edição manual.

O staging preserva a origem train/eval. O bloco eval permanece reservado para futura avaliação temporal; combinar arquivos para armazenamento não autoriza seu uso em treino ou tuning. Detalhes em [architecture.md](docs/architecture.md) e [decisions.md](docs/decisions.md).

## Reproduzir a Fase 2

Após a ingestão da fonte, na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe scripts/build_demand_profile.py
.\.venv\Scripts\python.exe scripts/render_data_understanding.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
```

O primeiro script lê somente `train.parquet`, gera `data/processed/mart_demand_profile.parquet`,
outputs de suporte em `data/outputs/demand_understanding/` e o relatório da Fase 2.
O segundo executa [01_data_understanding.ipynb](notebooks/01_data_understanding.ipynb), com nove figuras
baseadas nos outputs. Os nomes `*_demand` medem venda observada normalizada, não demanda latente.
Definições, tratamento de métricas indefinidas e regras dos exemplos estão em [methodology.md](docs/methodology.md).

## Reproduzir a Fase 3

Após gerar os outputs da Fase 2:

```powershell
.\.venv\Scripts\python.exe scripts/build_segmentation.py
.\.venv\Scripts\python.exe scripts/render_segmentation.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
```

O pipeline verifica a proveniência de train, recalcula ABC por produto e cria os marts de ABC,
XYZ, exposição e perfil operacional em processed. O notebook [02_segmentation.ipynb](notebooks/02_segmentation.ipynb)
contém nove figuras baseadas nos outputs. As razões de XYZ, thresholds e alternativas comparadas
ficam registradas no relatório e no resumo de execução. Nenhum score composto é criado.

As classes descrevem o train até 25/06/2024. No backtesting futuro, recalcular perfil, ABC/XYZ e
quantis em cada origem, sem reutilizar retrospectivamente o retrato integral. A Fase 4 implementa
esse recálculo. Eval permanece congelado.

## Reproduzir a Fase 4

Após a ingestão de train, na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe scripts/run_baseline_backtest.py
.\.venv\Scripts\python.exe scripts/render_forecasting_baselines.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
git diff --check
git status
```

O backtest lê somente o raw train verificado pelo manifesto e recalcula o perfil e a segmentação
até cada corte. Não depende dos marts finais das fases anteriores. Gera os marts de previsões
e métricas, sete Parquet auxiliares, resumo com hashes, telemetria e relatório. O notebook
[03_forecasting_baselines.ipynb](notebooks/03_forecasting_baselines.ipynb) executado contém dez figuras
que consomem esses outputs. A suíte completa também exige os outputs anteriores para seus testes.

São 2,8 milhões de previsões de venda observada normalizada, horizonte de sete dias e quatro
origens (29/05, 05/06, 12/06 e 19/06/2024). WAPE global: Naive 43,49%; Seasonal Naive 42,29%.
Dados e figuras soltas são ignorados; código, testes, documentação e notebook são elegíveis para Git.
Nenhum commit ou avanço de fase é executado automaticamente.

## Reproduzir a comparação da Fase 5

```powershell
.\.venv\Scripts\python.exe scripts/run_statistical_forecast.py --compare-only
.\.venv\Scripts\python.exe scripts/render_statistical_forecasting.py
.\.venv\Scripts\python.exe -m pytest --basetemp=.tmp/pytest-phase5-population-final --deselect=tests/test_raw_quality.py::test_raw_files_manifest_hashes_and_schema --deselect=tests/test_raw_quality.py::test_staging_reproducible_from_full_raw
.\.venv\Scripts\python.exe -m pip check
```

`--compare-only` reutiliza as previsões salvas sem repetir ajustes. Em uma primeira execução
populacional autorizada, o comando sem essa opção produz os forecasts; ele recusa sobrescrever
um resultado final ou parcial existente. A leitura ocorre em lotes de 2.500 históricos cortados
na origem. Preserva fallback Seasonal Naive, razões, forecast original e clipping negativo.

São gerados `mart_forecast_statistical.parquet`, `mart_model_comparison.parquet` e auxiliares em
`data/outputs/statistical_forecasting/`. A comparação reutiliza snapshots prospectivos e forecasts
da Fase 4, verificados por hash. O notebook [04_statistical_forecasting.ipynb](notebooks/04_statistical_forecasting.ipynb)
consome somente esses outputs e produz dez figuras. MAE, RMSE, WAPE, bias, materialidade e
potencial híbrido são documentados no relatório; não há MAPE nem política operacional final.

O benchmark anterior, em 135 séries e 540 ajustes por configuração, é preservado sem reexecução.
A/A/A não participa da execução populacional. A validação mantém os 92 testes anteriores e
acrescenta contratos populacionais/comparação. Os dois testes legados indicados em `--deselect`
abririam eval para verificar ingestão/staging: permanecem intactos, mas não são executados nesta
rodada. Temporários locais evitam o problema anterior de I/O em AppData. Reprodução de ajustes
usa seis séries; nenhuma segunda execução dos 200.000 ajustes é exigida antes da revisão.

Validação final: **98 testes aprovados, dois legados desmarcados**, em 123,69 s; `pip check`
e `git diff --check` aprovados. A reprodução dos seis ajustes usa uma thread numérica, como
o runner, e exige igualdade exata. Notebook executado com dez figuras e nenhum erro.
Esse resultado foi revisado e aprovado; a Fase 5 está commitada em `6a7ccec`, com as ressalvas do relatório.

## Reproduzir a Fase 6

Após os outputs aprovados das fases 2, 3 e 5:

```powershell
.\.venv\Scripts\python.exe scripts/build_forecast_risk_profile.py
.\.venv\Scripts\python.exe scripts/render_forecast_uncertainty.py
.\.venv\Scripts\python.exe -m pytest --basetemp=.tmp/pytest-phase6-final --deselect=tests/test_raw_quality.py::test_raw_files_manifest_hashes_and_schema --deselect=tests/test_raw_quality.py::test_staging_reproducible_from_full_raw
.\.venv\Scripts\python.exe -m pip check
git diff --check
git status
```

O pipeline verifica hashes e escopo train dos marts existentes e agrega 1,4 milhão de erros;
não lê raw nem ajusta modelos. Publica três marts em processed, 14 Parquet auxiliares e um
resumo determinístico em outputs/forecast_uncertainty. A reprodução compara seus hashes em
uma raiz sem raw/eval, com ajuste ETS bloqueado. Os dois testes legados acima permanecem
preservados e desmarcados porque abririam eval.

[05_forecast_uncertainty_and_risk.ipynb](notebooks/05_forecast_uncertainty_and_risk.ipynb)
consome esses outputs e contém dez figuras. Bias negativo em pelo menos três dos quatro
folds, junto de bias consolidado negativo, define persistência. O retrato operacional de
25/06 serve ao diagnóstico posterior; a avaliação prospectiva da Fase 5 permanece intacta.
Não há correção de forecast, demanda latente, lost sales ou fórmula de estoque.

Validação final da Fase 6: **106 testes aprovados e dois legados desmarcados**, em 169,47 s.
Os 17 Parquet e o resumo foram reproduzidos por hash, sem raw/eval ou ajuste ETS no pipeline
da Fase 6. A suíte também preserva as reproduções legadas em temporários, incluindo seis
ajustes ETS; nenhuma reexecução populacional ocorreu. Os hashes oficiais da Fase 5 continuam
iguais. Notebook com dez figuras e nenhum erro; `pip check` e `git diff --check` aprovados.
Recomendação técnica: Fase 6 aprovada para revisão descritiva, com sensibilidade do bias global
ao fold 4 explicitada. Stage vazio; entrega sem commit e sem avanço de fase.

## Fase 7 — avaliação final autorizada

O usuário autorizou a primeira abertura analítica de eval somente após o congelamento e commit
das fases 0–6. [Protocolo anterior à abertura](docs/final_holdout_protocol.md): ETS A/N/A e
Seasonal Naive, 50.000 séries, origem 26/06/2024, sete passos diretos, treino encerrado em 25/06.
Previsões dos dois modelos são persistidas sem actuals antes da leitura do holdout. Labels,
flags, fallback, clipping e hiperparâmetros anteriores permanecem inalterados.

```powershell
# Única primeira execução autorizada; recusa execução final/parcial já existente:
.\.venv\Scripts\python.exe scripts/run_final_holdout.py --fit-only
# Reproduzir avaliação sem refit:
.\.venv\Scripts\python.exe scripts/run_final_holdout.py --evaluate-only
.\.venv\Scripts\python.exe scripts/render_final_holdout.py
.\.venv\Scripts\python.exe -m pytest --basetemp=.tmp/pytest-phase7-final
.\.venv\Scripts\python.exe -m pip check
git diff --check
git status
```

Resultados em [final_holdout_evaluation_report.md](docs/final_holdout_evaluation_report.md) e
[06_final_holdout_evaluation.ipynb](notebooks/06_final_holdout_evaluation.ipynb), com dez figuras
que leem outputs. A suíte completa pode agora executar os dois testes legados de ingestão/staging
antes excluídos, pois a abertura do holdout foi autorizada. Não apagar as exclusões documentadas
nas rodadas históricas. Os três marts holdout e seus auxiliares são ignorados pelo Git.
Esta entrega não faz commit, tuning, reposição ou Power BI.

Resultado final holdout: ETS WAPE **35,62%**, Seasonal Naive **41,83%**; ganho **14,85%** em
MAE/WAPE e **14,90%** em RMSE. Os 50.000 ajustes terminaram sem fallback, em 7,10 minutos
incluindo I/O. Bias_pct ETS **−2,25%**, contra **+0,28%** do baseline. Classificação conjunta
**B — confirmação parcial**: forte confirmação da vantagem de erro do ETS, porém separação
prospectiva fraca da persistência (56,12% versus 54,29% com bias negativo) e confirmação não
uniforme da matriz de risco. Não se alterou nenhuma regra após observar esses resultados.

Validação final: **118 testes aprovados, sem falhas ou exclusões**, em 203,21 s conforme XML.
Os 13 Parquet e o resumo foram reproduzidos em raiz sem train, com fitting bloqueado; os 53
artefatos anteriores e forecasts pré-eval continuam íntegros. Notebook com dez figuras e zero
erros; `pip check` e `git diff --check` aprovados. A retomada confirmou os registros existentes
sem repetir forecasting. Recomendação técnica: Fase 7 aprovada para revisão, com classificação B
e ressalvas explícitas. Entrega sem commit; stage vazio; reposição e Power BI não iniciados.
