# Previsão de demanda e planejamento de reposição no varejo

## Problema de negócio

Como usar o histórico de vendas para prever demanda, identificar risco operacional e apoiar decisões de reposição no varejo?

## Objetivo

Apoiar decisões de negócio com previsões de curto prazo, avaliação temporal e comunicação de incerteza, conectando demanda e planejamento de reposição.

## Dataset escolhido

FreshRetailNet-50K. Os dados ainda não foram baixados.

## Status

Em desenvolvimento.

## Arquitetura resumida

- `data/raw/`: dados de origem imutáveis.
- `data/staging/`, `data/processed/` e `data/outputs/`: dados intermediários, tratados e saídas; não versionados.
- `src/`: lógica definitiva, organizada por etapa; `sql/`: consultas DuckDB.
- `notebooks/`: exploração; `config/`: parâmetros; `tests/`: validações; `scripts/`: execução auxiliar.
- `powerbi/`: futura camada de comunicação e decisão; `docs/`: documentação e decisões metodológicas.

## Política de reposição simulada

A política de reposição será simulada porque lead time e estoque físico não são fornecidos pela fonte. Esses parâmetros não serão apresentados como fatos observados.
