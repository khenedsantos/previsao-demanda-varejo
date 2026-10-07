# Arquitetura

## Propósito

Registrar a organização técnica e as responsabilidades de cada etapa.

## Fluxo previsto

`raw` imutável → `staging` → `processed` → `outputs`.

## Responsabilidades

- `src/`: ingestão, qualidade, preparação, atributos, segmentação, previsão, validação, reposição e comunicação.
- `sql/`: consultas de staging, análise e validação com DuckDB.
- `notebooks/`: exploração; a lógica definitiva ficará em `src/`.
- `config/`: parâmetros declarativos, ainda sem implementação de leitura pelo pipeline.
- `powerbi/`: futura apresentação orientada à decisão de negócio.

## Estado atual

Somente fundação técnica. Pipeline, contratos entre etapas e modelo analítico pendentes.
