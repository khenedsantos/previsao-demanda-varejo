# Metodologia

## Propósito

Registrar como o histórico de vendas será usado para apoiar decisões e comunicar incerteza.

## Estrutura prevista

- Qualidade dos dados e limites da observação de demanda.
- Tendência, sazonalidade e volatilidade.
- Baseline e backtesting temporal, sem divisão aleatória de treino e teste.
- Avaliação com MAE, RMSE, WAPE e bias; fórmulas e convenções definidas na Fase 4 abaixo.
- Segmentação ABC/XYZ; critérios definidos na Fase 3 e recalculados por origem na Fase 4.
- Simulação de reposição, estoque de segurança, ponto de reposição e cobertura.
- Comunicação de incerteza e risco operacional.

## Fase 2 — perfil descritivo de train

O mart `data/processed/mart_demand_profile.parquet` tem uma linha por `store_id + product_id`.
Os nomes `*_demand` representam **venda observada normalizada**, não demanda latente. A Fase 2 não
reconstrói demanda censurada, não imputa zeros e não aplica classes ABC/XYZ, modelos ou reposição.

### Fonte e tempo

- O script abre exclusivamente `data/raw/train.parquet`, conferindo seu tamanho, SHA-256 e schema
  contra o manifesto. Não lê eval nem o staging combinado, e funciona sem esses arquivos.
- Janela fixa de referência: 28/03/2024 a 25/06/2024, 90 dias. A função de cálculo aceita um corte
  `as_of` dentro dessa janela e filtra antes de calcular métricas, quantis, semanas e exemplos.
- Exige uma observação por dia/série do início até o corte, sem duplicidade, lacuna, valor de venda
  negativo ou não finito. No corte integral: 4.500.000 linhas e 50.000 séries.
- O mart final é descritivo **em 25/06/2024**. Não pode ser utilizado como feature em origens anteriores:
  o backtesting futuro terá de recalcular perfil, quantis e seleção a cada origem. Não existe backtesting nesta fase.

### Definições do mart

| Campos | Definição |
|---|---|
| `first_date`, `last_date`, `n_days`, `source_split` | Proveniência e janela efetivamente observada; source_split sempre train |
| `mean_demand`, `median_demand`, `std_demand`, `min_demand`, `max_demand`, `total_demand` | Média, mediana, desvio amostral (ddof=1), mínimo, máximo e soma de sale_amount |
| `zero_days`, `zero_ratio`, `positive_days` | Contagem de sale_amount=0, zero_days/n_days e contagem de sale_amount>0 |
| `near_zero_mean`, `coefficient_of_variation` | Média ≤1e-9 sinaliza proximidade numérica de zero; CV=desvio amostral/média somente acima da tolerância |
| `positive_mean_demand`, `positive_std_demand`, `positive_demand_cv_squared` | Estatísticas somente dos valores positivos; CV²=(std/mean)², indefinido se não houver tamanho de amostra ou média adequada |
| `adi` | n_days/positive_days; indefinido quando positive_days=0. Não é a média dos intervalos internos entre eventos |
| `maximum_consecutive_zero_days` | Maior sequência de dias com venda zero, inclusive sequências nas pontas |
| `stockout_days`, `stockout_rate` | Dias com stock_hour6_22_cnt>0 e proporção desses dias |
| `total_stockout_hours`, `mean_stockout_hours_when_affected` | Soma do contador e média somente nos dias com contador>0 |
| `maximum_consecutive_stockout_days` | Maior sequência diária de ruptura em [06h,22h); zero se não houver ruptura |
| `zero_days_with_stockout`, `zero_days_without_stockout` | Decomposição dos zeros segundo ruptura na janela operacional |
| `mean_demand_with_stockout`, `mean_demand_without_stockout`, `stockout_demand_difference` | Médias dentro da série e diferença com−sem; indefinida se um grupo não existir |
| `activity_days`, `activity_rate` | Soma de activity_flag e divisão por n_days |
| `mean_discount` | Média original de discount, incluindo zero e valores acima de 1 |
| `discount_days`, `discount_zero_days`, `discount_above_one_days` | Contagens separadas de 0<discount<1, discount=0 e discount>1; nenhuma correção |
| `mean_demand_with_activity`, `mean_demand_without_activity`, `activity_demand_difference` | Médias dentro da série e diferença com−sem atividade |
| `stockout_rate_with_activity`, `stockout_rate_without_activity`, `activity_stockout_rate_difference` | Taxas condicionais de ruptura dentro da série e diferença com−sem atividade |
| `mean_demand_monday` até `mean_demand_sunday` | Média de venda por weekday; todos os dias disponíveis, sem somar contagens desiguais |
| `weekday_mean_demand`, `weekend_mean_demand` | Médias nos dias segunda–sexta e sábado–domingo |
| `weekend_weekday_difference`, `weekend_weekday_relative_difference` | Fim de semana−dias úteis; e razão fim de semana/dias úteis−1, exigindo média dos dias úteis>1e-9 |
| `lag7_pairs`, `autocorrelation_lag7` | Número de pares separados exatamente por 7 dias e correlação de Pearson entre os dois vetores |
| `complete_weeks`, `mean_weekly_demand`, `std_weekly_demand`, `weekly_coefficient_of_variation` | Semanas completas segunda–domingo, média e desvio amostral dos totais semanais e sua razão |
| `early_valid_weeks`, `late_valid_weeks` | Semanas com média>1e-9 em cada metade cronológica das semanas completas |
| `weekly_pattern_half_correlation`, `weekly_pattern_half_mae` | Correlação e MAE entre os sete valores do perfil normalizado das metades |

