# Walkthrough do portfólio

### Em 30 segundos

O projeto investiga venda possivelmente censurada por rupturas, compara previsões
de curto prazo e simula proteção para reposição. No holdout final, o ETS reduziu o
WAPE em aproximadamente 14,85% frente ao Seasonal Naive. Nenhum cenário atingiu seu
target hipotético no fold 4: a conclusão gerencial é priorizar investigação e obter
dados operacionais reais antes de automatizar pedidos.

### Em 3 minutos

1. Leia os resultados no [README](../README.md): 50.000 séries, horizonte de sete dias e limites da escala normalizada.
2. Veja a separação entre fonte, marts e camada BI na [arquitetura](architecture.md).
3. Confira o [holdout final](final_holdout_evaluation_report.md): decisões congeladas antes de abrir `eval`, comparação pareada e segmentação prospectiva.
4. Percorra o Power BI: **01** síntese → **02** diagnóstico → **03** cenários → **04** decisão. Configuração local em [powerbi_report.md](powerbi_report.md).
5. Observe o julgamento gerencial: ETS como referência inicial, investigação de séries relevantes/expostas e cenários como sensibilidade; sem compra automática ou causalidade presumida.

### Em 15–30 minutos

| Foco | Onde olhar |
|---|---|
| Desenho temporal e vazamento | [Metodologia](methodology.md), [protocolo do holdout](final_holdout_protocol.md) |
| Qualidade e rastreabilidade | [Qualidade](data_quality_report.md), [manifesto](../config/source_manifest.yaml) |
| Baselines e ETS | [Baselines](forecasting_baselines_report.md), [avaliação estatística](statistical_forecasting_report.md) |
| Incerteza e risco | [Diagnóstico](forecast_uncertainty_and_risk_report.md), [validação prospectiva](final_holdout_evaluation_report.md) |
| Reposição | [Protocolo](replenishment_simulation_protocol.md), [resultados](replenishment_simulation_report.md) |
| Implementação e apresentação | [src](../src/), [notebooks 01–07](../notebooks/) |
| Evidência de engenharia | [Testes](../tests/), [validação final](final_validation.md) |
| Consumo e decisão | [Contrato BI](powerbi_data_contract.md), [medidas](powerbi_measures.md), [relatório](powerbi_report.md) |

Os relatórios anteriores registram a evidência disponível em cada etapa; menções antigas
a “eval congelado” descrevem aquela fronteira temporal. O estado final e as restrições
para novo tuning estão no README e no relatório do holdout.
