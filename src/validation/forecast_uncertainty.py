"""Distribuições empíricas dos erros salvos: sem refit ou alteração de forecasts."""

import re

import numpy as np
import pandas as pd


KEYS=["store_id","product_id"]
ERROR_QUANTILES=[.10,.25,.50,.75,.90]
ABSOLUTE_QUANTILES=[.50,.90,.95]


def error_aggregation(connection,dimensions=(),source="observations",where="TRUE"):
    """Quantis lineares (tipo 7), desvios amostrais ddof=1 e percentuais nulos se D=0.

    source/where/dimensões são expressões internas fixas, nunca entradas do usuário.
    """
    if not re.fullmatch(r"[a-z_]+",source) or any(not re.fullmatch(r"[a-z_]+",d) for d in dimensions):
        raise ValueError("Identificador SQL inválido.")
    keys=", ".join(dimensions)
    select=keys+", " if keys else ""
    grouped=" GROUP BY "+keys if keys else ""
    ordered=" ORDER BY "+keys if keys else ""
    return connection.execute(f"""
        SELECT {select}count(*)::BIGINT AS n_forecasts,
            count(DISTINCT (store_id,product_id))::BIGINT AS n_series,
            count(DISTINCT product_id)::BIGINT AS n_products,
            count(DISTINCT fold_id)::BIGINT AS n_folds,
            sum(actual) AS actual_total,sum(forecast) AS forecast_total,
            avg(abs(error)) AS mae,sqrt(avg(error*error)) AS rmse,
            sum(abs(error))/nullif(sum(actual),0) AS wape,
            avg(error) AS bias,sum(error)/nullif(sum(actual),0) AS bias_pct,
            stddev_samp(error) AS error_std,stddev_samp(abs(error)) AS absolute_error_std,
            quantile_cont(abs(error),.50) AS p50_absolute_error,
            quantile_cont(abs(error),.90) AS p90_absolute_error,
            quantile_cont(abs(error),.95) AS p95_absolute_error,
            quantile_cont(error,.10) AS error_q10,quantile_cont(error,.25) AS error_q25,
            quantile_cont(error,.50) AS error_q50,quantile_cont(error,.75) AS error_q75,
            quantile_cont(error,.90) AS error_q90,
            count(*) FILTER(WHERE error<0)::BIGINT AS underforecast_days,
            avg((error<0)::INTEGER) AS underforecast_rate,
            count(*) FILTER(WHERE error>0)::BIGINT AS overforecast_days,
            avg((error>0)::INTEGER) AS overforecast_rate,
            count(*) FILTER(WHERE error=0)::BIGINT AS exact_forecast_days,
            sum(greatest(-error,0)) AS total_underforecast_amount,
            avg(-error) FILTER(WHERE error<0) AS mean_underforecast_amount_when_positive
        FROM {source} WHERE {where}{grouped}{ordered}
    """).df()


def attach_bias_persistence(series,series_fold):
    if series.duplicated(KEYS).any() or series_fold.duplicated([*KEYS,"fold_id"]).any():
        raise ValueError("Chaves duplicadas no perfil de erro.")
    fold_counts=series_fold.assign(negative=series_fold.bias.lt(0)).groupby(KEYS).agg(
        negative_bias_fold_count=("negative","sum"),bias_fold_count=("fold_id","nunique"))
    if not fold_counts.bias_fold_count.eq(4).all():
        raise ValueError("A regra de persistência exige exatamente quatro folds.")
    result=series.merge(fold_counts,on=KEYS,validate="one_to_one",how="left")
    if result.bias_fold_count.isna().any():
        raise ValueError("Série sem cobertura de folds.")
    result["negative_bias_fold_count"]=result.negative_bias_fold_count.astype("int64")
    result["persistent_underforecast_flag"]=result.bias.lt(0)&result.negative_bias_fold_count.ge(3)
    return result.sort_values(KEYS).reset_index(drop=True)


def metric_correlations(profile):
    rows=[]
    fields=["error_std","rmse","p90_absolute_error","p95_absolute_error"]
    for scope,part in [("ALL",profile),*profile.groupby("abc_class",observed=True,sort=True)]:
        for method in ["pearson","spearman"]:
            matrix=part[fields].corr(method=method)
            for i,left in enumerate(fields):
                for right in fields[i+1:]:
                    rows.append({"abc_scope":scope,"method":method,"metric_1":left,"metric_2":right,
                                 "correlation":matrix.loc[left,right],"n_series":len(part)})
    return pd.DataFrame(rows)


def descriptive_thresholds(profile):
    """Limiares somente para diagnóstico, sem redefinir a matriz de risco."""
    return {"low_actual_p05":float(profile.actual_total.quantile(.05)),
            "metric_p75":{m:float(profile[m].quantile(.75)) for m in
                ["error_std","rmse","p90_absolute_error","p95_absolute_error"]}}
