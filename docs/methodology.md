# Metodologia

## Propósito

Registrar como o histórico de vendas será usado para apoiar decisões e comunicar incerteza.

## Estrutura prevista

- Qualidade dos dados e limites da observação de demanda.
- Tendência, sazonalidade e volatilidade.
- Baseline e backtesting temporal, sem divisão aleatória de treino e teste.
- Avaliação com MAE, RMSE, WAPE e bias; fórmulas e convenções ainda serão definidas.
- Segmentação ABC/XYZ; critérios ainda serão definidos.
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

## Pendências das próximas fases

Definir segmentação e seu uso temporal, baselines/backtesting, incerteza e política simulada
somente após revisão desta fase. Nenhum modelo, ABC/XYZ definitivo ou previsão foi implementado.
