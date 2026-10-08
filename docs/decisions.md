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
