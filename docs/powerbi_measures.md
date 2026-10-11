# Catálogo de medidas Power BI

29 medidas no catálogo: Forecast Rows preservada, seis revisadas e 22 novas.
O pacote contém 28 definições, todas em `_Medidas`, com os nomes físicos em minúsculas informados pelo usuário.

## Aplicação segura

[measures_pack.tmdl](../powerbi/tmdl/measures_pack.tmdl) usa `createOrReplace` com **`ref table _Medidas`**.
Só os objetos de medida declarados são criados/substituídos; não há declaração de tabela, coluna, partição ou relacionamento.
`Dummy`, `Forecast Rows`, demais medidas não listadas e tabelas físicas ficam fora do escopo.
O PBIX local preexistente não foi aberto nem editado. O script é para o modelo já descrito pelo usuário.

Sintaxe confirmada na [documentação oficial de scripts TMDL](https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-scripts)
e de [descrições e propriedades TMDL](https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-overview).
A validação local cobre estrutura, referências e fórmulas equivalentes nos CSVs; não executa o motor DAX/TMDL do Desktop.
O Preview no modelo real é a conferência final antes de Apply, conforme a [documentação da Exibição TMDL](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-tmdl-view).

1. No PBIX existente, abra a Exibição TMDL e uma aba de script vazia.
2. Copie todo o arquivo `measures_pack.tmdl` e cole nessa aba, sem arrastar a tabela inteira.
3. Clique **Preview**: confirme somente 28 medidas em `_Medidas`, sem remoção de Dummy, Forecast Rows ou alterações de tabelas/relacionamentos.
4. Sem erros em Problems/Output e com esse escopo confirmado, clique **Apply**.
5. Confira as quatro pastas e as 29 medidas; salve o PBIX normalmente, sem atualizar dados.

## Catálogo

| Measure | Display Folder | Purpose | Format | Important semantic restriction |
|---|---|---|---|---|
| Forecast Rows | 01 Forecast | Contagem existente de linhas de forecast; sem alteração no pacote | Inteiro, 0 casas esperado; não alterado | ETS 350.000; Seasonal Naive 350.000; Total 700.000 |
| MAE (revisada) | 01 Forecast | Erro absoluto médio na escala normalizada. | 0.000 | Requer exatamente 1 model. |
| RMSE (revisada) | 01 Forecast | Raiz da média dos erros quadráticos; não média de RMSEs. | 0.000 | Requer exatamente 1 model. |
| WAPE (revisada) | 01 Forecast | Ratio das somas dos erros absolutos e actual; nunca média de WAPEs. | 0.00% | Requer 1 model; denominador zero retorna BLANK. |
| Bias % (revisada) | 01 Forecast | Erro assinado relativo ao actual; negativo indica subprevisão. | 0.00% | Requer 1 model; denominador zero retorna BLANK. |
| Actual Total | 01 Forecast | Actual único, usando ETS como cópia canônica para evitar duplicação entre modelos. | #,##0.00 | Remove somente model/model_code; mantém date e filtros de dim_series. |
| Forecast Total | 01 Forecast | Soma do forecast congelado na escala normalizada. | #,##0.00 | Requer 1 model; não soma modelos alternativos. |
| Underforecast Rate | 01 Forecast | Proporção de previsões diárias com error < 0. | 0.00% | Requer 1 model; zero ocorrências dá 0; sem linhas dá BLANK. |
| ETS WAPE | 01 Forecast | WAPE do ETS independentemente do filtro atual de modelo. | 0.00% | Limpa model e model_code; preserva filtros de datas/séries. |
| Seasonal Naive WAPE | 01 Forecast | WAPE do baseline Seasonal Naive. | 0.00% | Limpa model e model_code; preserva filtros de datas/séries. |
| WAPE Improvement vs Baseline | 01 Forecast | Melhoria relativa do WAPE ETS contra o baseline. | 0.00% | BLANK se faltar algum modelo ou baseline tiver WAPE zero. |
| Average Safety Stock (revisada) | 02 Replenishment | Buffer simulado médio na escala normalizada, não unidades físicas. | 0.000 | Requer 1 cenário; não é compra recomendada ou estoque real. |
| Average Reorder Point (revisada) | 02 Replenishment | Limiar simulado médio na escala normalizada, não estoque físico. | 0.000 | Requer 1 cenário; sem posição atual ou quantidade a comprar. |
| Buffer Ratio | 02 Replenishment | Ratio das somas de buffer e forecast acumulado, não média dos ratios individuais. | 0.00% | Requer 1 cenário; denominador zero retorna BLANK. |
| Average Equivalent Coverage Days | 02 Replenishment | Média da cobertura equivalente; ignora BLANKs e não representa dias reais garantidos de estoque. | 0.000 | Requer 1 cenário; equivalência na escala prevista. |
| Safety Stock Above Forecast Rate | 02 Replenishment | Proporção de séries com buffer simulado acima do forecast de lead time. | 0.00% | Requer 1 cenário; não indica ruptura nem recomendação de compra. |
| Target Coverage | 03 Validation | Hipótese de cobertura do cenário, não service level real, fill rate ou OTIF. | 0.00% | Requer 1 cenário; não responde a filtros de série ou data. |
| Observed Coverage | 03 Validation | Resultado global da validação temporal histórica no fold4. | 0.00% | Requer 1 cenário; não responde a filtros de série ou data. |
| Coverage Gap | 03 Validation | Cobertura observada menos target; fração assinada equivalente a pontos percentuais ao multiplicar por 100. | 0.00% | Requer 1 cenário; não responde a filtros de série ou data. |
| Normal Reference Coverage | 03 Validation | Cobertura histórica global da referência Normal no fold4. | 0.00% | Requer 1 cenário; não responde a filtros de série ou data. |
| Coverage Status | 03 Validation | Compara a cobertura histórica com o target hipotético. | texto | Requer 1 cenário e gap disponível; BLANK não é target atingido. |
| Series Count | 04 Executive | Quantidade de séries distintas no contexto da dimensão. | #,##0 | Responde a filtros de dim_series; datas/modelos não retrofiltram a dimensão. |
| High Exposure Series | 04 Executive | Quantidade de séries HIGH no contexto atual. | #,##0 | Interseção com os filtros atuais; retorna 0 quando não há séries elegíveis. |
| Double Signal Series | 04 Executive | Quantidade de séries com os dois sinais históricos. | #,##0 | Interseção com os filtros atuais; retorna 0 quando não há séries elegíveis. |
| A Double Signal Series | 04 Executive | Quantidade de séries A com os dois sinais históricos. | #,##0 | Interseção com os filtros atuais; retorna 0 quando não há séries elegíveis. |
| A Buffer Share | 04 Executive | Participação de A no buffer simulado do cenário. | 0.00% | Requer 1 cenário; força A no numerador e remove só abc_class no denominador; mantém os demais filtros. |
| Z Buffer Share | 04 Executive | Participação de Z no buffer simulado do cenário. | 0.00% | Requer 1 cenário; força Z no numerador e remove só xyz_class no denominador; mantém os demais filtros. |
| High Exposure Average Safety Stock | 04 Executive | Buffer simulado médio das séries HIGH; escala normalizada. | 0.000 | Requer 1 cenário; intersecta exposure com o filtro atual, sem forçar HIGH sobre LOW. |
| Selected Scenario | 04 Executive | Cenário único ou instrução textual de seleção. | texto | Nenhum ou vários cenários: Selecione um cenário. |

