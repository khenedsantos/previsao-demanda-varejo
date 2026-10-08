# Dicionário de dados

## Propósito

Documentar o schema observado nos Parquet oficiais da revisão `08c1fab7f9257bc73679d415d65d644165d351d4`. Grão: data + loja + produto. Tipos abaixo são Arrow; o schema físico Parquet está em [data_quality_report.md](data_quality_report.md).

## Campos

| Campo | Tipo raw → staging | Significado | Origem | Observações e limitações |
|---|---|---|---|---|
| city_id | int64 | Identificador da cidade | Fonte | Anonimizado; 18 valores; sem nome geográfico |
| store_id | int64 | Identificador da loja | Fonte | Anonimizado; 898 valores; compõe a chave |
| management_group_id | int64 | Grupo de gestão do produto | Fonte | Identificador, não medida numérica |
| first_category_id | int64 | Categoria de primeiro nível | Fonte | Sem rótulo comercial publicado |
| second_category_id | int64 | Categoria de segundo nível | Fonte | Sem rótulo comercial publicado |
| third_category_id | int64 | Categoria de terceiro nível | Fonte | Sem rótulo comercial publicado |
| product_id | int64 | Identificador do produto | Fonte | 865 valores observados; compõe a chave |
| dt | string → date32 | Data da observação diária | Fonte | ISO YYYY-MM-DD; não contém fuso horário; compõe a chave |
| sale_amount | float64 | Venda diária normalizada | Fonte | Coeficiente global não divulgado; não assumir unidades físicas ou monetárias; não equivale a demanda latente |
| hours_sale | list<float64> | Venda normalizada por hora | Fonte | 24 posições; soma coerente com sale_amount dentro de tolerância numérica; mesma limitação de unidade |
| stock_hour6_22_cnt | int32 | Quantidade de horas com ruptura na janela operacional | Fonte | 0 a 16; igual à soma das posições 6 a 21 do vetor, isto é, [06h,22h); não mede estoque físico |
| hours_stock_status | list<int64> | Indicador horário de ruptura | Fonte | 24 posições; 1 = ruptura, 0 = sem ruptura; ficha declara int32, arquivo contém int64 |
| discount | float64 | Fator de desconto informado pela fonte | Fonte | 2.773 valores, de 0 a 1,088; significado dos extremos 0 e >1 não confirmado; não corrigido |
| holiday_flag | int32 | Indicador de feriado | Fonte | Domínio 0/1; calendário operacional não reconstruído |
| activity_flag | int32 | Indicador de atividade promocional | Fonte | Domínio 0/1; intensidade e mecanismo da promoção não fornecidos |
| precpt | float64 | Precipitação | Fonte | Unidade/escala não especificada na ficha; valores preservados |
| avg_temperature | float64 | Temperatura média | Fonte | Unidade não confirmada; sem conversão |
| avg_humidity | float64 | Umidade média | Fonte | Unidade/escala não confirmada; sem conversão |
| avg_wind_level | float64 | Nível médio de vento | Fonte | Escala não confirmada; não interpretar como velocidade física |
| source_split | string, somente staging | Partição oficial train ou eval | Derivada | Proveniência, sem mudança do papel temporal dos arquivos |
| source_file | string, somente staging | Nome do Parquet de origem | Derivada | train.parquet ou eval.parquet; rastreabilidade |

## Nulabilidade e semântica

Todos os campos raw e elementos das listas são nullable no schema, mas nenhum nulo foi observado. Os dois campos de proveniência são não nulos no staging. Os vetores têm comprimento fixo 24 e não foram expandidos em linhas.

O artigo usa uma máscara matemática de disponibilidade com polaridade oposta ao indicador de ruptura raw. Não confundir as convenções. Venda zero sem ruptura na janela não comprova demanda zero, e venda positiva pode coexistir com ruptura em parte do dia.

Fonte: [ficha oficial congelada](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K/blob/08c1fab7f9257bc73679d415d65d644165d351d4/README.md). Frequências, quantis e comparação documental estão no relatório de qualidade; métricas não foram imputadas nem reescaladas.
