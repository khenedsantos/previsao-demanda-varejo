# Validação de fechamento

> **Nota factual de atualização — 12/10/2026:** o texto abaixo preserva o checkpoint
> histórico de preparação, inclusive o bloqueio de whitespace. Posteriormente foram
> realizados os commits [7878ee6](https://github.com/khenedsantos/previsao-demanda-varejo/commit/7878ee6)
> (`feat: add Power BI decision report and portable sources`) e
> [6040751](https://github.com/khenedsantos/previsao-demanda-varejo/commit/6040751)
> (`docs: finalize retail demand portfolio documentation`), ambos em 11/10/2026.
> Assim, as referências abaixo a arquivos no stage, bloqueio e ausência de commits
> descrevem aquele checkpoint, não o estado posterior à entrega. Esta nota não
> declara reexecução de testes nem amplia o alcance das validações registradas.

Fechamento de documentação e empacotamento sobre `main`, HEAD `850032d`.
Na rodada inicial não houve staging, commit, push, refresh ou fitting ETS. Na preparação
seguinte, somente o primeiro commit planejado foi colocado no stage para revisão;
README, capturas e documentação editorial ficaram fora dele. Não houve commit ou push.
As páginas 01–04 já estavam visualmente aprovadas; seus arquivos foram preservados
por SHA-256. Os dados, PBIX, código analítico, medidas e relacionamentos permaneceram intactos.

## Alterações permitidas

- Um parâmetro M de texto, `pPowerBIDataRoot`, em `definition/expressions.tmdl`, com placeholder genérico.
- Seis substituições do argumento de `File.Contents`, mantendo os mesmos CSVs. Cada arquivo reverte exatamente aos bytes anteriores ao recolocar o argumento original: etapas, tipos, encoding, delimitador, cabeçalhos e transformações são idênticos.
- Apenas `visibility: HiddenInViewMode` no JSON da página 00, conforme o schema oficial page 2.1.0.
- Regras de exclusão e documentação final. As demais definições existentes não foram regravadas.

## Testes

**136 passaram, 12 foram desmarcados, zero falhas**; execução pytest em **42,82 s**.
`python -m pip check`: nenhuma dependência incompatível. `git diff --check`: aprovado.
Um guard temporário registrou **zero tentativa de `ExponentialSmoothing.fit`**.
Nenhum pipeline de produção foi reexecutado; testes de integração restantes leram
artefatos congelados e os casos negativos usaram fixtures/cópias temporárias.

A suíte tem 148 casos coletados. As exclusões abaixo são deliberadas para cumprir o
escopo sem fitting, refresh, recalibração ou reconstrução populacional. Não são
resultados aprovados nesta rodada nem falhas ocultadas.

| Teste excluído | Motivo |
|---|---|
| `tests/test_statistical_forecasting.py::test_weekly_additive_forecast_has_seven_finite_values` | Ajuste ETS |
| `tests/test_statistical_forecasting.py::test_future_mutation_does_not_change_history_or_forecast` | Ajustes ETS |
| `tests/test_statistical_population.py::test_batch_preserves_cutoff_fallback_and_finite_forecasts` | Ajuste ETS |
| `tests/test_statistical_population.py::test_population_hashes_and_small_batch_reproduction` | Seis ajustes ETS |
| `tests/test_raw_quality.py::test_staging_reproducible_from_full_raw` | Reconstrução integral de staging |
| `tests/test_demand_profile.py::test_full_outputs_reproduce_with_eval_absent` | Reconstrução de outputs de demanda |
| `tests/test_segmentation.py::test_all_outputs_reproduce_without_eval_or_staging` | Reconstrução de segmentação |
| `tests/test_forecasting_baselines.py::test_full_pipeline_reproduces_without_eval_or_any_previous_mart` | Backtesting populacional de baselines |
| `tests/test_forecast_uncertainty.py::test_population_outputs_reproduce_without_raw_eval_or_forecast_fitting` | Reconstrução dos outputs de risco |
| `tests/test_final_holdout.py::test_population_holdout_reproduces_without_train_or_fits` | Reconstrução da avaliação populacional |
| `tests/test_replenishment_simulation.py::test_population_reproducible_without_eval_and_invariant_to_changed_eval` | Duas reconstruções/calibrações da simulação |
| `tests/test_powerbi_layer.py::test_reproduction_from_only_allowed_marts_without_raw_or_forecasting` | Duas regenerações dos CSVs BI |

Para reproduzir a mesma seleção, com os dados e artefatos locais presentes:

```powershell
$closureExcluded = 'test_weekly_additive_forecast_has_seven_finite_values or test_future_mutation_does_not_change_history_or_forecast or test_batch_preserves_cutoff_fallback_and_finite_forecasts or test_population_hashes_and_small_batch_reproduction or test_staging_reproducible_from_full_raw or test_full_outputs_reproduce_with_eval_absent or test_all_outputs_reproduce_without_eval_or_staging or test_full_pipeline_reproduces_without_eval_or_any_previous_mart or test_population_outputs_reproduce_without_raw_eval_or_forecast_fitting or test_population_holdout_reproduces_without_train_or_fits or test_population_reproducible_without_eval_and_invariant_to_changed_eval or test_reproduction_from_only_allowed_marts_without_raw_or_forecasting'
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.tmp/pytest-final-close -k "not ($closureExcluded)"
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

O comando reproduz a seleção; o guard adicional e os relatórios JUnit usados nesta
rodada ficam em `.tmp/`, fora do Git. Os dois testes legados que acessam `eval`,
omitidos em fases anteriores enquanto o holdout estava fechado, não estão excluídos
por esse motivo agora: a avaliação one-shot já foi concluída. Isso não autoriza retuning.

## Power BI: alcance da validação

- JSON, ordem das cinco páginas, IDs, referências a tabelas/colunas/medidas e visibilidade são conferidos por código.
- Page 2.1.0, PBIP, PBIR, metadata e definição do SemanticModel são conferidos com os schemas oficiais disponíveis.
- VisualContainer permanece em 2.13.0. A validação utiliza o schema oficial 2.12.0 em memória como verificação de compatibilidade; não declara conformidade integral com uma publicação 2.13.0 indisponível no cache usado.
- O parâmetro segue a sintaxe oficial de expressão compartilhada TMDL. A validação M/TMDL é estrutural; a tentativa de carregar o parser instalado foi impedida pelo acesso negado às bibliotecas WindowsApps, mesmo fora do sandbox.
- Não houve abertura, refresh, execução DAX nem serialização do modelo pelo Desktop. O usuário deve configurar a fonte local e verificar o refresh posteriormente.

## Artefatos e pendências

`.tmp/final_repo_audit.json` reúne inventário por arquivo/tamanho, hashes, privacidade,
notebooks, exclusões, testes e lista exata recomendada para os dois commits.
Nenhum dado é incluído para substituir a reprodução. O PBIX, cache, abas locais de
scripts, CSVs, manifests gerados, ambientes, logs e backups ficam fora do Git.

**SCREENSHOTS_PRESENT**: as quatro capturas manuais finais estão em `docs/assets/powerbi/`
e foram incorporadas ao README. Integridade PNG, dimensões e tamanhos foram conferidos;
nenhuma imagem foi editada, redimensionada ou recomprimida. A extensão duplicada da
primeira captura foi corrigida, sem mudar seus bytes.

Na preparação do stage, `pPowerBIDataRoot` já continha o placeholder genérico. Todas
as definições Power BI foram preservadas por hash. `pip check`, verificações de diff,
privacidade e estrutura foram repetidos; a suíte pytest não foi reexecutada, pois não
houve alteração de código executável. As listas exatas dos dois commits ficam em
`.tmp/commit_1_files.txt` e `.tmp/commit_2_files.txt`, fora do Git. O stage deve coincidir
exatamente com a primeira lista. Não houve abertura do Desktop nem refresh pelo agente.

Após o staging explícito, `git diff --cached --check` encontrou 12 ocorrências
preexistentes em 11 TMDLs: 11 linhas vazias ao final dos arquivos e uma linha com
whitespace em `_Medidas.tmdl`. Os hashes confirmam que esses arquivos não mudaram
nesta rodada. A correção não foi aplicada porque a autorização no SemanticModel
se limita ao valor do parâmetro. Os 167 arquivos do commit 1 permanecem no stage;
os sete do commit 2 permanecem fora. O fechamento está bloqueado nessa checagem,
sem commit ou push. O resultado anterior de `git diff --check` continua válido
para o diff não staged, mas não substitui essa checagem do índice.
