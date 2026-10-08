"""Duas previsões de sete dias, sem atualização por valores do horizonte."""

from datetime import timedelta


HORIZON = 7
MODELS = ("naive", "seasonal_naive")


def create_predictions(connection, forecast_origin):
    """forecast_origin é o primeiro dia previsto, antes de observar sua venda.

    A tabela train contém o histórico. Mesmo que o chamador forneça linhas futuras,
    as consultas selecionam apenas cutoff=origin−1 e origin−7..origin−1.
    Não há acesso a actual do horizonte nesta função.
    """
    cutoff = forecast_origin-timedelta(days=1)
    end = forecast_origin+timedelta(days=HORIZON-1)
    connection.execute("""
        CREATE TEMP TABLE predictions AS
        WITH dates AS (
            SELECT cast(value AS DATE) AS target_date FROM generate_series(
                cast($origin AS DATE),cast($end AS DATE),INTERVAL 1 DAY) t(value)
        ), naive AS (
            SELECT h.store_id,h.product_id,d.target_date,'naive' AS model,
                   h.dt AS source_observation_date,h.sale_amount AS forecast
            FROM train h CROSS JOIN dates d WHERE h.dt=cast($cutoff AS DATE)
        ), seasonal AS (
            SELECT store_id,product_id,cast(dt+INTERVAL 7 DAY AS DATE) AS target_date,
                   'seasonal_naive' AS model,dt AS source_observation_date,sale_amount AS forecast
            FROM train WHERE dt BETWEEN cast($origin AS DATE)-INTERVAL 7 DAY AND cast($cutoff AS DATE)
        )
        SELECT *,cast($origin AS DATE) AS forecast_origin,cast($cutoff AS DATE) AS cutoff_date,
               cast(date_diff('day',cast($origin AS DATE),target_date)+1 AS SMALLINT) AS horizon_step
        FROM (SELECT * FROM naive UNION ALL SELECT * FROM seasonal)
    """, {"origin":forecast_origin,"cutoff":cutoff,"end":end})
    invalid = connection.execute("""
        SELECT count(*) FROM predictions WHERE source_observation_date>=forecast_origin
            OR target_date<forecast_origin OR horizon_step NOT BETWEEN 1 AND 7
            OR forecast IS NULL OR NOT isfinite(forecast) OR forecast<0
    """).fetchone()[0]
    if invalid:
        raise ValueError("Previsões inválidas ou fonte posterior à origem.")
