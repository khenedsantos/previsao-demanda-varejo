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