Valores matematicamente indefinidos permanecem nulos, nunca zero artificial. A tolerância 1e-9 é
numérica na escala do dataset, sem relação com thresholds de segmentação; nenhuma média de série
real cai abaixo dela nesta janela. Desvios usam n−1. ADI e zero_ratio são redundantes nesta janela:
ADI=1/(1−zero_ratio). Não somar ambos como evidências independentes de intermitência.

### Padrão semanal e sua estabilidade

Lag 7 usa correlação de Pearson nos pares t e t−7, com pelo menos três pares e desvio>1e-9
nos dois vetores. Esse estimador usa médias/variâncias dos pares e é diferente da ACF com
denominador global. O calendário completo garante 83 pares no corte integral.

As semanas incompletas nas pontas são excluídas **somente** das métricas semanais: restam 12
semanas de 01/04 a 23/06/2024. Divide-se o conjunto cronologicamente em duas metades
(floor(n/2) semanas na primeira; o restante na segunda). Cada venda diária é dividida pela média
da própria semana. Semanas de média≤1e-9 ficam fora dessa normalização. Calculam-se sete médias
por metade, uma por weekday, e comparam-se os dois perfis. Exigem-se pelo menos duas semanas
válidas por metade. Perfis constantes invalidam a correlação, mas não o MAE. Quatro séries reais
não têm semanas válidas suficientes; não foram descartadas do mart.

Essas métricas são descritivas. Não há teste de significância, ajuste de tendência, controle de
promoção/ruptura ou afirmação de sazonalidade anual. Perfil agregado e heterogeneidade entre
séries são apresentados lado a lado.

### Comparações, intermitência e exposição à censura

As comparações com/sem ruptura e atividade são calculadas globalmente e dentro das mesmas séries.
As diferenças por série têm peso igual no resumo, enquanto a média global pondera pelos dias
de cada grupo; os sinais podem diferir. Nenhuma comparação isola efeito causal.

O relatório exibe a distribuição completa de zero_days, quantis de zero_ratio, ADI e CV² positivo.
A expressão "zeros na maioria dos dias" significa literalmente >50%, apenas para responder à
contagem descritiva; não é um threshold de intermitência nem XYZ. Grupos por quartis observados de
ruptura preservam empates. O cruzamento ruptura≥p75 e zeros≥p75 é diagnóstico exploratório,
sem classe permanente. A ruptura de 16 horas também é analisada como caso operacional explícito.

