# Fase 7 — protocolo anterior à abertura analítica de eval

Autorização explícita do usuário após aprovação e commit das fases 0–6, HEAD `d6681aa`.
Esta é a primeira abertura **analítica** autorizada de eval; verificações de ingestão/qualidade
anteriores não constituíram avaliação preditiva. Preflight: 106 testes aprovados e dois testes
que abrem eval desmarcados, em 161,26 s. As duas exclusões deixam de ser necessárias após
a abertura autorizada desta fase. Nenhuma lógica das fases anteriores será alterada.

Antes de ler actuals de eval, persistir previsões dos dois modelos para todas as 50.000 séries
e registrar seus hashes. Cada ETS A/N/A usa os 90 dias até 25/06/2024; sete passos diretos,
26/06–02/07, sem atualização intrahorizonte. Seasonal Naive usa exclusivamente 19–25/06.
Reutilizar a função ETS congelada: sazonalidade aditiva 7, sem tendência, estados estimados,
SLSQP maxiter=200/ftol=1e-6, use_brute=False, remove_bias=False, uma thread numérica.
Preservar previsão original, clipping em zero, fallback e razões. Não repetir a população
para reproduzir análises: os forecasts completos sem actuals são o input imutável.

Antes de métricas, verificar hash/schema do manifesto, 350.000 linhas, 50.000 séries, sete
datas, chaves únicas, período e cobertura igual aos IDs conhecidos em train. Não alterar raw.
Erro = forecast−actual; MAE, RMSE, WAPE, bias, bias_pct mantêm fórmulas anteriores. Percentuais
indefinidos permanecem nulos; sem MAPE. Improvement=(SN−ETS)/SN somente em MAE/RMSE/WAPE.

Usar os labels finais conhecidos em 25/06 da Fase 6: ABC, XYZ, exposição, censura, persistência
e célula de risco. Preservar 16.529 persistentes, 1.028 com duplo sinal e 706 A com duplo sinal.
Comparar esses grupos prospectivamente, sem refazer suas regras. Não interpretar bias como
demanda perdida ou diferença de grupos como causalidade.

Incerteza: Spearman das quatro medidas históricas (desvio, RMSE, p90/p95 absolutos) com MAE e
RMSE holdout por série. Quartis calculados **somente no perfil histórico**, antes de abrir eval:
Q1≤q25, Q2≤q50, Q3≤q75, Q4>q75; empates juntos. Não recalibrar cortes no holdout. Baixa escala
usa o p05 de actual_total dos 28 dias históricos, já congelado (10,13), e também informa casos
com actual holdout zero. Não excluir extremos nem definir risco pelo WAPE.

Comparar as cinco métricas holdout com agregado, média, mínimo, máximo, desvio amostral dos
quatro folds e fold 4. Win rate e distribuição de improvement por série são complementares;
empates preservam atol=1e-12/rtol=1e-10 da Fase 5. Não introduzir regra híbrida ou outro modelo.
Reutilizar todos os sete exemplos da Fase 6. Separadamente, descrever observações com/sem
ruptura contemporânea em eval (`stock_hour6_22_cnt>0`), sem usá-las em forecasts ou labels.

Classificação A/B/C/D será um julgamento documentado da evidência conjunta: erro absoluto,
WAPE, bias, consistência temporal, segmentos e falhas/clipping. Nenhum limite de aceitabilidade
operacional de bias foi estabelecido; não inventar um após observar os resultados. Um único
holdout de sete dias não prova estabilidade de longo prazo ou validade de política de estoque.
Nenhum tuning, seleção retrospectiva de exemplos, lost sales, reposição ou Power BI.

`protocol.json` registra fontes, hashes dos artefatos/código congelados, cortes e runtime.
`execution.json` e `eval_opening.json` separam timestamps do resumo determinístico. Novos
outputs ficam em final_holdout e marts holdout; artefatos anteriores não serão sobrescritos.
Releitura do mesmo holdout somente para validar/reproduzir a metodologia já congelada.
Não fazer commit nesta entrega.

## Registro técnico anterior à abertura

Durante a execução train-only, um teste sintético encontrou diferença de representação da
chave dt: Parquet devolvia date e DuckDB timestamp. Foi normalizado somente o tipo de data
na junção posterior com actuals, sem mudar datas, forecasts, configuração ou cálculo de erro.
Os seis testes unitários passaram novamente antes da abertura. `protocol_at_fit_start.json`
preserva o protocolo original; `protocol_amendment.json` registra horário e hashes anterior/final.
O protocolo final preserva todos os valores estatísticos, os hashes de código usados na geração
das previsões e o hash do protocolo inicial. O primeiro acesso analítico ocorre depois dessa
correção registrada. Nenhum ajuste populacional foi repetido.