## Semântica dos filtros

- Métricas diretas de forecast exigem `HASONEVALUE(fact_forecast[model])`: sem modelo único ficam BLANK. Um total com um único modelo selecionado continua válido.
- Actual Total e os WAPEs forçados removem **somente model e model_code**, antes de impor o modelo canônico. Datas e atributos de dim_series continuam filtrando.
- Reposição, shares e validação exigem `HASONEVALUE(dim_scenario[scenario])`; selecionar vários cenários não produz soma de alternativas. Filtro direto na fato não substitui seleção na dimensão.
- Contadores de risco e a média HIGH usam `KEEPFILTERS`: cruzam o recorte desejado com a seleção existente. Contagem sem elegíveis dá 0; média sem linhas dá BLANK.
- A/Z Buffer Share substituem somente o filtro da própria classe no numerador e o removem no denominador, preservando cenário, outras classes, exposição, IDs e sinais. Se outra seleção eliminar todas as séries A/Z, o numerador pode ficar BLANK.
- Cobertura histórica permanece global no fold4; filtros ABC/XYZ/exposure/data não a tornam segmentada. Nenhuma medida introduz relação fato-fato ou modifica direção de filtro.
- Coverage Gap armazena fração e usa `0.00%` conforme solicitado: −0,10352 aparece como −10,35%, correspondendo a **−10,352 p.p.** de diferença. Não multiplicar a expressão por 100 com esse formato; não é melhoria relativa.
- Os formatos arredondam somente a exibição. Dados/métricas conservam a precisão original. Escala normalizada não é receita, unidade física, estoque real ou pedido.

## Validação

Resultados e testes de contexto em `.tmp/measure_validation.json`, ignorado pelo Git.
Somente os seis CSVs autorizados foram usados para cálculos; nenhum pipeline foi chamado.
As equivalências locais testam filtros de data, ABC, XYZ, exposição e cruzamentos, totais mistos,
model_code conflitante, shares condicionais, interseção de risco, denominadores zero e ausência de linhas.
A validação local não substitui a execução do script no motor DAX do modelo real.


Resultado local: **PASS**, 335 verificações de estrutura/referências, números e contextos.
ETS WAPE 35,621479%; baseline 41,831405%; melhoria 14,845129%.
Actual canônico 417.568,523, contado uma vez. Séries 50.000; HIGH 12.606;
duplo sinal 1.028; A + duplo sinal 706. Buffer Ratio 53,289855% / 54,241323% / 62,957636%.
SS/ROP, cobertura histórica, participações A/Z e média HIGH preservados.
Os seis CSVs mantiveram seus hashes; nenhuma análise ou fonte foi escrita.
