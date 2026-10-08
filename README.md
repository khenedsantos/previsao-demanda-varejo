# Previsão de demanda e planejamento de reposição no varejo

## Problema de negócio

Como usar o histórico de vendas para prever demanda, identificar risco operacional e apoiar decisões de reposição no varejo?

## Objetivo

Apoiar decisões de negócio com previsões de curto prazo, avaliação temporal e comunicação de incerteza, conectando demanda e planejamento de reposição.

## Dataset escolhido

FreshRetailNet-50K, publicado por Dingdong-Inc no Hugging Face (versão 1.0, CC BY 4.0). Arquivos Parquet oficiais congelados por revisão e SHA-256 em [source_manifest.yaml](config/source_manifest.yaml).

## Status

Em desenvolvimento. Fases 0 a 3 aprovadas e commitadas: fundação, ingestão/qualidade, entendimento
de train e segmentação operacional. Fase 4 implementada para revisão: Naive, Seasonal Naive e
quatro folds temporais com segmentação prospectiva. Resultados em
[forecasting_baselines_report.md](docs/forecasting_baselines_report.md). Seasonal Naive é a referência
global, com exceções por segmento. Eval permanece congelado; modelos adicionais e reposição pendentes.

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
