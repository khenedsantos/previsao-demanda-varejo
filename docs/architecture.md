# Arquitetura

## Propósito

Registrar a organização técnica e as responsabilidades de cada etapa.

## Fluxo previsto

`raw` imutável → `staging` → `processed` → `outputs`.

## Responsabilidades

- `src/`: ingestão, qualidade, preparação, atributos, segmentação, previsão, validação, reposição e comunicação.
- `sql/`: consultas de staging, análise e validação com DuckDB.
- `notebooks/`: exploração; a lógica definitiva ficará em `src/`.
- `config/`: parâmetros do projeto e manifesto da fonte congelada.
- `powerbi/`: futura apresentação orientada à decisão de negócio.

## Estado atual

Fase 1 implementada e commitada: ingestão e qualidade. Fase 2 implementada: perfil descritivo
de train, análise de disponibilidade e notebook de apresentação, aprovada e commitada.
Fase 3 aprovada e commitada: ABC por produto, XYZ por série e exposição separada.
Fase 4 aprovada e commitada: dois baselines e quatro folds com segmentação prospectiva.
Fase 5 iniciada até o benchmark de custo; execução estatística completa e reposição pendentes.

## Execução e contratos

1. `scripts/ingest_data.py` lê `config/project.yaml` e `config/source_manifest.yaml`; baixa somente os dois Parquet oficiais da revisão fixada. Arquivos existentes são conferidos por tamanho, SHA-256, linhas e schema, nunca sobrescritos. Um download incompleto permanece fora do raw e é descartado.
2. `scripts/validate_raw.py` verifica novamente a identidade da fonte e executa o profiling SQL em DuckDB diretamente nos Parquet. Falhas bloqueiam a geração do staging e retornam código de erro.
3. PyArrow cria `data/staging/fresh_retail_daily.parquet` em lotes de 65.536 linhas, com compressão ZSTD. `dt` passa de string para date32; `source_split` e `source_file` identificam a proveniência. As outras 18 colunas são preservadas. Uma comparação integral em lotes confirma valores e contagem.
4. São gerados o JSON de qualidade e o Parquet de cobertura por série em `data/outputs/`; o relatório Markdown em `docs/` é elegível para versionamento.

O staging existente é conferido, sem sobrescrita silenciosa. A publicação inicial de raw/staging ocorre somente depois de validar o arquivo temporário. A ordem de entrada é train e depois eval, preservando a ordem de cada arquivo.

## Memória, disco e Git

DuckDB usa duas threads, limite de memória de 1 GB e spill temporário limitado a 2 GB em `.tmp/duckdb`. Não há banco persistente nem carregamento integral em pandas. Temporários de download e staging ficam em `.tmp/`. O teste de reprodução cria uma cópia temporária do staging e a remove ao terminar.

Dados, ambiente, caches e segredos são ignorados. Código, SQL, configurações e documentação ficam no Git. Nenhum notebook, feature, modelo ou dashboard foi criado na Fase 1.

## Contrato da Fase 2

`scripts/build_demand_profile.py` verifica e abre **apenas train.parquet**. A leitura exclusiva evita
que o staging combinado exponha eval à exploração. `src/features/demand_profile.py` executa
`sql/analytical/demand_profile.sql` depois de aplicar o corte temporal, produzindo o mart por série,
tabelas de weekday/semana, curvas de concentração e exemplos selecionados por regra.

O resumo JSON referencia hashes dos seis outputs Parquet e o hash/revisão da fonte. A documentação
é gerada por `src/reporting/demand_understanding_report.py`. O notebook de nove figuras só consome
outputs, usando `src/reporting/demand_understanding_plots.py`; sua execução reproduzível está em
`scripts/render_data_understanding.py`. Nenhuma regra crítica depende de execução manual de células.

Dados gerados continuam fora do Git. O notebook executado e o relatório ficam disponíveis para revisão.
A validação reconstrói os outputs em uma raiz sem eval e verifica igualdade de hashes no mesmo runtime.

## Contrato da Fase 3

`scripts/build_segmentation.py` lê somente train e os outputs aprovados da Fase 2. A identidade
do raw, o hash/proveniência do perfil e a janela são verificados antes do cálculo. Chaves, dias e
totais de venda por série são conciliados com o train até o corte.

Em `src/segmentation/`, `abc.py` trata a contribuição global por produto, `xyz.py` deriva regras
categóricas de duas métricas, `stockout_exposure.py` mantém disponibilidade separada, e
`operational_profile.py` executa e valida as junções. `sql/analytical/segmentation.sql` contém
as agregações de contribuição, matriz e exposição. Não há framework interno ou score composto.

Quatro marts são publicados em processed: produto/ABC, série/XYZ, exposição e perfil operacional.
Sete Parquet de suporte e resumo com hashes ficam em outputs/segmentation. Relatório e gráficos
ficam nos módulos de reporting; `scripts/render_segmentation.py` executa o notebook de nove figuras,
consumindo apenas outputs. Nenhuma lógica crítica é exclusiva de célula de notebook.

O mart de entrada precisa corresponder exatamente ao corte solicitado. ABC, XYZ e quantis do
train integral não podem ser reaproveitados em origens anteriores. Nenhum backtesting é executado
nesta fase. Os outputs são reproduzidos por hash em uma raiz sem eval ou staging.

## Contrato da Fase 4

