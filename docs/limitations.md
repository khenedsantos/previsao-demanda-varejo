# Limitações

## Propósito

Delimitar as interpretações possíveis e evitar conclusões além das evidências.

## Limitações observadas na Fase 1

- São 90 dias em train e sete dias posteriores em eval. Essa janela não permite validar sazonalidade anual e limita os futuros cortes temporais.
- `sale_amount` e `hours_sale` são normalizados por coeficiente global não divulgado. Não representam, comprovadamente, unidades, quilogramas ou moeda, e venda observada não é demanda latente.
- Não há estoque físico nem lead time. Qualquer política futura de reposição será simulada, com parâmetros explicitamente hipotéticos.
- Todas as 50.000 séries apresentam alguma ruptura no período, mas a comparação entre grupos não identifica o efeito causal da ruptura nem quantifica vendas perdidas.
- `stock_hour6_22_cnt` descreve [06h,22h), não as 24 horas. Há 763.399 dias sem ruptura nessa janela e com ruptura fora dela; o rótulo diário precisa sempre explicitar sua janela.
- `discount` contém 17.339 zeros e 34 valores superiores a 1 (máximo 1,088). A ficha não esclarece esses extremos; foram preservados, sem classificação automática como erro.
- Unidades/escala meteorológicas e interpretação operacional do calendário/fuso não estão confirmadas. Não foram aplicados limites físicos arbitrários.
- Há diferenças documentais: 865 produtos observados e na ficha atual versus 863 no artigo; vetor de ruptura int64 observado versus int32 declarado. O tipo observado foi preservado.
- A máscara de disponibilidade do artigo tem polaridade inversa ao indicador de ruptura raw. O código usa a definição da ficha e a consistência empírica do contador.
- Eval foi auditado quanto à qualidade, sem tuning. A avaliação futura deverá respeitar sua posição temporal e documentar a elegibilidade dos dias, inclusive a avaliação sem ruptura usada pelos autores.
- Nenhum desempenho preditivo, demanda reconstruída ou ganho operacional foi estimado nesta fase.

## Evidência

Consulte [data_quality_report.md](data_quality_report.md), [data_dictionary.md](data_dictionary.md) e o [artigo oficial](https://arxiv.org/abs/2505.16319). As pendências semânticas ficam registradas para etapas posteriores; não impedem preservar e validar a fonte nesta fase.