### Concentração e seleção de exemplos

Curvas por produto, loja e loja-produto somam sale_amount, ordenam por contribuição decrescente
e desempatam por identificador. A soma é normalizada pela soma de todas as entidades do nível.
Top 1%/5%/20% usam ceil na contagem de entidades. Os números necessários para 80% e 95% incluem
a entidade que cruza cada participação. Não se rotulam entidades como A/B/C. As contribuições
também refletem cobertura de sortimento do painel, sem disponibilidade de receita ou margem.

Exemplos, sempre recalculados somente com dados até o corte:

1. Alta venda/baixa ruptura: média≥p75 e ruptura≤p25; maior média.
2. Alta venda/alta ruptura: média≥p75 e ruptura≥p75; maior média.
3. Baixa venda/baixa ruptura: média≤p25 e ruptura≤p25; menor média.
4. Maior CV matematicamente válido.
5. Maior proporção de zeros.

Desempate por store_id e product_id. Uma série pode atender a mais de uma regra. Nenhum exemplo
foi escolhido pela aparência, e os cortes servem exclusivamente para ilustrar perfis.

### Reprodução e validação

```powershell
.\.venv\Scripts\python.exe scripts/build_demand_profile.py
.\.venv\Scripts\python.exe scripts/render_data_understanding.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
git diff --check
git status
```

SQL em `sql/analytical/demand_profile.sql`; execução em `src/features/demand_profile.py`;
relatório e figuras em `src/reporting/`. O notebook só consome outputs e chama funções de desenho.
O renderizador usa explicitamente o Python/.venv que executa o script. Nove figuras, sem notebooks
adicionais. Raw, staging e artefatos da Fase 1 não são regravados.

DuckDB roda com uma thread e memória limitada a 1 GB, com spill limitado a 2 GB em `.tmp`.
Outputs Parquet têm ordenação total e parâmetros fixos de escrita. O resumo registra hashes de
seis Parquet, hash/revisão da fonte e versões de DuckDB/PyArrow, sem timestamp variável.
Os testes reconstroem todos esses outputs e o JSON em raiz temporária sem eval/staging e
comparam hashes. A garantia de igualdade de bytes é para o mesmo runtime registrado; não para
versões arbitrárias de bibliotecas. As figuras são reproduzidas a partir desses outputs.

Testes sintéticos cobrem constantes, zeros, média quase nula, periodicidade semanal, sequências,
extremos de desconto e calendário inválido. Uma mutação extrema de todos os dias posteriores
ao corte não pode mudar nenhuma métrica, resumo ou exemplo calculado naquele corte.

## Pendências registradas ao encerrar a Fase 2

Definir segmentação e seu uso temporal, baselines/backtesting, incerteza e política simulada
somente após revisão desta fase. Nenhum modelo, ABC/XYZ definitivo ou previsão foi implementado.

## Fase 3 — segmentação e perfil operacional

O objetivo desta fase é manter separadas três dimensões: relevância global do produto (ABC),
estabilidade observada da série loja-produto (XYZ) e exposição à ruptura/possível censura.
Não há score composto, peso, clustering, forecasting ou política de reposição.

### Entradas e proveniência

`scripts/build_segmentation.py` verifica a identidade de **train.parquet** e recalcula a contribuição
dos produtos diretamente de `sale_amount`. Para XYZ e disponibilidade usa o mart da Fase 2,
verificando seu hash, o resumo de proveniência, a partição train, datas e cobertura. Também confere
chaves, número de dias e somas por série contra train lido até o corte. Nenhum arquivo eval,
staging combinado ou relatório global da Fase 1 é lido pelo pipeline da Fase 3.

