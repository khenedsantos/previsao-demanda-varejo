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

## Fase 5 — benchmark e evidência populacional

- Foram medidos apenas 135 históricos de séries, em quatro origens e duas especificações.
  Cinco séries por estrato não cobrem integralmente a cauda de custo e falhas. Nenhum fallback
  na amostra não implica ausência de falhas entre as 50.000 séries.
- Projeção temporal é ponderada pelo tamanho dos estratos; margem de 25% é uma convenção
  operacional, não intervalo de confiança. O custo tabular da Fase 4 aproxima overhead ainda
  não medido no pipeline completo. Carga da máquina altera o tempo efetivo.
- Pico de 528,20 MiB corresponde ao benchmark, não ao backtest populacional. Não se pressupõe
  disponibilidade integral dos 7,78 GiB de RAM física ou speedup linear com paralelismo.
- A pausa inicial por custo foi superada por autorização explícita de A/N/A completo. A margem
  do benchmark não garante duração; tempos reais separam ajustes, I/O, comparação e notebook.
  Uma falha de memória antes de qualquer ajuste exigiu leitura em lotes, sem mudança analítica.
- Projeção não negativa afeta bias; frequência e magnitude populacionais ficam no relatório.
  Valores originais são preservados. Não existe imputação ou correção de censura.
- Os quatro folds avaliam somente 28 dias. Ganho populacional dentro de train não é validação
  externa; não há teste de significância ou garantia de repetição em eval, que permanece fechado.
- Um ganho médio pode coexistir com maior subprevisão ou perdas relevantes por série. Win rate,
  melhoria ponderada global, distribuição de perdas e custo precisam ser considerados juntos.
- ABC/XYZ mudam por origem. Win rate por série×classe usa subconjuntos de folds e permite que
  uma série figure em mais de uma classe. Esses totais não somam necessariamente 50.000.
- A análise híbrida tem somente dois folds após o período mínimo de observação. Não é política
  operacional aprovada nem prova de vantagem fora da amostra; nenhuma regra foi afinada por resultado.
- Casos D=0 e referência SN zero permanecem indefinidos para os percentuais correspondentes.
  Pequenos denominadores geram caudas extremas. Exemplos são selecionados por extremos, sem
  representatividade e sem influência na seleção de modelo.
- Não foi repetida a população completa. Contratos, hashes e seis ajustes reproduzidos dão
  evidência delimitada; outra execução integral dependerá da próxima decisão do usuário.
- Dois testes legados de ingestão/staging abririam eval. Foram preservados e excluídos desta
  rodada para respeitar o holdout fechado; isso deve acompanhar a contagem de testes executados.
- Na execução populacional, o bias global melhora (−3,27% → −2,17%), mas o p05 do bias_pct
  por série piora (−20,58% → −23,86%) e o p95 aumenta (18,00% → 29,43%). A magnitude do bias
  piora nos folds 1, 2 e 3; no fold 4 persiste subprevisão de 10,45%. Menor erro médio não
  garante calibração individual melhor. A flag=True ainda apresenta bias_pct de −7,68%.
- WAPE melhora em todos os folds, mas seu desvio entre folds aumenta de 1,39 para 1,72 ponto
  percentual. 5.797 séries perdem em MAE/WAPE e 4,256% pioram pelo menos 10%. A classificação
  A é relativa à evidência conjunta deste backtest, sem alegar dominância universal.
- Reprodução bit a bit dos ajustes também exige a configuração de threads do runner. A primeira
  validação, com o runtime padrão do pytest, divergiu até 0,000124 em seis ajustes; usando uma
  thread numérica os mesmos valores foram reproduzidos exatamente. O teste fixa esse contexto
  com threadpoolctl (já presente na stack), sem relaxar tolerâncias ou modificar forecasts.

## Fase 6 — incerteza e risco descritivos

- São apenas 28 erros por série, provenientes de quatro folds; p90/p95 dependem de poucas
  observações. Quantis empíricos não constituem intervalo preditivo calibrado, nível de serviço
  ou garantia de cobertura futura. Não se assume independência dos erros para agregar lead time.
- O retrato final de ABC/XYZ/exposição usa train até 25/06. Serve ao diagnóstico disponível
  depois dessa data, sem validade prospectiva nos folds anteriores. Os outputs da Fase 5 e
  suas classes por origem permanecem intactos. Não houve abertura do holdout.
- Persistência descreve o backtest; a matriz usa o próprio sinal do bias em sua definição.
  Diferenças de bias entre suas células são parcialmente mecânicas, não validação independente
  de capacidade preditiva da matriz. Não há escore causal ou estimativa de demanda oculta.
- O sinal do bias global muda ao excluir fold 4: −2,17% vira +0,98%. Embora 90,59% dos
  persistentes mantenham bias negativo nesse diagnóstico, não se garante estabilidade futura.
