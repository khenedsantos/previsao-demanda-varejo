# Entrega Power BI

O relatório traduz resultados congelados em prioridades de investigação e limites
para operacionalização. Destina-se a gestores, planejamento, analistas e leitores
do portfólio; não é um sistema automático de pedidos.

## Páginas e navegação

| Página | Papel |
|---|---|
| 00 Validação | Auditoria interna; `HiddenInViewMode`, preservada no projeto |
| 01 Visão Executiva | Síntese de previsão, exposição, sinais e cobertura |
| 02 Demanda & Forecast | Venda observada × ETS e concentração do erro |
| 03 Planejamento de Reposição | Comparação de cenários e proteção simulada |
| 04 Recomendações & Decisão | Três recomendações, ações, limites e próximos passos |

As páginas 01–04 foram aprovadas e congeladas. A página 00 continua acessível ao
autor em edição; ocultá-la da leitura não é um controle de segurança.
As quatro capturas finais estão em `docs/assets/powerbi/` e na seção Power BI do
[README](../README.md#power-bi).

## Modelo e interações

Modelo estrela com três dimensões (`dim_series`, `dim_date`, `dim_scenario`) e três
fatos (`fact_forecast`, `fact_replenishment`, `fact_scenario_validation`), além da
tabela `_Medidas`. As cinco relações são unidirecionais, de dimensão para fato.
A cobertura do fold 4 é global por cenário: filtros de série não a tornam segmentada.

Na página 03, o slicer de cenário filtra KPIs e exposição, mas **não** os dois gráficos
comparativos. A página 02 usa filtros ABC/XYZ/exposição; sua leitura editorial é uma
síntese global. A página 04 é editorial, sem slicer, gráfico ou card de KPI.

WAPE, RMSE, viés, melhoria relativa, contadores de risco, buffer, limiar e cobertura
usam as medidas existentes. Fórmulas e contexto estão no [catálogo de medidas](powerbi_measures.md).
O [contrato](powerbi_data_contract.md) define grãos e semântica;
o [sistema visual](powerbi_visual_system.md) define cores e hierarquia.

### Configuração da fonte local

1. Gere os CSVs com `python scripts/build_powerbi_layer.py`, após disponibilizar os marts congelados requeridos. A saída é `powerbi/data/`; esses dados não são versionados.
2. Abra `powerbi/previsao-demanda-varejo.pbip` no Power BI Desktop com suporte a PBIP, PBIR Enhanced e TMDL.
3. Antes do refresh, configure em **Transformar dados → Gerenciar parâmetros** o parâmetro de texto **`pPowerBIDataRoot`** para o caminho absoluto da pasta `<repo>\powerbi\data`, sem barra final.
4. O valor versionado é `C:\PATH\TO\previsao-demanda-varejo\powerbi\data`. É um placeholder deliberado: não existe resolução automática confiável em relação ao PBIP.
5. As seis queries concatenam o parâmetro com o nome original de cada CSV. Cabeçalhos, encoding, delimitador, tipos e transformações permanecem iguais.
6. Ao salvar uma configuração pessoal no Desktop, restaure o placeholder em `definition/expressions.tmdl` antes de publicar alterações no Git. Nunca publique o diretório pessoal.

PBIX, cache e configurações locais ficam ignorados. Um clone sem cache contém o modelo
e o relatório, mas precisa da exportação local para exibir dados. O fechamento não
executou refresh nem alterou o PBIX. Reabra o projeto para carregar a definição atual,
evitando salvar uma sessão antiga do Desktop sobre os arquivos atualizados externamente.

A implementação usa [expressões compartilhadas TMDL](https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-overview).
Os [arquivos locais e compartilhados do PBIP](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset)
são tratados separadamente: `editorSettings.json`, `.platform` e layout do modelo
fazem parte da definição; cache, `localSettings.json` e alterações M não aplicadas
ficam fora. Abas locais `TMDLScripts/` são excluídas; o pacote canônico permanece em
`powerbi/tmdl/measures_pack.tmdl`. Esse pacote é referência e não precisa ser reaplicado.

## Limites da leitura

Venda, buffer e limiar estão em escala normalizada. Rupturas podem censurar venda;
nenhum indicador mede demanda perdida. A simulação não fornece estoque físico,
quantidade a comprar ou impacto financeiro. Targets são hipotéticos; cobertura
histórica não é fill rate/OTIF. Recomendações priorizam investigação e piloto controlado.

## Validação e manutenção

O fechamento verifica JSON, schemas disponíveis, bindings, referências do modelo,
ordem/visibilidade das páginas, hashes e a substituição isolada das fontes.
Os visuais mantêm a versão 2.13.0 e usam o schema oficial 2.12.0 como verificação de
compatibilidade; isso não equivale à validação integral contra 2.13.0 ou à execução
do motor visual/DAX. Não houve refresh. Veja [validação final](final_validation.md).
