"""Métricas por somas suficientes: nunca média ingênua de WAPEs/RMSEs."""

import numpy as np


LEVELS = {
    "series_fold":["store_id","product_id","fold_id","forecast_origin","abc_class","xyz_class","stockout_exposure","censoring_risk_flag"],
    "series":["store_id","product_id"],
    "fold":["fold_id","forecast_origin"],
    "global":[],
    "abc":["abc_class"],
    "xyz":["xyz_class"],
    "stockout_exposure":["stockout_exposure"],
    "censoring_risk_flag":["censoring_risk_flag"],
    "abc_xyz":["abc_class","xyz_class"],
    "abc_fold":["abc_class","fold_id","forecast_origin"],
    "xyz_fold":["xyz_class","fold_id","forecast_origin"],
    "stockout_exposure_fold":["stockout_exposure","fold_id","forecast_origin"],
    "censoring_risk_flag_fold":["censoring_risk_flag","fold_id","forecast_origin"],
    "abc_xyz_fold":["abc_class","xyz_class","fold_id","forecast_origin"],
}
DIMENSION_TYPES = {"store_id":"BIGINT","product_id":"BIGINT","fold_id":"INTEGER",
                   "forecast_origin":"DATE","abc_class":"VARCHAR","xyz_class":"VARCHAR",
                   "stockout_exposure":"VARCHAR","censoring_risk_flag":"BOOLEAN"}


def metrics_from_arrays(actual, forecast):
    """Contrato escalar usado também nos testes de fórmulas e sinais."""
    actual,forecast=np.asarray(actual,dtype=float),np.asarray(forecast,dtype=float)
    if actual.shape!=forecast.shape or actual.ndim!=1 or not actual.size:
        raise ValueError("Arrays devem ser unidimensionais, não vazios e de mesmo tamanho.")
    if not np.isfinite(actual).all() or not np.isfinite(forecast).all() or (actual<0).any():
        raise ValueError("Métricas exigem valores finitos e actual não negativo.")
    error=forecast-actual
    denominator=float(actual.sum())
    return {"mae":float(np.abs(error).mean()),"rmse":float(np.sqrt(np.square(error).mean())),
            "wape":float(np.abs(error).sum()/denominator) if denominator>0 else None,
            "bias":float(error.mean()),"bias_pct":float(error.sum()/denominator) if denominator>0 else None,
            "actual_sum":denominator,"n_forecasts":len(actual)}


def create_metric_tables(connection, forecast_path, segments_path):
    connection.execute("""
        CREATE TEMP TABLE atomic_metrics AS
        SELECT f.store_id,f.product_id,f.fold_id,f.forecast_origin,f.model,
               s.abc_class,s.xyz_class,s.stockout_exposure,s.censoring_risk_flag,
               count(*) AS n_forecasts,sum(f.actual) AS actual_sum,sum(f.forecast) AS forecast_sum,
               sum(abs(f.error)) AS absolute_error_sum,sum(f.error*f.error) AS squared_error_sum,
               sum(f.error) AS error_sum
        FROM read_parquet(?) f JOIN read_parquet(?) s
          USING(store_id,product_id,fold_id,forecast_origin)
        GROUP BY ALL
    """,[str(forecast_path),str(segments_path)])
    queries=[]
    for level,dimensions in LEVELS.items():
        columns=[name if name in dimensions else f"NULL::{kind} AS {name}" for name,kind in DIMENSION_TYPES.items()]
        group_by=", ".join(["model",*dimensions])
        queries.append(f"""
            SELECT '{level}' AS level,model,{', '.join(columns)},
                   count(DISTINCT (store_id,product_id)) AS n_series,
                   count(DISTINCT product_id) AS n_products,count(DISTINCT fold_id) AS n_folds,
                   count(*) AS n_series_folds,sum(n_forecasts)::BIGINT AS n_forecasts,
                   sum(actual_sum) AS actual_sum,sum(forecast_sum) AS forecast_sum,
                   sum(absolute_error_sum) AS absolute_error_sum,
                   sum(squared_error_sum) AS squared_error_sum,sum(error_sum) AS error_sum
            FROM atomic_metrics GROUP BY {group_by}
        """)
    connection.execute("CREATE TEMP TABLE metric_sums AS " + " UNION ALL ".join(queries))
    connection.execute("""
        CREATE TEMP TABLE metrics AS
        SELECT *,absolute_error_sum/n_forecasts AS mae,sqrt(squared_error_sum/n_forecasts) AS rmse,
               absolute_error_sum/nullif(actual_sum,0) AS wape,error_sum/n_forecasts AS bias,
               error_sum/nullif(actual_sum,0) AS bias_pct,actual_sum=0 AS undefined_percentage_metrics
        FROM metric_sums
    """)


def relative_improvement(naive, seasonal):
    """Melhora positiva = menor erro Seasonal Naive; referência zero fica indefinida."""
    if naive is None or seasonal is None or not np.isfinite(naive) or not np.isfinite(seasonal) or naive<=0:
        return None
    return float((naive-seasonal)/naive)
