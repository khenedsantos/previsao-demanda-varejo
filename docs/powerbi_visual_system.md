# Sistema visual Power BI — Previsão de demanda

Contrato visual global para as páginas executivas deste projeto. A Página 01 é a
primeira aplicação. Páginas futuras devem reutilizar os tokens e os mapas abaixo:
consistência semântica vem antes de decoração ou variação visual. Nenhuma regra
visual autoriza mudanças de medidas, dados, relacionamentos ou análises.

## Tokens

| Token | Hex | Meaning | Allowed Uses | Forbidden Uses |
|---|---|---|---|---|
| BACKGROUND | #F7F5F0 | Fundo editorial | Canvas executivo | Fundo saturado alternativo |
| SURFACE | #FFFFFF | Superfície distinta quando necessária | Bloco que precisa de contraste | Mosaico de cards brancos |
| TEXT_PRIMARY | #202927 | Informação principal | Títulos, números, Actual | Substituir warning sem label |
| TEXT_SECONDARY | #68716E | Informação de apoio | Subtítulos, labels, Target | Identificar ETS |
| TEXT_MUTED | #8B928F | Metadados | Notas, datas, rodapé | Informação crítica sem contraste |
| DIVIDER | #D9D6CF | Separação discreta | Linhas finas | Bordas pesadas |
| PRIMARY | #2F6659 | Identidade e destaque | ETS, seleção, quantitativo único, sinal favorável adequado | Indicar que BASE é recomendado |
| PRIMARY_LIGHT | #DDE9E5 | Destaque suave | Seleção e preenchimento leve | Texto pequeno com baixo contraste |
| BASELINE | #9AA19E | Referência neutra | Seasonal Naive, referência Normal | ETS ou HIGH |
| WARNING | #9B5145 | Atenção operacional | HIGH, gap negativo, duplo sinal | Classe A ou Z por si só |
| MEDIUM | #A17C56 | Exposição intermediária | MEDIUM, subprevisão isolada | Garantir gravidade ou compra |
| LOW | #54786B | Exposição baixa observada | LOW | Garantir ausência de ruptura |

## Mapas semânticos obrigatórios

| Mapa | Entidade | Hex | Interpretação |
|---|---|---|---|
| Forecast | ETS | #2F6659 | Modelo ETS congelado |
| Forecast | Seasonal Naive | #9AA19E | Baseline |
| Forecast | Actual | #202927 | Venda observada normalizada |
| Exposure | HIGH | #9B5145 | Atenção operacional |
| Exposure | MEDIUM | #A17C56 | Exposição intermediária |
| Exposure | LOW | #54786B | Baixa exposição observada |
| ABC | A | #2F6659 | Maior contribuição observada |
| ABC | B | #6F9388 | Contribuição intermediária |
| ABC | C | #B7CBC4 | Menor contribuição observada |
| XYZ | X | #53756D | Estabilidade observada X |
| XYZ | Y | #839991 | Estabilidade observada Y |
| XYZ | Z | #AEBBB6 | Estabilidade observada Z; não warning automático |
| Scenario | LEAN | #7C918A | Hipótese LEAN |
| Scenario | BASE | #2F6659 | Hipótese BASE; não recomendação |
| Scenario | PROTECTED | #405D56 | Hipótese PROTECTED; não superioridade |
| Coverage | Target | #68716E | Target hipotético |
| Coverage | Observed Coverage | #2F6659 | Cobertura histórica global, fold 4 |
| Coverage | Normal Reference | #9AA19E | Referência histórica Normal |
| Coverage | Negative Gap | #9B5145 | Cobertura abaixo do target |
| Coverage | Positive Gap | #2F6659 | Cobertura acima do target, se ocorrer futuramente |
| Risk Cell | NEITHER | #B8BDBA | Nenhum dos dois sinais |
| Risk Cell | UNDERFORECAST_ONLY | #A17C56 | Somente subprevisão persistente |
| Risk Cell | CENSORING_ONLY | #8B7064 | Somente censura |
| Risk Cell | CENSORING_AND_UNDERFORECAST | #9B5145 | Coexistência de sinais para investigação |

Quando um único cenário estiver selecionado, um quantitativo pode usar PRIMARY.
A cor do cenário não indica ruim/bom/melhor. ABC não representa risco; XYZ não
representa severidade. A participação Z em um indicador textual usa TEXT_SECONDARY,
conforme a especificação da Página 01; séries categóricas XYZ usam seu mapa fixo.
Contagens da linha de síntese usam TEXT_PRIMARY com labels explícitos.

Os três cenários congelados têm gap negativo. A Página 01 usa WARNING no gap e no
status atual. Se os dados forem substituídos no futuro, revisar o sinal e aplicar
o mapa Positive Gap antes de publicar; não presumir que a cor constante é uma regra
condicional automática. Esta tarefa não altera o DAX para produzir cores.

## Tipografia, grid e hierarquia

Segoe UI regular; Segoe UI Semibold em títulos e valores. Canvas 1280 × 720, margens
de 48 px e grid preferencial de 8 px. O desenho específico admite os deslocamentos
de header e divisores definidos no briefing.