O corte integral é 25/06/2024. Um corte anterior só é aceito se o perfil da Fase 2 tiver sido
recalculado para exatamente a mesma data; o mart integral é recusado nesse caso. Não existe
implementação de folds ou backtesting nesta fase.

### ABC por contribuição de venda normalizada

Grão: product_id. O total de cada produto é a soma de sale_amount no train. Produtos são
ordenados por total decrescente e product_id crescente. A participação é total do produto / total
do painel, com acumulado nessa ordem e ranking iniciado em 1.

Se P é a participação acumulada **antes** do produto:

- A se P < 0,80;
- B se 0,80 ≤ P < 0,95;
- C se P ≥ 0,95.

O produto que cruza a fronteira permanece na classe cujo intervalo completa. Igualdade numérica
com 0,80/0,95, por tolerância absoluta de 1e-12 na participação, significa fronteira já atingida;
o próximo produto inicia o intervalo seguinte. Empates são resolvidos pelo identificador, sem
forçar todos os empatados à mesma classe. Um produto muito dominante pode cruzar dois limites
de uma vez; não se força a existência de todas as classes em qualquer universo sintético.

Os resultados reais (122 A, 167 B, 576 C) são checks de regressão, não constantes da classificação.
A classe é propagada por produto para as séries e nunca recalculada por loja-produto. A contribuição
não é financeira e também reflete o número de lojas presentes no painel para cada produto.

### Avaliação e escolha das métricas XYZ

Foram calculadas correlações Pearson e Spearman por pares válidos entre CV diário, CV semanal,
correlação da forma semanal entre metades, MAE da forma, lag 7, zeros e ADI. As contagens de pares
são preservadas. CV diário/semanal têm Pearson 0,8109; CV semanal/correlação da forma, −0,0972.
ADI e zero_ratio têm relação determinística monotônica e Spearman 1.

Escolha mínima: **CV semanal + correlação da forma entre metades**. São eixos distintos de
variação dos totais entre semanas e persistência do perfil de weekday. CV diário e MAE permanecem
diagnósticos, evitando acrescentar cortes parcialmente redundantes. Lag 7 não domina a regra.
Zero_ratio fica como diagnóstico: as 74 séries com maioria de zeros já recebem Z. Não se usa ADI
como segundo sinal de intermitência nem se introduz exceção adicional para esse grupo.

Quatro alternativas foram calculadas e ficam registradas com thresholds, contagens, medianas por
classe e número de séries que mudam em relação à escolhida:

| Alternativa | CV baixo/alto | Forma baixa/boa |
|---|---|---|
| Semanal, quartis | p25 / p75 | p25 / p75 |
| Semanal, mediana e caudas (escolhida) | p50 / p75 | p25 / p50 |
| Semanal, tercis | p33⅓ / p66⅔ | p33⅓ / p66⅔ |
| Diário, mediana e caudas | p50 / p75 | p25 / p50 |

Quantis usam interpolação linear e apenas valores válidos de train. Não se demonstrou uma quebra
natural única nas distribuições. A convenção escolhida considera X a interseção das metades
favoráveis e Z a união das caudas desfavoráveis. Não há cotas de tamanho nem escolha por erro de
previsão. Quartis restringiam X a 3.448 séries; tercis ampliavam Z a 27.085. A alternativa escolhida
preserva contraste descritivo com grupos utilizáveis, sem impor equilíbrio artificial.

### Regra XYZ escolhida (weekly_median_tail)

Prioridade de aplicação:

1. Z se CV semanal ≥ p75 **ou** correlação da forma ≤ p25.
2. X se não houver critério Z, CV semanal ≤ p50 **e** correlação da forma ≥ p50.
3. Y nos demais casos.

Thresholds calculados nesta execução: CV p50=0,265992446005; CV p75=0,381015820606;
correlação p25=0,058267078628; correlação p50=0,394743548722. O código deriva esses valores do
perfil; não contém esses números como constantes. Empates permanecem juntos; Z prevalece se
limites coincidirem. ABC, stockout_rate, horas de ruptura, flag de censura e activity_rate não
participam do cálculo de XYZ.

