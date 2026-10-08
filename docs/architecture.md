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

Fase 1 implementada: ingestão e qualidade. Etapas analíticas posteriores continuam pendentes.

## Execução e contratos

1. `scripts/ingest_data.py` lê `config/project.yaml` e `config/source_manifest.yaml`; baixa somente os dois Parquet oficiais da revisão fixada. Arquivos existentes são conferidos por tamanho, SHA-256, linhas e schema, nunca sobrescritos. Um download incompleto permanece fora do raw e é descartado.
2. `scripts/validate_raw.py` verifica novamente a identidade da fonte e executa o profiling SQL em DuckDB diretamente nos Parquet. Falhas bloqueiam a geração do staging e retornam código de erro.
3. PyArrow cria `data/staging/fresh_retail_daily.parquet` em lotes de 65.536 linhas, com compressão ZSTD. `dt` passa de string para date32; `source_split` e `source_file` identificam a proveniência. As outras 18 colunas são preservadas. Uma comparação integral em lotes confirma valores e contagem.
4. São gerados o JSON de qualidade e o Parquet de cobertura por série em `data/outputs/`; o relatório Markdown em `docs/` é elegível para versionamento.

O staging existente é conferido, sem sobrescrita silenciosa. A publicação inicial de raw/staging ocorre somente depois de validar o arquivo temporário. A ordem de entrada é train e depois eval, preservando a ordem de cada arquivo.

## Memória, disco e Git

DuckDB usa duas threads, limite de memória de 1 GB e spill temporário limitado a 2 GB em `.tmp/duckdb`. Não há banco persistente nem carregamento integral em pandas. Temporários de download e staging ficam em `.tmp/`. O teste de reprodução cria uma cópia temporária do staging e a remove ao terminar.

Dados, ambiente, caches e segredos são ignorados. Código, SQL, configurações e documentação ficam no Git. Nenhum notebook, feature, modelo ou dashboard foi criado nesta fase.
