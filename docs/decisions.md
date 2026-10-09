# Registro de decisões

## Propósito

Manter rastreabilidade das escolhas técnicas e metodológicas.

## Decisões iniciais

| Decisão | Justificativa | Estado |
|---|---|---|
| FreshRetailNet-50K como dataset | Escolha definida para o projeto | Fonte oficial adquirida e validada |
| Fundação técnica antes de análise | Separar preparação do repositório da implementação | Fundação commitada; Fase 1 implementada |
| Raw imutável e dados fora do Git | Preservar a origem e evitar versionar dados gerados | Diretriz definida |
| Notebooks exploratórios e lógica em src | Separar exploração da implementação definitiva | Diretriz definida |
| Reposição simulada | Lead time e estoque físico não fornecidos pela fonte | Diretriz definida |
| Validação temporal | Respeitar a ordem das observações | Desenho detalhado pendente |

## Registro futuro

Para cada nova decisão: data, contexto, alternativas, escolha e consequências.

## Fase 1 — 2026-10-08

| Decisão confirmada | Evidência/justificativa | Consequência |
|---|---|---|
| Congelar os dois Parquet oficiais por revisão, tamanho e SHA-256 | Fonte Dingdong-Inc, versão 1.0, CC BY 4.0; manifesto com metadados reais | Reexecução confere a identidade, sem substituir raw |
| Usar DuckDB diretamente no Parquet | Profiling SQL em 4.850.000 linhas, sem banco servidor | Limite de memória/temporários e ausência de banco persistente |
| Adotar grão diário data + loja + produto | 4.850.000 chaves distintas, zero duplicatas | Nenhuma deduplicação ou agregação corretiva |
| Preservar train/eval na proveniência | Mesmas 50.000 séries; 90 dias seguidos de sete dias sem sobreposição | Eval reservado como bloco futuro; backtesting dentro de train será definido depois |
| Converter somente dt e acrescentar proveniência no staging | Datas parseáveis; schema de origem conhecido | 21 colunas, mesmas linhas e demais valores; sem transformações analíticas |
| Usar stock_hour6_22_cnt > 0 como ruptura diária nessa janela | Contador coincide exatamente com os índices 6 a 21 do vetor binário | Relatar [06h,22h) e medir separadamente eventos fora da janela |
| Preservar int64 do vetor de ruptura | Divergência entre ficha e schema físico entendida | Não forçar o tipo documentado nem aceitar deriva silenciosa |
| Preservar extremos de discount e clima | Sem evidência suficiente para regra corretiva | Registrar faixas, frequências e pendências sem imputar ou excluir |
| Manter testes de integração com a fonte local | Contratos reais e reprodução completa do staging | Executar ingestão e validação antes do pytest |

Os resultados e limites estão em [data_quality_report.md](data_quality_report.md). Não houve escolha de modelo, reconstrução de demanda, segmentação ou política de reposição nesta fase.

## Fase 2 — 2026-10-08

| Decisão | Justificativa | Consequência |
|---|---|---|
| Abrir somente train.parquet | Eval é holdout final; staging mistura as duas partições | Pipeline da Fase 2 funciona mesmo sem eval e staging presentes |
| Perfil ao corte explícito | Evitar uso de observações posteriores à origem | Filtro anterior a métricas, quantis e exemplos; recalcular em cada origem futura |
| Interpretar *_demand como venda observada normalizada | Não há demanda latente identificada nem unidade física confirmada | Nenhuma imputação, previsão ou decisão de compra |
| Desvio amostral e epsilon numérico 1e-9 | CV indefinido para médias próximas de zero | Nulos preservados; nenhuma classe XYZ associada |
| ADI=n_days/positive_days e CV² dos valores positivos | Descrever ocorrência e tamanho da venda positiva | Sem thresholds; ADI é redundante com zero_ratio nesta cobertura completa |
| Pearson lag 7 e estabilidade em semanas completas | Explicitar estimador e evitar semanas parciais | 12 semanas; comparação dos perfis normalizados de duas metades |
| Comparar ruptura/atividade também dentro de cada série | A média global mistura níveis e frequências distintas | Comparações pareadas descritivas, sem inferência causal |
| Preservar discount=0 e >1 em contagens separadas | 34 valores >1 encontrados em train, produto 37, seis lojas | Sem correção; atividade e desconto não são sinônimos |
| Curvas em três níveis sem rótulos ABC | Concentração muda muito com o grão | Contribuição normalizada; regra de segmentação segue pendente |
| Exemplos por quartis empíricos e máximos válidos | Evitar seleção visual oportunista | Critérios e desempates registrados no resumo; não são classes operacionais |
| Relatório, seis Parquet, JSON e notebook de nove figuras | Separar cálculo reproduzível de apresentação | Lógica em SQL/src; outputs e figuras ignorados pelo Git |