| Uso | Tamanho visual de referência | Implementação |
|---|---|---|
| Título | 24–26 px | Textbox 18,75 pt (aprox. 25 px) |
| Subtítulo | 11–12 px | 8,5–9 pt |
| Seção | 13–14 px | 10,5 pt, Semibold |
| KPI label | Aproximadamente 10 px | 8 pt, mínimo do schema de formatação nativa |
| KPI value | 20–24 px | 15–18 pt; 17 pt no texto de melhoria |
| Notas | 8–9 px | Textbox 6,75 pt (aprox. 9 px) |

Os tamanhos de formatação de visuais são em pontos; as posições do canvas são em
pixels. O tema usa somente tamanhos aceitos por seu schema (mínimo de 8 pt).
Notas menores estão em textboxes PBIR. Conferir legibilidade na renderização real.

Preferir espaço em branco a containers. Indicadores são visuais nativos transparentes,
sem borda, sombra ou preenchimento interno destacado. Não usar títulos gigantes,
bold excessivo, gauges, rainbow, custom visuals ou caixas decorativas. Cores sempre
acompanham labels, valores e posição; nunca são o único meio de identificação.

## Implementação da Página 01

Página existente `90da913c52719518493f`, editada no lugar, sem alterar sua ordem.
34 objetos nativos: 15 cardVisual transparentes, 14 textboxes, um barChart horizontal,
um slicer e três separadores shape. As medidas continuam no modelo `_Medidas`.
Nenhum número esperado foi gravado como substituto de medida no visual.

O slicer usa `dim_scenario[scenario]`, dropdown, seleção única e sem Select All.
A seleção inicial não foi injetada: selecionar BASE uma vez no Desktop e salvar.
Contagens e WAPEs não recebem o filtro de cenário pelo modelo existente; buffer e
cobertura recebem. Interações da barra com os indicadores e o slicer foram desativadas
por `NoFilter`, evitando alterar a síntese por clique em HIGH/MEDIUM/LOW.

As barras usam seletores explícitos de categoria, cores do mapa Exposure, labels com
três casas e ordenação por Average Safety Stock decrescente. Percentuais usam duas
casas; as quatro contagens usam inteiros sem abreviação. Coverage Gap continua
formatado em percentual, conforme a medida existente; não é melhoria relativa.

O tema [previsao_demanda_theme.json](../powerbi/theme/previsao_demanda_theme.json)
centraliza a paleta, classes tipográficas e estilos básicos para reutilização global.
**O tema foi criado e validado, mas não registrado como customTheme do relatório.**
Aplicá-lo globalmente mudaria a aparência herdada da página 00. Para preservar
integralmente esse trabalho manual, o report.json e o tema-base ficaram intactos,
e a Página 01 recebeu formatação explícita equivalente. Futuras páginas devem usar
este contrato. A migração visual da página 00 requer uma tarefa própria; não importar
o tema sobre ela automaticamente. dataColors não substitui os mapas semânticos.

## Auditoria e limites de validação

- Backup de definições: `.tmp/pbir-backup-before-page01/`, com SHA-256.
- Estado inicial/hashes: `.tmp/page01_before.json`.
- Build, posições, bindings, cores, arquivos e hashes: `.tmp/page01_build_report.json`.
- Auditoria de cores: `.tmp/powerbi_color_audit.json`.
- Reconciliação numérica de validação: `.tmp/page01_numeric_validation.json`.
- Scripts locais idempotentes: `.tmp/build_page01.py` e `.tmp/validate_page01.py`.

JSON, referências, nomes e valores de propriedades nativas, dimensões, colisões de
retângulos e IDs foram conferidos por código. Os hashes verificam a preservação da
página 00, modelo, relacionamentos, PBIX e CSVs. O script recusa objetos inesperados
e alterações concorrentes; repetir o build correto não duplica nem regrava visuais.

O Desktop exportou visualContainer **2.13.0**, ainda indisponível na publicação
oficial consultada. O identificador original foi preservado. A validação estrutural
dos visuais usou o schema oficial **2.12.0 como verificação de compatibilidade**,
trocando a URL somente na cópia em memória do validador. Isso não confirma
validação integral contra 2.13.0. Page 2.1.0 e demais schemas disponíveis foram
validados em suas versões exatas. O tema foi validado contra reportThemeSchema 2.157.

Referências oficiais: [estrutura PBIR](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report),
[schemas de relatório](https://github.com/microsoft/json-schemas/tree/main/fabric/item/report),
[schemas de tema](https://github.com/microsoft/powerbi-desktop-samples/tree/main/Report%20Theme%20JSON%20Schema).

Não houve renderização nem execução de DAX no Power BI nesta tarefa. Reconciliação
numérica local usa somente os CSVs de consumo já existentes, sem fitting, refresh,
nova análise ou alteração de fontes. Não equivale a testar o motor visual/DAX.

Para inspecionar, feche sem salvar uma sessão antiga do PBIP, reabra o projeto,
selecione BASE e confira números, cores, ausência de cortes, dropdown e os três
cenários. Capture a Página 01 para revisão. Se o Desktop rejeitar a definição,
considerar a entrega falha e restaurar somente os arquivos desta construção usando
o backup e o inventário do build, preservando quaisquer edições manuais posteriores.

Classificação de entrega: **APROVADA PARA INSPEÇÃO VISUAL NO POWER BI**.
Não significa aprovação final de design. Sem commit e sem implementação da Página 2.