`scripts/run_baseline_backtest.py` usa `src/forecasting/backtesting.py` e abre somente raw train,
verificado por manifesto. Para cada origem, `prepare_tables(as_of=cutoff)` da Fase 2 aplica o
corte antes das agregações; ABC/XYZ/exposição da Fase 3 são recalculados com esse prefixo.
Nenhum mart final de perfil/segmentação é reutilizado. A SQL de perfil aprovada permanece intacta.

`src/forecasting/baselines.py` cria as previsões sem actual do horizonte. Depois o backtest junta
actuals do mesmo train para calcular error. O mart contém cutoff e data da observação usada,
permitindo auditoria integral de Naive e t−7. PyArrow escreve um fold por vez em Parquet ZSTD,
com ordenação e grupos de 65.536 linhas definidos. Não há modelo serializado ou banco persistente.

`src/validation/forecast_metrics.py` agrega somas de erros e actuals em DuckDB. O campo `level`
do mart de métricas distingue nove níveis solicitados e cinco cortes segmento×fold, estes usados
somente para estabilidade. Dimensões não aplicáveis são nulas; filtrar `level` antes de agregar.
O consolidado por série não recebe rótulo fixo, pois a classificação muda entre origens.

Os dois marts em processed e sete Parquet em outputs/forecasting_baselines incluem snapshots
de séries/produtos por corte, melhoria relativa, estabilidade, seleção e trajetórias dos exemplos.
`summary.json` registra hashes, métricas, thresholds, fonte e versões. `performance.json` separa
tempo e pico de memória, não determinísticos. Reprodução compara os nove Parquet e o resumo
em raiz que contém apenas configurações e train. Dados permanecem ignorados pelo Git.

DuckDB usa uma thread e limite de 1 GB; spill por fold até 2 GB em `.tmp/forecasting_baselines`.
O pico do processo também inclui pandas, PyArrow e Python, podendo exceder o limite do DuckDB.
Não há loops Python por linha. `forecast_report.py` gera documentação; `forecast_plots.py` lê
outputs; `scripts/render_forecasting_baselines.py` executa notebook de dez figuras na .venv.
Não existe lógica analítica exclusiva de célula. Modelos adicionais e reposição seguem fora do escopo.

## Contrato da Fase 5

`src/forecasting/ets.py` encapsula Holt-Winters aditivo de período sete, convergência, projeção
de previsões negativas em zero e fallback Seasonal Naive com razão explícita. Nenhum modelo
treinado é persistido. `ets_benchmark.py` verifica a fonte train e todos os hashes da Fase 4,
seleciona amostra por ABC×XYZ×escala do primeiro snapshot e lê históricos com corte na SQL.

`scripts/benchmark_statistical_forecast.py` limita threads numéricas e executa 135 séries ×
quatro folds × duas especificações sequencialmente. Publica amostra, custos/status por ajuste
e JSON em outputs/statistical_forecasting, ignorados pelo Git. Tempos são variáveis; a seleção
é determinística. Esse benchmark foi preservado; a continuação foi autorizada exclusivamente
para A/N/A populacional, com o limite inicial de custo revogado.

`scripts/run_statistical_forecast.py` orquestra `statistical_backtesting.py` e `model_comparison.py`.
As opções `--fit-only` e `--compare-only` separam ajustes e comparação. O primeiro recusa um mart
final/parcial existente, registra runtime/configuração, lê 2.500 séries por lote a partir das
chaves dos snapshots prospectivos e escreve Parquet temporário. Ao validar 200.000 ajustes e
1.400.000 forecasts, publica o arquivo final por renomeação. `progress.json` é atualizado
atomicamente a cada lote. Nenhum ajuste recebe actual futuro; a união acontece depois.

`forecast_metrics.py` aceita múltiplos marts e filtro de modelos, preservando fórmulas e o
comportamento padrão da Fase 4. `model_comparison.py` agrega SN e ETS sobre as mesmas chaves
e snapshots; valida cobertura/denominadores antes do pareamento. `mart_model_comparison`
contém uma linha por par de métricas, ambos os valores e melhoria; `level` distingue série,
série×fold, consolidados, segmentos×fold e série×classe prospectiva para win rate.

Fallback e clipping permanecem no mart de forecasts. Auxiliares guardam diagnósticos, win rates,
materialidade, estabilidade, escolhas híbridas baseadas no passado e exemplos determinísticos.
O mart SN não é copiado. Fonte, benchmark e outputs ficam ligados por hashes no summary.json;
telemetria variável é separada. DuckDB usa uma thread, 512 MB para históricos e 768 MB para
comparação; esse limite não inclui objetos pandas/PyArrow. Spill da comparação fica em `.tmp/`.

`statistical_report.py` gera as tabelas do relatório; `statistical_plots.py` lê apenas outputs;
`render_statistical_forecasting.py` executa dez figuras na .venv. Nenhuma lógica crítica é
exclusiva do notebook. Dados/outputs continuam ignorados; não há modelos serializados,
abertura de eval ou integração com reposição/Power BI.

O runner configura BLAS/OMP/MKL com uma thread antes dos imports. O teste de reprodução dos
seis ajustes usa o mesmo limite via threadpoolctl já disponível na stack, pois pytest pode ter
importado as bibliotecas antes. A comparação mantém igualdade exata dos arrays; não se aumenta
tolerância para aceitar um runtime diferente. Threads também fazem parte da proveniência.