Resultados completos em [demand_understanding_report.md](demand_understanding_report.md).
As escolhas acima descrevem apenas esta análise exploratória. Não congelam thresholds ABC/XYZ
nem metodologia de previsão e não autorizam avanço para outra fase.

## Fase 3 — 2026-10-08

| Decisão | Evidência/justificativa | Consequência |
|---|---|---|
| ABC oficial por produto, propagado às séries | Forte concentração por produto na Fase 2; grão autorizado | 122 A, 167 B, 576 C, sem ABC local por loja-produto |
| Classificar pelo acumulado anterior ao item | Preservar o produto que cruza 80%/95% no intervalo completado | Fronteira auditável, desempate por product_id e tolerância numérica 1e-12 |
| Recalcular ABC diretamente de train | Rastreabilidade da contribuição normalizada | Nenhum uso de eval ou informação financeira inexistente |
| XYZ com CV semanal e correlação da forma | CV diário/semanal redundantes em parte (r=0,81); CV semanal/forma pouco associados | Duas métricas complementares; demais ficam para diagnóstico |
| Regra categórica mediana/caudas | Quatro alternativas calculadas; separação descritiva e ausência de quotas | X favorável em ambos os eixos; Z desfavorável em pelo menos um; Y intermediário |
| Preservar nulos e usar fallback explícito | Quatro séries sem forma válida têm CV semanal elevado | Z_HIGH_CV_NO_PATTERN; nenhuma série descartada ou correlação imputada |
| Zero_ratio apenas diagnóstico, ADI não entra | ADI é transformação de zero_ratio; 74 séries majoritariamente zeradas já estão em Z | Evitar dupla contagem e exceção desnecessária |
| Exposição separada de XYZ | Frequência de ruptura tem interpretação distinta de estabilidade | LOW/MEDIUM/HIGH por p25/p75 recalculados; nenhuma ponderação composta |
| Flag ruptura≥p75 e zeros≥p75 | Reproduz 2.651 séries com alta coincidência de zeros e ruptura | Sinal de possível censura, não demanda perdida comprovada |
| Manter ABC, XYZ, exposição e flag em colunas separadas | Preservar interpretação operacional de cada dimensão | Matriz e perfis prioritários, sem score ou política de reposição |
| Registrar sensibilidade e limites preditivos | Mudar de CV semanal para diário altera 9.226 séries; lag 7 não ordena X/Y/Z | XYZ é estabilidade observada; utilidade preditiva será testada posteriormente |
| Conferir corte e cadeia de hashes de entrada | Impedir reaproveitamento silencioso do perfil integral em data anterior | Recalcular perfil/quantis/classes por origem no backtesting futuro |

Regras e resultados em [segmentation_report.md](segmentation_report.md). A implementação desta fase
não autoriza forecasting, backtesting ou reposição. Nenhum commit final é feito sem autorização.

## Fase 4 — 2026-10-08

