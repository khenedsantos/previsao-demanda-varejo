# Fase 8 — protocolo anterior à avaliação da política

HEAD inicial: `3c52827a140e484d4b4257682bb944f2bb4eb6ae`, main limpa.
Este protocolo é definido antes de calcular qualquer cobertura da política no fold 4.
O forecasting permanece congelado: zero fitting, tuning ou alteração de previsões.

## Método fixo

- LEAN: L=1, q=0,90; BASE: L=2, q=0,95; PROTECTED: L=3, q=0,98.
- `service_level` é alias legado para `target_coverage_level`: quantil alvo da
  distribuição histórica de erro contra venda observada normalizada. Não é fill rate,
  OTIF, serviço real, ausência garantida de ruptura ou atendimento de demanda latente.
- Erro de lead time = soma de forecast menos soma de actual nos primeiros L dias
  de cada fold. Shortfall = máximo do negativo desse erro e zero.
- Calibração temporal: folds 1–3, escala amostral por série (ddof=1) dos 21 erros
  desses folds. Aplicação única no fold 4, sem escolher regra pela cobertura obtida.
- Rótulos de cada observação de calibração vêm do snapshot prospectivo daquele
  fold da Fase 4. Aplicação no fold 4 usa seu snapshot de 18/06. Nenhum rótulo
  full-train é usado na validação retrospectiva. Migrações de classe são possíveis.
- Shortfall padronizado = shortfall / (error_std × sqrt(L)). Quantil empírico
  linear (interpolação entre estatísticas de ordem, pandas/numpy padrão).
- Hierarquia fixa: ABC×XYZ×exposure → ABC×XYZ → XYZ → GLOBAL. Menor nível com
  n ≥ ceil(20/(1−q)): 200, 400, 1000 observações série×fold. Registrar também
  séries distintas; observações correlacionadas não equivalem a amostras independentes.
- Escala nula, não finita ou não positiva bloqueia o pipeline explicitamente;
  não imputar escala, trocar por RMSE ou excluir séries silenciosamente. GLOBAL
  insuficiente também bloqueia. Não inventar uma fórmula após ver o fold 4.
- Safety stock = multiplicador empírico × error_std × sqrt(L).
  Reorder point = lead_time_forecast + safety_stock. Flags são apenas overlays.
- Normal z(q) × mesma escala é benchmark fixo, nunca selecionado por performance.
- Antes da aplicação, diagnosticar dependência nos folds 1–3: correlações dos
  resíduos padronizados e centrados por série em lags 1–6 dentro do mesmo fold;
  razão Var(soma de L resíduos)/soma das variâncias marginais. Não presumir
  independência, normalidade ou garantia de cobertura. sqrt(L) é referência;
  quantis empíricos de somas preservam a dependência observada dentro do lead time.
- Métricas de cobertura são frações de séries, sem pesos. Ratios individuais
  têm denominador estritamente positivo; agregados usam soma(buffer)/soma(forecast).
  Nenhum MAPE, correção do point forecast ou nova classificação de prioridade.

## Snapshot final e limites

Depois da validação, repetir exatamente o método com os quatro folds de train,
seus rótulos prospectivos e error_std da Fase 6. Aplicar aos rótulos finais de 25/06
e às previsões ETS pré-abertura de eval da Fase 7. A tabela de previsões congeladas
não contém actuals; nenhum mart avaliado no holdout nem raw é input desta fase.
as_of=25/06/2024; available_from=26/06/2024. 50.000 séries × três cenários.

Equivalência em dias = reorder_point / média do forecast de sete dias (se >0).
Sem estoque real, posição de inventário, quantidades de compra, custos ou lead time
real: todos os resultados são limiares simulados na escala normalizada.
Os três cenários variam L e q simultaneamente; a comparação não identifica efeitos
causais separados. Mostrar fatores sqrt(L), multiplicadores e forecast acumulado,
sem construir grade ou escolher um cenário vencedor.

Reutilizar os sete exemplos da Fase 6. A + duplo sinal é grupo de investigação,
sem multiplicador adicional. Tabela complementar de concentração: dez maiores
buffers entre séries A por cenário, desempate por store_id/product_id crescentes;
não substituir os sete exemplos gráficos nem escolher casos manualmente.
Verificar hashes dos inputs antes/depois, reprodução
em diretório sem eval e teste explícito de invariância a actuals eval ausentes ou
alterados. Não executar testes legados que refaçam fitting ou abram raw/holdout.
Nenhum commit e nenhuma implementação Power BI.