Uma métrica indefinida permanece nula. Se a outra métrica válida atende ao critério Z, usa-se Z
com razão de fallback; caso contrário, Y_INCOMPLETE_METRICS exige revisão sem presumir estabilidade.
As quatro séries reais sem forma válida têm CV semanal entre 1,3119 e 1,9164 e recebem
Z_HIGH_CV_NO_PATTERN. Todas as 50.000 séries têm uma classe e uma razão auditável.

Razões compactas: X_LOW_CV_STABLE, Y_INTERMEDIATE, Z_HIGH_CV, Z_LOW_STABILITY, Z_BOTH,
Z_HIGH_CV_NO_PATTERN, Z_LOW_PATTERN_NO_CV e Y_INCOMPLETE_METRICS. O relatório contém suas definições.

A validação compara as classes em CV diário/semanal, correlação/MAE da forma, lag 7, zeros,
venda média e diferença relativa de fim de semana. A separação nas métricas da regra é esperada
por construção e não comprova previsibilidade. Lag 7 não acompanha a ordem X/Y/Z; desempenho
de forecast permanece uma hipótese a testar em fase posterior.

### Exposição à ruptura e flag de possível censura

A dimensão de disponibilidade usa stockout_rate exclusivamente para os rótulos:

- HIGH se taxa ≥ p75 (0,522222222222 nesta janela);
- LOW se taxa ≤ p25 (0,344444444444), sem atender HIGH;
- MEDIUM nos demais casos.

HIGH prevalece se os quantis coincidirem. As classes são relativas ao painel. LOW pode ter até
34,44% dos dias afetados; não é nível de serviço nem evidência de disponibilidade adequada.
Horas totais, maior sequência e duração média nos dias afetados ficam como métricas de suporte.
As duas primeiras aumentam nas medianas LOW→HIGH, mas a duração por dia afetado diminui: não se
afirma que frequência resume toda a severidade da ruptura.

`censoring_risk_flag = (stockout_rate >= p75) AND (zero_ratio >= p75)`.
O p75 de zero_ratio é 0,055555555556 (cinco dias em 90). Ambos os limites são recalculados.
Os 2.651 casos confirmam o achado anterior; a flag indica alta exposição à **possível censura**,
sem quantificar demanda perdida e sem afirmar causalidade. Não entra no XYZ.

### Contratos dos outputs e matriz operacional

| Output | Grão e conteúdo |
|---|---|
| mart_product_abc.parquet | product_id; total, participação, acumulado atual/anterior, ranking, classe e séries associadas |
| mart_series_xyz.parquet | store_id+product_id; duas métricas utilizadas, classe, regra e razão |
| mart_stockout_exposure.parquet | store_id+product_id; exposição, flag e métricas de disponibilidade |
| mart_operational_profile.parquet | store_id+product_id; ABC propagado, XYZ, exposição, flag, razões, janela e métricas de suporte |
| data/outputs/segmentation/ | Correlações, alternativas, perfis por classe, matriz, cubo de exposição, exemplos e resumo com hashes |

O perfil operacional é a junção de dimensões, sem score final. A matriz ABC×XYZ contém as nove
células, contagem de séries/produtos, venda total e participação global, ruptura média/mediana,
quantidade/fração de flags e quantidade de HIGH. Produtos podem estar em várias classes XYZ;
seus counts não são aditivos. Série e venda são aditivas. Perfis prioritários A+flag se sobrepõem
a AX/AY/AZ+HIGH e não devem ser somados como grupos exclusivos.

### Exemplos sem seleção visual

- AX com maior venda total;
- AX com maior stockout_rate;
- AZ com maior stockout_rate;
- A com flag, maior stockout_rate e depois maior zero_ratio, sem score numérico de risco;
- CX e CZ mais próximos da mediana de CV semanal da própria combinação.