| Decisão | Evidência/justificativa | Consequência |
|---|---|---|
| Target é venda observada normalizada | Contrato sale_amount e ausência de demanda latente identificada | Sem correção de censura ou interpretação física/financeira |
| Horizonte único de sete dias | Planejamento curto e padrão semanal; definido antes da avaliação | Nenhuma busca de horizontes com dados futuros |
| Quatro folds, 62/69/76/83 dias de histórico | Primeiro corte preserva oito semanas completas para XYZ | Testes de 29/05 a 25/06/2024, sem sobreposição |
| Origem é o primeiro target antes de observá-lo | Convenção explícita evita ambiguidade | Cutoff é origem menos um dia; fonte sempre anterior à origem |
| Naive constante e Seasonal Naive t−7 | Baselines auditáveis sem tuning | Forecasts precedem a união com actuals; nenhum update no horizonte |
| Recalcular perfil, ABC/XYZ, quantis e exposição por fold | Retrato full-train produziria leakage temporal | Pipeline só depende de raw train e configurações, não de marts finais |
| Preservar duração indefinida sem dias de ruptura | Dois casos no fold 1, um no fold 2 | Validação aceita nulo apenas com taxa/horas/sequência zero; classes inalteradas |
| Métricas consolidadas por somas suficientes | Evitar média de WAPEs e de RMSEs | Percentuais nulos se D=0; nenhum MAPE ou zero artificial |
| Manter labels temporais em série×fold, não em série consolidada | Grupos podem mudar entre cortes | Nível série agrega erro sem inventar segmento fixo; contar entidades distintas com cuidado |
| P05 de D positivo apenas diagnóstico | WAPE extremo é instável em pouca venda | Nenhuma exclusão por baixa escala; 263 casos D=0 por modelo no nível série×fold |
| Escolher Seasonal Naive pelo WAPE global | 42,29% versus 43,49%; ganhos em MAE/RMSE e menor magnitude do bias | Referência global, mantendo exceções C–Z e flag; não é escolha por série |
| Não ajustar XYZ ao erro | X tem menor WAPE, mas Z é mais estável entre folds em SN | Relação preditiva parcial, sem impor ordenação favorável |
| Exemplos por extremos e desempate de IDs no último fold | Transparência e uma origem comum | Exibir denominadores; não apresentar como representativos |
| Separar telemetria de artefatos determinísticos | Tempo e pico de memória variam a cada execução | Nove Parquet e resumo reproduzidos por hash; performance.json fora dessa igualdade |

Resultados e tradeoffs em [forecasting_baselines_report.md](forecasting_baselines_report.md).
A fase termina na recomendação de referência e validação, sem commit ou avanço automático.

## Fase 5 — benchmark preliminar, 2026-10-08

| Decisão | Justificativa | Consequência |
|---|---|---|
| Preservar integralmente o protocolo da Fase 4 | Comparabilidade e isolamento de eval | Mesmos quatro folds, horizonte e target |
| A/N/A como candidato principal pré-declarado | Modelo semanal aditivo simples, compatível com zeros e janela curta | A/A/A apenas no benchmark; nenhuma seleção por erro futuro |
| 135 séries em 27 estratos do primeiro snapshot | Cobrir ABC/XYZ e escalas sem olhar classes futuras | Seleção por hash; custo extrapolado com pesos populacionais |
| SLSQP limitado e sem brute force | Ajuste determinístico com esforço controlado | Falhas/não convergência levam a Seasonal Naive auditável |
| Preservar previsão original antes de max(0, forecast) | Formulação aditiva pode prever venda negativa | Projeção explícita, sem modificar o histórico |
| Limite inicial local de 30 minutos, comunicado antes da medição | Controle de esforço neste ambiente; usuário pediu parada se custo excessivo | Projeção com margem de 39,03 minutos bloqueia execução completa |
| Não classificar ETS em A/B/C/D nesta etapa | Ainda não há comparação de desempenho | Fase 5 parcial; custo não prova inferioridade preditiva |

Nenhum modelo adicional foi avaliado, nenhum holdout aberto e nenhum commit feito nesta etapa.

## Fase 5 — continuação populacional autorizada, 2026-10-08

O quadro preliminar acima registra a decisão histórica. A autorização posterior substitui
o bloqueio de custo: o limite de 30 minutos deixa de se aplicar.

