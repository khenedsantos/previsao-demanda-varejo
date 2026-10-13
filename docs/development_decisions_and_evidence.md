# Decisões de desenvolvimento e evidências

Este índice liga decisões e limites do projeto às evidências disponíveis. O objetivo
de negócio e os resultados estão no [README](../README.md); as justificativas por
fase permanecem em [decisions.md](decisions.md), sem serem reproduzidas aqui.

**A — Comprovada:** existe código, teste, commit ou relatório identificável.
**B — Parcial:** a implementação é verificável, mas parte da proveniência não é.
**C — Não comprovada:** requer evidência adicional. Essas classes qualificam
a evidência, não a qualidade do modelo.

## Evolução incremental

O histórico contém 12 commits até `6040751`. Alguns marcos verificáveis:

| Entrega | Commit |
|---|---|
| Ingestão e qualidade | [4bfe8ce](https://github.com/khenedsantos/previsao-demanda-varejo/commit/4bfe8ce) |
| Segmentação operacional | [cbfd4dd](https://github.com/khenedsantos/previsao-demanda-varejo/commit/cbfd4dd) |
| Baselines e backtesting | [4dfaa9d](https://github.com/khenedsantos/previsao-demanda-varejo/commit/4dfaa9d) |
| Avaliação ETS | [6a7ccec](https://github.com/khenedsantos/previsao-demanda-varejo/commit/6a7ccec) |
| Holdout final | [3c52827](https://github.com/khenedsantos/previsao-demanda-varejo/commit/3c52827) |
| Simulação de reposição | [c5f1178](https://github.com/khenedsantos/previsao-demanda-varejo/commit/c5f1178) |
| Relatório Power BI e fontes portáveis | [7878ee6](https://github.com/khenedsantos/previsao-demanda-varejo/commit/7878ee6) |
| Documentação e capturas finais | [6040751](https://github.com/khenedsantos/previsao-demanda-varejo/commit/6040751) |

**A:** entregas incrementais. **B:** os commits agregam trabalho por fase; não
registram todas as tentativas.

## Problemas e correções

- **A — Histórico sem ruptura:** o diff de `4dfaa9d` em
  [stockout_exposure.py](../src/segmentation/stockout_exposure.py) passa a aceitar
  duração indefinida somente quando taxa, horas e sequência de ruptura são zero.
  O teste `test_no_stockout_history_keeps_undefined_duration_without_changing_rules`
  em [test_forecasting_baselines.py](../tests/test_forecasting_baselines.py) cobre o caso e rejeita inconsistências.
- **A/B — Memória na execução ETS:** o [relatório estatístico](statistical_forecasting_report.md)
  registra falha ao carregar todos os históricos e a correção por lotes de 2.500 séries,
  implementada em [statistical_backtesting.py](../src/forecasting/statistical_backtesting.py).
  A implementação é verificável; o log original citado no relatório não é versionado.

## Decisões e alternativas documentadas

| Decisão verificável — A | Evidências e alcance |
|---|---|
| Comparar Naive e Seasonal Naive; usar o segundo como referência | [Baselines](forecasting_baselines_report.md), [implementação](../src/forecasting/baselines.py). Escolha global, sem selecionar retrospectivamente o vencedor por série. |
| Executar A/N/A na população | [Relatório ETS](statistical_forecasting_report.md), [especificações e fallback](../src/forecasting/ets.py). A/A/A aparece no benchmark; isso não constitui comparação populacional nem busca ampla de modelos. A análise híbrida também está documentada. |
| Recalcular segmentos por origem e separar previsão de avaliação | [Backtesting](../src/forecasting/backtesting.py), [protocolo do holdout](final_holdout_protocol.md), [testes temporais](../tests/test_forecasting_baselines.py). |
| ABC por produto e XYZ por CV semanal e estabilidade da forma | [Segmentação](segmentation_report.md): quatro alternativas comparadas e sensibilidade dos rótulos; [testes](../tests/test_segmentation.py) de fronteiras, empates e nulos. |
| Calibrar reposição nos folds 1–3 e validar no fold 4 | [Protocolo](replenishment_simulation_protocol.md), [testes](../tests/test_replenishment_simulation.py). Método empírico oficial; Normal é referência. |
| Separar grãos e contextos de filtro no Power BI | [Contrato](powerbi_data_contract.md), [medidas](powerbi_measures.md), [relatório](powerbi_report.md) e [sistema visual](powerbi_visual_system.md). |

**B — Antecedência dos protocolos:** os documentos declaram congelamento antes da
avaliação, e o código contém proteções temporais. Os protocolos de holdout e reposição
foram incluídos nos commits das respectivas entregas; o histórico Git sozinho não
comprova a ordem de todas as execuções. Hashes locais também não equivalem a uma
atestação independente de data.

## Validações, resultados desfavoráveis e limites

- **A:** os [testes de baselines](../tests/test_forecasting_baselines.py) verificam
  invariância das previsões e segmentos ao alterar o futuro, somas suficientes e
  denominadores zero. Os [testes BI](../tests/test_powerbi_layer.py) verificam chaves,
  órfãos, relações e reconciliação com números congelados.
- **A:** o [holdout](final_holdout_evaluation_report.md) preserva o pior bias do ETS
  frente ao baseline e a confirmação limitada das flags. A vantagem em erro não é
  apresentada como validação integral da metodologia de risco.
- **A:** a [simulação](replenishment_simulation_report.md) mostra que nenhum target
  nominal foi atingido no fold 4. Cenários não equivalem a estoque físico, pedido,
  fill rate ou garantia de serviço. As [limitações](limitations.md) também distinguem
  venda normalizada, censura potencial e demanda latente não observada.
- **A/B:** [final_validation.md](final_validation.md) registra 136 testes aprovados
  e 12 exclusões; logs completos e guard temporário não estão no Git. Isso documenta
  aquela execução, sem afirmar uma nova execução ou validação integral do motor Power BI.

Para preparar uma demonstração técnica, consulte as [perguntas de estudo](technical_interview_preparation.md).
