"""Holt-Winters aditivo semanal, ajuste determinístico e fallback auditável."""

import warnings

import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from src.forecasting.baselines import HORIZON


SEASONAL_PERIOD=7
PRIMARY_MODEL="ets_ana"
SPECIFICATIONS={
    "ets_ana":{"trend":None,"seasonal":"add","seasonal_periods":SEASONAL_PERIOD},
    "ets_aaa":{"trend":"add","seasonal":"add","seasonal_periods":SEASONAL_PERIOD},
}
FIT_OPTIONS={"optimized":True,"use_brute":False,"method":"SLSQP",
             "minimize_kwargs":{"options":{"maxiter":200,"ftol":1e-6}},"remove_bias":False}


def forecast_history(history, specification=PRIMARY_MODEL):
    """Recebe somente o prefixo conhecido. Não recebe actuals do horizonte.

    A/N/A e A/A/A denotam erro aditivo, ausência/presença de tendência aditiva e
    sazonalidade aditiva. Estimação por soma de erros quadráticos no histórico.
    Projeta forecasts negativos em zero, guardando valores originais para auditoria;
    não transforma ou imputa os dados de entrada.
    """
    if specification not in SPECIFICATIONS:
        raise ValueError("Especificação ETS não autorizada.")
    y=np.asarray(history,dtype=np.float64)
    if y.ndim!=1 or len(y)<SEASONAL_PERIOD or not np.isfinite(y).all() or (y<0).any():
        raise ValueError("Histórico deve ter pelo menos sete vendas finitas e não negativas.")
    fallback=y[-SEASONAL_PERIOD:].copy()
    result={"model_requested":specification,"model_used":specification,"fallback_flag":False,
            "fallback_reason":"","warning_categories":"","converged":False}
    reason=""
    raw=None
    if len(y)<2*SEASONAL_PERIOD:
        reason="insufficient_seasonal_history"
    elif np.ptp(y)==0:
        reason="constant_history"
    else:
        try:
            with warnings.catch_warnings(record=True) as observed:
                warnings.simplefilter("always")
                fitted=ExponentialSmoothing(y,**SPECIFICATIONS[specification],
                    initialization_method="estimated",use_boxcox=False,missing="raise").fit(**FIT_OPTIONS)
                raw=np.asarray(fitted.forecast(HORIZON),dtype=np.float64)
            result["warning_categories"]=";".join(sorted({w.category.__name__ for w in observed}))
            result["converged"]=bool(fitted.mle_retvals.get("success",False))
            if not result["converged"]:
                reason="optimizer_not_converged"
            elif raw.shape!=(HORIZON,) or not np.isfinite(raw).all() or not np.isfinite(fitted.sse):
                reason="nonfinite_fit_or_forecast"
        except (ValueError,RuntimeError,FloatingPointError,OverflowError,np.linalg.LinAlgError) as error:
            reason=f"fit_exception:{type(error).__name__}"
    if reason:
        result.update(model_used="seasonal_naive",fallback_flag=True,fallback_reason=reason)
        raw=fallback
    result["forecast_unclipped"]=raw
    result["negative_clipped"]=raw<0
    result["forecast"]=np.maximum(raw,0.)
    return result