Desempate por store_id, depois product_id. Proximidade à mediana refere-se somente à métrica
declarada, não a um centróide multidimensional. Uma série pode ser escolhida por mais de uma regra.
O notebook apenas consome esses exemplos e os demais outputs; não recalcula regras analíticas.

### Reprodução, testes e prevenção de leakage

```powershell
.\.venv\Scripts\python.exe scripts/build_segmentation.py
.\.venv\Scripts\python.exe scripts/render_segmentation.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
git diff --check
git status
```

Os testes cobrem fronteiras ABC, igualdade exata, empates, contribuições inválidas, thresholds
recalculados, invariância de XYZ a alterações em disponibilidade/ABC/atividade, nulos, propagação,
matriz e conservação de totais. Os 11 Parquet e o resumo JSON são reconstruídos em raiz temporária
sem eval nem staging e comparados por hash no runtime registrado. O notebook tem nove figuras.

**No backtesting futuro, ABC/XYZ, thresholds e quantis deverão ser recalculados com dados
disponíveis até cada origem temporal quando usados como features ou critérios de decisão.**
Não reutilizar retrospectivamente a classificação do train completo. A guarda de corte não substitui
a futura validação do desenho temporal. Forecasting/backtesting seguem fora desta fase.

## Fase 4 — Baselines e backtesting temporal

As restrições de escopo anteriores descrevem cada fase. Nesta Fase 4, somente Naive e Seasonal
Naive são autorizados. Target: `sale_amount`, venda observada normalizada. Eval permanece reservado;
a execução lê exclusivamente raw train, sem staging ou marts full-train anteriores.

### Origens e informação disponível

Horizonte único de sete dias, em quatro folds de histórico crescente. Datas e desenho foram
reportados antes de congelar a implementação. Histórico inicia em 28/03/2024:

| Fold | Fim do histórico | Dias | Origem / início do teste | Fim do teste |
|---|---|---|---|---|
| 1 | 28/05/2024 | 62 | 29/05/2024 | 04/06/2024 |
| 2 | 04/06/2024 | 69 | 05/06/2024 | 11/06/2024 |
| 3 | 11/06/2024 | 76 | 12/06/2024 | 18/06/2024 |
| 4 | 18/06/2024 | 83 | 19/06/2024 | 25/06/2024 |

`forecast_origin` é o primeiro dia previsto **antes** de sua observação; `cutoff_date=origin−1`.
Os testes não se sobrepõem. O primeiro histórico conserva oito semanas completas para XYZ;
quatro folds equilibram histórico e repetição da avaliação nos 90 dias disponíveis.
Não existe shuffle, partição aleatória, teste de múltiplos horizontes ou escolha com eval.

Por origem, o filtro de data antecede todas as métricas do perfil e todos os quantis. ABC por
produto, regra XYZ mediana/caudas, exposição e flag usam somente esse prefixo. Regras da Fase 3
permanecem iguais; parâmetros são novamente estimados. O resumo registra thresholds, nulos
e contagens por origem; não há análise retrospectiva misturada com a avaliação prospectiva.

A duração média da ruptura nos dias afetados é nula quando nenhum dia foi afetado. Dois casos
no primeiro fold e um no segundo exigiram aceitar esse nulo somente quando taxa, horas totais
e maior sequência são zero. Trata-se de uma extensão da validação de suporte, sem imputação
ou mudança de regras. A reprodução da Fase 3 permanece coberta pelos testes.

### Previsões e métricas

Naive repete a venda no cutoff nos sete dias. Seasonal Naive copia a venda exatamente sete
dias antes de cada target_date; todos esses valores precedem a origem. Forecasts ficam prontos
antes da união com actuals do horizonte. Grão: store_id+product_id+forecast_origin+target_date+model;
fold_id, cutoff_date, horizon_step (1–7) e source_observation_date permitem rastrear a origem.

Para `e=forecast−actual`, N previsões e D=soma(actual):

