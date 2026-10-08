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

## Limitações específicas da Fase 3

- ABC usa contribuição de venda observada normalizada. Censura pode subestimar a relevância de
  produtos; número de lojas por produto também influencia o total. Não é ABC financeiro.
- O ABC global do produto é igual em suas séries, mesmo quando uma loja tem venda local baixa.
  Contagens de produtos na matriz ABC×XYZ não são aditivas entre células.
- Os cortes XYZ/exposição são convenções relativas derivadas dos quantis de train. Não existe
  limite universal ou quebra natural única demonstrada. Mudar a regra altera classes; o relatório
  registra quatro alternativas, incluindo 9.226 trocas ao usar CV diário em lugar de semanal.
- A distinção X/Y/Z nas métricas utilizadas é esperada por construção. Não constitui validação
  independente de previsibilidade; lag 7 é maior na mediana de Z que na de X. Ainda não há erro
  de forecast ou backtesting para comprovar utilidade preditiva dos segmentos.
- CV semanal evita dupla contagem com o CV diário, mas não descreve toda a oscilação intrassemanal.
  Correlação de forma pode ser instável quando o perfil é quase plano e não mede igualdade de nível;
  as séries têm só 12 semanas completas. MAE e CV diário continuam como diagnósticos.
- Separar ruptura de XYZ não remove sua influência indireta na venda observada. Promoção,
  calendário, mudança de nível e censura também afetam CV e estabilidade.
- Quatro séries sem correlação válida recebem Z pela outra métrica, com fallback explícito.
  Em futuros cortes, ausência de evidência suficiente leva a Y_INCOMPLETE_METRICS e exige revisão,
  sem afirmar que a série tem comportamento intermediário comprovado.
- LOW de exposição significa frequência relativamente menor, não disponibilidade adequada:
  pode incluir ruptura em 34,44% dos dias. HIGH mede frequência, não severidade completa;
  duração média nos dias afetados tem mediana menor em HIGH que em LOW.
- A flag de censura aponta associação de ruptura e zeros, não perda comprovada. Sua ausência
  não demonstra demanda não censurada. Não existe score contínuo de risco nem causalidade estimada.
- Perfis A+flag se sobrepõem a AX/AY/AZ+HIGH. Somá-los contaria séries/vendas repetidamente.
  Exemplos próximos à mediana são típicos somente no CV semanal, sem representatividade universal.
- As classificações do train completo são descritivas em 25/06/2024. Reutilizá-las em folds
  anteriores causaria leakage; recalcular ABC/XYZ/quantis por origem quando usados temporalmente.

## Limitações específicas da Fase 4

- O backtest avalia 28 dos 90 dias de train em quatro origens. Não demonstra comportamento em
  outras estações, horizontes, novos produtos/lojas ou mudanças prolongadas; eval segue reservado.
- Forecasting mede venda observada normalizada. Censura, promoções, calendário e mudança de nível
  podem afetar os erros. Nenhuma variável explica causalmente os resultados e não se estimam perdas.
- O recálculo prospectivo resolve o uso indevido das classes finais nos folds, mas os rótulos são
  relativos ao painel e sua composição muda. Métricas agregadas dos grupos misturam essas composições.
- A relação XYZ com performance é parcial: X supera Z em WAPE nos dois modelos, mas Y tem menor
  MAE/RMSE que X, e Z tem menor variabilidade entre folds no Seasonal Naive. Não se ajustou a regra.
- Seasonal Naive vence globalmente e nos quatro folds em WAPE, mas perde ligeiramente em C–Z e
  na flag. Seu WAPE global tem desvio um pouco maior. Não há dominância em todos os critérios.
- HIGH tem maior erro absoluto e subprevisão, mas menor WAPE que LOW, por diferenças de escala.
  Isso não implica previsibilidade intrínseca ou efeito causal da ruptura. Bias negativo não é,
  por si só, risco de ruptura ou justificativa para decisão de compra.
- Existem 263 casos série×fold com soma actual zero por modelo. WAPE e bias_pct permanecem nulos.
  Não há caso assim ao agregar todos os folds. Valores positivos tão pequenos quanto 0,1 produzem
  WAPEs extremos. P05 serve ao diagnóstico, sem remoção de séries ou threshold operacional.
- Exemplos usam extremos no último fold e podem ser dominados pela baixa escala; não representam
  séries típicas. Selecioná-los após observar erros é permitido somente para explicação descritiva.
- O desvio e CV entre quatro folds resumem variação, não significância ou intervalo de confiança.
  Vencer nos quatro folds não garante melhora no holdout final. Não houve tuning de modelos.
- Prefixos menores têm métricas de forma indefinidas e alguns históricos sem ruptura. Fallbacks
  XYZ permanecem explícitos; duração média sem dias afetados fica nula, sem imputação.
- Hashes são reproduzidos no runtime registrado. Dependências ainda não têm lock; versões e
  serialização podem alterar bytes. Telemetria é variável e excluída dos hashes determinísticos.
- Limite de 1 GB do DuckDB não é limite do processo inteiro: pandas/PyArrow e objetos Python
  também consomem memória. Pico medido depende do processo; testes e notebook têm custos próprios.
