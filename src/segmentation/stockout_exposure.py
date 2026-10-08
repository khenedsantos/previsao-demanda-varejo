"""Disponibilidade como dimensão separada de XYZ: frequência relativa e flag."""

import numpy as np


SUPPORT_METRICS = ["stockout_rate","total_stockout_hours","maximum_consecutive_stockout_days",
                   "mean_stockout_hours_when_affected","zero_ratio"]


def fit_exposure_thresholds(profile):
    return {"low_quantile":.25,"high_quantile":.75,"zero_quantile":.75,
            "stockout_low":float(profile.stockout_rate.quantile(.25)),
            "stockout_high":float(profile.stockout_rate.quantile(.75)),
            "zero_high":float(profile.zero_ratio.quantile(.75)),"interpolation":"linear",
            "n_series":len(profile)}


def classify_exposure(profile, thresholds):
    result = profile[["store_id","product_id",*SUPPORT_METRICS]].copy()
    required = [c for c in SUPPORT_METRICS if c != "mean_stockout_hours_when_affected"]
    allowed_undefined_duration = (result.stockout_rate.eq(0) & result.total_stockout_hours.eq(0)
                                  & result.maximum_consecutive_stockout_days.eq(0))
    invalid_duration = result.mean_stockout_hours_when_affected.isna() & ~allowed_undefined_duration
    if result[required].isna().any().any() or invalid_duration.any():
        raise ValueError("Métrica de disponibilidade indefinida; não atribuir exposição silenciosamente.")
    if not result.stockout_rate.between(0,1).all() or not result.zero_ratio.between(0,1).all():
        raise ValueError("Taxas de ruptura/zero fora de [0,1].")
    high = result.stockout_rate.ge(thresholds["stockout_high"])
    low = result.stockout_rate.le(thresholds["stockout_low"])
    # HIGH tem prioridade se quantis coincidirem; todos os empates ficam juntos.
    result["stockout_exposure"] = np.select([high,low],["HIGH","LOW"],default="MEDIUM")
    result["censoring_risk_flag"] = high & result.zero_ratio.ge(thresholds["zero_high"])
    return result.sort_values(["store_id","product_id"]).reset_index(drop=True)
