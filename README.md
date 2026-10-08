# Previsão de demanda e planejamento de reposição no varejo

## Problema de negócio

Como usar o histórico de vendas para prever demanda, identificar risco operacional e apoiar decisões de reposição no varejo?

## Objetivo

Apoiar decisões de negócio com previsões de curto prazo, avaliação temporal e comunicação de incerteza, conectando demanda e planejamento de reposição.

## Dataset escolhido

FreshRetailNet-50K, publicado por Dingdong-Inc no Hugging Face (versão 1.0, CC BY 4.0). Arquivos Parquet oficiais congelados por revisão e SHA-256 em [source_manifest.yaml](config/source_manifest.yaml).

## Status

Em desenvolvimento. Fase 1: ingestão e qualidade estrutural/semântica; resultados em [data_quality_report.md](docs/data_quality_report.md). Nenhuma previsão implementada.

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