- Remover diagnosticamente as caudas p01/p99 reduz RMSE de 0,6723 para 0,4705, evidenciando
  sensibilidade a extremos. Os resultados oficiais incluem todos os registros.
- D<=p05 inclui 2.501 séries por empates. WAPE mediano de 61,13% coexiste com desvio absoluto
  menor; WAPE isolado não define risco. Os 263 casos série×fold com D=0 mantêm percentuais nulos.
- Censoring=True está contido em HIGH pela definição preservada. Ausências de células com
  LOW/MEDIUM são estruturais, não perda de dados. Frequência de subprevisão não cresce com a
  flag: 50,09% versus 50,23%; magnitude e dispersão aumentam, o que é uma afirmação diferente.
- Os p75 de alta incerteza e o mínimo de 100 séries por célula são convenções descritivas,
  não thresholds operacionais calibrados. Dependência entre séries/folds limita inferência
  mesmo em células com milhares de observações. Não se executou teste de significância.
- Participações são de venda observada normalizada, não receita, estoque físico ou lost sales.
  Ruptura pode censurar vendas; erro em relação à venda observada não revela demanda latente.
- Associações entre activity_rate e erro são fracas e sujeitas a composição. Não equivalem às
  associações diárias da Fase 2, nem sustentam causalidade promocional ou mudança do modelo.
- Exemplos são determinísticos, mas ilustrativos. LOW significa baixa exposição relativa;
  o exemplo de menor MAE tem baixa escala e ainda apresenta dias de ruptura.
- Os dois testes legados que abrem eval permanecem preservados e excluídos desta rodada.
  Reprodução byte a byte vale para o runtime registrado; telemetria e notebook não entram
  no contrato de igualdade dos 17 Parquet e do resumo. Nenhuma política operacional foi criada.

## Fase 7 — limites do holdout final

- São sete dias em uma única origem. Confirmação fora do backtest não garante estabilidade
  em outras estações, mudanças de nível, lojas/produtos futuros ou políticas de reposição.
- Eval foi aberto após o congelamento das fases 0–6. A partir disso, não pode orientar tuning
  e depois ser reapresentado como teste intocado. Reproduzir a mesma avaliação não aumenta
  a amostra nem cria nova evidência independente.
- Actual é venda observada normalizada e pode ser censurada. Bias/subprevisão não identificam
  demanda perdida, unidades físicas, receita ou estoque insuficiente. Não há estimativa de lost sales.
- Perfis históricos podem antecipar diferenças de erro, mas grupos têm escalas e dependências
  distintas. Spearman/quartis não provam causalidade ou calibração de intervalos preditivos.
- Quartis vêm de 28 erros históricos por série; MAE/RMSE holdout vêm de sete. Caudas e sinal
  do bias têm amostra curta. Não se recalibrou qualquer threshold usando a resposta do holdout.
- Baixa escala histórica e denominador zero no holdout são diagnósticos diferentes. Percentuais
  indefinidos ficam nulos; win rate direto e improvement relativo podem ter denominadores distintos.
- Ruptura contemporânea é descrição posterior por observação. Uma série pode ter dias com e sem
  ruptura; somar n_series dos dois grupos duplica entidades. Esses campos não são features futuras.
- Não existia limite aprovado de aceitabilidade operacional de bias. Reportar seu valor não
  permite declará-lo aceitável para estoque ou definir uma política. A classificação A/B/C/D
  deve considerar toda a evidência sem inventar um threshold retrospectivo.
- Previsões e regras permanecem congeladas. Reprodução por hash depende do runtime registrado;
  tempos/memória/timestamps são separados. Os artefatos anteriores permanecem protegidos.

- No holdout, menor erro ETS não equivale a melhor bias: −2,25% versus +0,28% do baseline.
  A classe X tem bias_pct ETS −5,67%. Não há política operacional que torne esses valores
  automaticamente aceitáveis, mesmo com ganhos de MAE/RMSE/WAPE em todos os segmentos.
- A persistência histórica separa fracamente a ocorrência de bias negativo em sete dias:
  56,12% versus 54,29%. O duplo sinal não produz a maior taxa de dias subprevistos; CENSORING_ONLY
  tem bias_pct mais negativo. Não reinterpretar retrospectivamente as flags para forçar sucesso.
- As 2.501 séries de baixa escala histórica têm WAPE ETS 55,83%, embora MAE seja 0,2176,
  menor que 0,4359 nas demais. Há 61 séries com actual holdout zero; percentuais ficam nulos.
- A associação de ruptura contemporânea combina maior frequência de subprevisão com bias
  agregado positivo: frequência e magnitude podem divergir. Esse recorte posterior não pode
  ser confundido com as flags históricas ou usado para modificar previsões já congeladas.
