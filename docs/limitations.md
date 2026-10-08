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

## Limitações específicas da Fase 2 (somente train)

- Os números da seção anterior registram o escopo da Fase 1 (train+eval). Na Fase 2 usam-se somente
  4.500.000 registros de train. Há 16.039 discount=0 e 34 discount>1 nessa partição.
- O mart usa nomes *_demand por contrato, mas continua medindo venda observada. Zeros, CV e ADI
  podem refletir censura, não apenas demanda ou intermitência do consumidor.
- A ruptura se mede em [06h,22h), enquanto sale_amount é diário. Mesmo com 16 horas afetadas,
  pode haver venda fora da janela; não há medida validada da demanda perdida.
- Comparações dentro da série não controlam promoção, calendário, tendência ou seleção dos dias
  afetados. Médias globais e diferenças por série têm ponderações distintas e podem divergir de sinal.
- Atividade e discount não são equivalentes. Os 34 valores >1 concentram-se no produto 37 em
  seis lojas, sem activity_flag=1. Isso sugere investigação específica do fator; não identifica erro
  de cadastro, preço de referência ou sua causa. Não há preço para verificar tais hipóteses.
- ADI e zero_ratio são transformações um do outro nesta janela de cobertura completa. Não devem
  ser tratados como evidências independentes na segmentação futura.
- Correlação lag 7 e estabilidade semanal são estatísticas exploratórias, sem teste de significância
  ou controle de tendência. Há só 12 semanas completas e quatro séries sem estabilidade calculável
  por insuficiência de semanas com média positiva nas metades. Nulos foram preservados.
- Agregação por produto/loja também depende de quantas séries de cada entidade estão no painel.
  As curvas não representam receita, margem nem o sortimento completo de todas as lojas.
- Quartis usados para comparação e exemplos são derivados de train e não são thresholds operacionais
  nem classes XYZ. Há empates, tamanhos de grupos diferentes e exemplos extremos não representativos.
- O perfil integral resume informações até 25/06/2024. Usá-lo para origens anteriores introduziria
  vazamento; a função suporta corte anterior, mas o desenho de backtesting ainda está pendente.
- Reprodutibilidade por hash é testada com as versões registradas. As dependências do projeto ainda
  não têm arquivo de lock; mudança de versão pode alterar ordem numérica/serialização e requer validação.