| Métrica | Fórmula | Interpretação |
|---|---|---|
| MAE | soma(abs(e))/N | Erro absoluto na escala normalizada |
| RMSE | sqrt(soma(e²)/N) | Maior peso aos erros grandes |
| WAPE | soma(abs(e))/D | Erro relativo agregado; indefinido se D=0 |
| Bias | soma(e)/N | Assinado: negativo indica subprevisão |
| Bias percentual | soma(e)/D | Assinado; indefinido se D=0 |

Não há MAPE. Nulos não viram zeros. Consolidações usam somas suficientes, não a média de
percentuais/RMSEs das séries. O mart traz N, D, soma de forecasts, erros absolutos, quadráticos
e assinados, além de contagens de séries/produtos/folds e flag de percentual indefinido.

Níveis: série×fold×modelo, série×modelo, fold×modelo, global×modelo, ABC, XYZ, exposição, flag e
ABC×XYZ por modelo. Mais cinco níveis segmento×fold atendem à estabilidade, sem cortes extras
arbitrários. Cada level tem dimensões aplicáveis e demais campos nulos. Filtrar level antes de
somar evita duplicação. A série consolidada não recebe rótulo temporal único. Contagens distintas
podem se sobrepor entre grupos porque classes mudam por fold; não somá-las como entidades únicas.

Melhoria relativa `(Naive−Seasonal Naive)/Naive` aplica-se a MAE/RMSE/WAPE; positiva favorece SN.
Referência zero resulta em nulo; não se usa essa fórmula para bias assinado. Referência global
é o menor WAPE consolidado, com MAE/RMSE, bias e estabilidade relatados como critérios adicionais.

### Comparações, baixa escala e estabilidade

XYZ é testado nos erros futuros de cada corte, sem redefinir classes com base no desempenho.
X tem menor WAPE que Z nos dois baselines, mas a hipótese de maior estabilidade não é universal:
Z tem menor desvio/CV do WAPE entre folds no Seasonal Naive. Y tem MAE/RMSE menores que X.

Bias por série agrega os 28 dias antes dos quantis; cortes por ABC/XYZ/exposição/flag usam as
somas de erros. Subprevisão não é automaticamente risco de ruptura. Diferenças entre grupos são
associações descritivas, sem controle causal. Denominadores acompanham os resultados: 263 casos
série×fold por modelo têm D=0; no agregado por série nenhum é indefinido. Baixa escala é descrita
pelo p05 dos D positivos, sem excluir casos ou criar threshold operacional. Empates no p05 são incluídos.

Estabilidade usa média, desvio amostral ddof=1 e mínimo/máximo por fold para MAE/RMSE/WAPE/bias/bias_pct.
CV=desvio/média apenas para métricas de erro e média positiva, nunca para bias assinado. A média
do WAPE entre folds não é o WAPE global consolidado. Quatro folds não equivalem a inferência estatística.

### Exemplos, reprodução e apresentação

Seleção determinística no último fold: menor e maior WAPE SN em AX; menor bias SN negativo em AZ;
maior WAPE SN entre HIGH; menor bias SN negativo entre flags; maior diferença positiva de
WAPE(SN)−WAPE(Naive). Desempates por loja e produto. WAPE nulo não concorre em regras de WAPE.
Sem filtro para esconder baixa escala: os denominadores são exibidos. Os exemplos são extremos
e descritivos, sem participação em previsão, classificação ou ajuste.

`scripts/run_baseline_backtest.py` publica nove Parquet, JSON de resumo/proveniência e telemetria
separada; `scripts/render_forecasting_baselines.py` executa dez figuras no notebook. Relatório:
[forecasting_baselines_report.md](forecasting_baselines_report.md). Lógica reside em src e na SQL
de perfil aprovada. Testes validam métricas conhecidas, fontes temporais, t−7, grãos, somas,
thresholds e invariância de forecasts/segmentos após mutar todo o futuro. A reprodução em raiz
sem eval, staging ou marts compara os nove hashes e summary.json; tempo/memória ficam fora.
