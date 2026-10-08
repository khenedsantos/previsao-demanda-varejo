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