| Decisão | Justificativa | Consequência |
|---|---|---|
| Executar somente A/N/A completo | Autorização explícita após projeção de 39,03 minutos | 200.000 ajustes solicitados; nenhuma execução A/A/A ou tuning |
| Carregar 2.500 históricos por lote | Agregação dos 50.000 excedeu 512 MB antes do primeiro ajuste | Preserva chaves, corte temporal, modelo e forecasts; correção de memória |
| Reutilizar os snapshots/forecasts da Fase 4 por hash | Evitar vazamento e duplicação desnecessária | Mesmos actuals, denominadores e classes prospectivas |
| Parear métricas antes de calcular improvement | Comparação exige cobertura equivalente | Falha explícita em chaves/denominadores divergentes; referência zero indefinida |
| Win rate por série×classe prospectiva | Classes mudam entre origens | Agrega apenas folds pertencentes à classe; contagens podem se sobrepor |
| Exibir ganhos e perdas em todos os segmentos predefinidos | Evitar seleção favorável após ver erros | Erro, bias, folds, materialidade e custo orientam classificação conjunta |
| Híbrido apenas analítico e baseado em folds anteriores | Evitar escolher pelo próprio erro futuro | Mínimo dois folds, ganho WAPE consistente, nenhum RMSE pior e bias absoluto não pior |
| Não repetir imediatamente a população | Autorização dispensa segunda execução antes da revisão | Contratos, hashes, referência SN e seis ajustes reproduzidos |
| Preservar mas não executar dois testes legados que abrem eval | Instrução explícita de manter holdout fechado | Demais testes executados com basetemp local; exclusões documentadas |

Não há commit, reposição, Power BI ou política operacional final nesta continuação.

Classificação após os resultados: **A — ETS claramente superior no backtest observado**.
MAE/WAPE melhoram 14,82%, RMSE 13,32%; vitória nas três métricas nos quatro folds e nos
segmentos predefinidos. Bias global aproxima-se de zero; win rate MAE/WAPE de 88,406% e
mediana de melhoria de 16,53% sustentam materialidade. Custo medido: 29,08 minutos para
população/comparação, zero fallback. Ressalvas: caudas de bias mais largas, 4,256% das séries
com piora ≥10% e bias mais distante de zero nos três primeiros folds. A regra híbrida
conservadora melhora WAPE em 2,15%, mas fica atrás de ETS uniforme; não foi ajustada depois.
Recomendação para revisão: A/N/A como candidato principal; SN permanece referência/fallback.
Nenhuma decisão operacional ou abertura de eval decorre automaticamente dessa classificação.

## Fase 6 — perfil de incerteza e risco, 2026-10-09

| Decisão | Justificativa | Consequência |
|---|---|---|
| Reutilizar forecasts aprovados por hash | Preservar comparabilidade e evitar refit | Nenhuma execução populacional, benchmark ou novo modelo |
| Usar retrato operacional conhecido em 25/06 | Produto da fase é um perfil disponível após os quatro folds | Proibida reutilização retrospectiva em folds; comparação prospectiva anterior intacta |
| Manter bias consolidado negativo e ≥3 folds negativos | Regra preferida, interpretável e empiricamente examinada | 16.529 persistentes; alternativas 2/4 apenas diagnósticas |
| Preservar a flag de censura da Fase 3 | Não confundir exposição, censura potencial e erro do modelo | Quatro células sem score ou demanda imputada |
| Conservar desvio, RMSE e quantis separadamente | Dispersão, erro quadrático e cauda representam aspectos diferentes | Nenhuma escolha automática de fórmula de estoque |
| Avaliar suporte do cruzamento fino com ≥100 séries | Evitar resumos em células muito pequenas | As 27 células passam; limiar não é garantia de precisão |
| Manter extremos e baixa escala na população | Não melhorar métricas mediante exclusões | Trim e p05 usados apenas como sensibilidades claramente identificadas |
| Explicitar dependência do bias global em relação ao fold 4 | Retirá-lo muda bias_pct de −2,17% para +0,98% | Sem alegar subprevisão global estável; 90,59% dos persistentes mantêm bias negativo |
| Usar associação contínua com atividade como complemento | Correlações fracas e mistura de fatores entre séries | Sem faixas arbitrárias, uplift causal ou alteração da matriz |
| Reproduzir apenas agregações da Fase 6 | Forecasts congelados e instrução de não repetir população | 17 Parquet e resumo comparados por hash; refit bloqueado no teste |

A+B com duplo sinal somam 964 séries; 706 são A. Priorização significa investigar na próxima
etapa que vier a ser autorizada, sem compra, ajuste de forecast, safety stock ou reposição.
Entrega preservada sem commit. Eval fechado; nenhuma fase seguinte iniciada.
